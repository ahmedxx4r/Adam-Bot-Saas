import time

from conversation_store import ConversationStore


def test_history_is_saved_and_trimmed():
    store = ConversationStore(ttl_seconds=60, max_sessions=10, max_messages=2)
    store.add_turn("s1", "hello", "hi")
    store.add_turn("s1", "how are you?", "great")
    history = store.get_history("s1")
    assert history == [
        {"role": "user", "content": "how are you?"},
        {"role": "assistant", "content": "great"},
    ]


def test_clear_session():
    store = ConversationStore()
    store.add_turn("s1", "hello", "hi")
    store.clear("s1")
    assert store.get_history("s1") == []


def test_expired_session_is_removed():
    store = ConversationStore(ttl_seconds=0)
    store.add_turn("s1", "hello", "hi")
    time.sleep(0.01)
    assert store.get_history("s1") == []
