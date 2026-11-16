import threading
import time
from collections import OrderedDict


class ConversationStore:
    """Small in-memory conversation store with TTL and bounded capacity."""

    def __init__(self, ttl_seconds=1800, max_sessions=1000, max_messages=24):
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self.max_messages = max_messages
        self._sessions = OrderedDict()
        self._lock = threading.RLock()

    def _prune(self, now):
        expired = [
            session_id for session_id, item in self._sessions.items()
            if now - item["updated_at"] > self.ttl_seconds
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)
        while len(self._sessions) > self.max_sessions:
            self._sessions.popitem(last=False)

    def get_history(self, session_id):
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            item = self._sessions.get(session_id)
            if item is None:
                return []
            item["updated_at"] = now
            self._sessions.move_to_end(session_id)
            return list(item["messages"])

    def add_turn(self, session_id, user_text, assistant_text):
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            item = self._sessions.setdefault(
                session_id, {"messages": [], "updated_at": now}
            )
            item["messages"].extend([
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": assistant_text},
            ])
            item["messages"] = item["messages"][-self.max_messages:]
            item["updated_at"] = now
            self._sessions.move_to_end(session_id)
            self._prune(now)

    def clear(self, session_id):
        with self._lock:
            self._sessions.pop(session_id, None)
