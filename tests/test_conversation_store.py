from conversation_store import ConversationStore
from database import Base, engine


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_history_is_saved_and_trimmed():
    store = ConversationStore(max_messages=2)
    store.add_turn("s1", "hello", "hi")
    store.add_turn("s1", "how are you?", "great")
    assert store.get_history("s1") == [
        {"role": "user", "content": "how are you?"},
        {"role": "assistant", "content": "great"},
    ]


def test_clear_session():
    store = ConversationStore()
    store.add_turn("s1", "hello", "hi")
    store.clear("s1")
    assert store.get_history("s1") == []


def test_history_persists_between_store_instances():
    ConversationStore().add_turn("persistent", "remember me", "I will")
    assert ConversationStore().get_history("persistent") == [
        {"role": "user", "content": "remember me"},
        {"role": "assistant", "content": "I will"},
    ]
