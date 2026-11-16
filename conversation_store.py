from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from database import SessionLocal
from database_models import Conversation, Message


class ConversationStore:
    """Persistent SQL-backed conversation history."""

    def __init__(self, ttl_seconds=30 * 24 * 60 * 60, max_sessions=10000, max_messages=24):
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self.max_messages = max_messages

    def _expire(self, db):
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.ttl_seconds)
        db.execute(delete(Conversation).where(Conversation.updated_at < cutoff))

    def get_history(self, session_id):
        with SessionLocal() as db:
            self._expire(db)
            conversation = db.get(Conversation, session_id)
            if conversation is None:
                db.commit()
                return []
            conversation.updated_at = datetime.now(timezone.utc)
            rows = db.scalars(
                select(Message)
                .where(Message.conversation_id == session_id)
                .order_by(Message.id.desc())
                .limit(self.max_messages)
            ).all()
            db.commit()
            rows.reverse()
            return [{"role": row.role, "content": row.content} for row in rows]

    def add_turn(self, session_id, user_text, assistant_text):
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            self._expire(db)
            conversation = db.get(Conversation, session_id)
            if conversation is None:
                conversation = Conversation(id=session_id, created_at=now, updated_at=now)
                db.add(conversation)
                db.flush()
            conversation.updated_at = now
            db.add_all([
                Message(conversation_id=session_id, role="user", content=user_text),
                Message(conversation_id=session_id, role="assistant", content=assistant_text),
            ])
            db.flush()
            stale_ids = db.scalars(
                select(Message.id)
                .where(Message.conversation_id == session_id)
                .order_by(Message.id.desc())
                .offset(self.max_messages)
            ).all()
            if stale_ids:
                db.execute(delete(Message).where(Message.id.in_(stale_ids)))
            db.commit()

    def clear(self, session_id):
        with SessionLocal() as db:
            db.execute(delete(Conversation).where(Conversation.id == session_id))
            db.commit()
