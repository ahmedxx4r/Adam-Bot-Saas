"""Persistence and deduplication for inbound provider webhook events."""

import json
import time

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from database_models import WebhookEvent, WhatsAppIdentity


class WebhookEventStore:
    def save_many(self, events: list[dict]) -> dict:
        inserted = 0
        duplicates = 0
        saved_ids = []
        with SessionLocal() as db:
            for event in events:
                provider = str(event.get("provider") or "unknown")[:32]
                message_id = event.get("provider_message_id")
                if message_id and db.scalar(select(WebhookEvent.id).where(
                    WebhookEvent.provider == provider,
                    WebhookEvent.provider_message_id == str(message_id),
                )) is not None:
                    duplicates += 1
                    continue
                record = WebhookEvent(
                    provider=provider,
                    provider_message_id=str(message_id)[:255] if message_id else None,
                    sender=str(event.get("sender") or "unknown")[:64],
                    user_id=(db.scalar(select(WhatsAppIdentity.user_id).where(WhatsAppIdentity.phone == "+" + str(event.get("sender")))) if event.get("sender") else None),
                    event_type=str(event.get("event_type") or "unknown")[:32],
                    payload=json.dumps(event, ensure_ascii=False),
                    status="received",
                )
                try:
                    with db.begin_nested():
                        db.add(record)
                        db.flush()
                except IntegrityError:
                    duplicates += 1
                    continue
                saved_ids.append(record.id)
                inserted += 1
            db.commit()
        return {"inserted": inserted, "duplicates": duplicates, "event_ids": saved_ids}

    def claim_next(self) -> int | None:
        """Atomically claim one pending linked event for a durable worker."""
        with SessionLocal() as db:
            candidate = db.scalar(
                select(WebhookEvent.id)
                .where(
                    WebhookEvent.status.in_({"received", "failed"}),
                    WebhookEvent.user_id.is_not(None),
                    WebhookEvent.attempts < 5,
                    WebhookEvent.next_attempt_at_unix <= int(time.time()),
                )
                .order_by(WebhookEvent.created_at.asc())
                .limit(1)
            )
            if candidate is None:
                return None
            result = db.execute(
                update(WebhookEvent)
                .where(WebhookEvent.id == candidate, WebhookEvent.status.in_({"received", "failed"}), WebhookEvent.attempts < 5)
                .values(status="processing", attempts=WebhookEvent.attempts + 1)
            )
            db.commit()
            return candidate if result.rowcount == 1 else None

    def get(self, event_id: int) -> dict | None:
        with SessionLocal() as db:
            row = db.get(WebhookEvent, event_id)
            if row is None:
                return None
            return {
                "id": row.id, "provider": row.provider,
                "provider_message_id": row.provider_message_id,
                "sender": row.sender, "user_id": row.user_id,
                "event_type": row.event_type, "payload": json.loads(row.payload),
                "status": row.status, "attempts": row.attempts,
            }

    def set_status(self, event_id: int, status: str) -> None:
        if status not in {"received", "processing", "processed", "failed", "ignored"}:
            raise ValueError("Invalid webhook event status")
        with SessionLocal() as db:
            row = db.get(WebhookEvent, event_id)
            if row is not None:
                row.status = status
                if status == "failed":
                    delay = min(30 * (2 ** max(row.attempts - 1, 0)), 900)
                    row.next_attempt_at_unix = int(time.time()) + delay
                db.commit()
    def list_recent(self, limit: int = 100) -> list[dict]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(WebhookEvent).order_by(WebhookEvent.created_at.desc()).limit(max(1, min(limit, 500)))
            ).all()
            return [
                {
                    "id": row.id,
                    "provider": row.provider,
                    "provider_message_id": row.provider_message_id,
                    "sender": row.sender,
                    "user_id": row.user_id,
                    "event_type": row.event_type,
                    "payload": json.loads(row.payload),
                    "status": row.status, "attempts": row.attempts,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
