from database import Base, SessionLocal, engine
from database_models import User, WebhookEvent, WhatsAppIdentity
from integrations.whatsapp_identity import WhatsAppIdentityService
from webhook_store import WebhookEventStore


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def create_user():
    with SessionLocal() as db:
        user = User(email="wa-link@example.com", password_hash="test-hash")
        db.add(user)
        db.commit()
        return user.id


def test_whatsapp_link_requires_code_from_the_claimed_sender(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-that-is-at-least-32-characters")
    user_id = create_user()
    service = WhatsAppIdentityService()
    challenge = service.create_challenge(user_id, "+201000000000")
    try:
        service.create_challenge(user_id, "+201000000000")
    except ValueError as exc:
        assert "already active" in str(exc)
    else:
        raise AssertionError("Expected active challenge rate limit")
    assert service.verify_inbound_code("+201000000001", challenge["verification_code"]) is None
    assert service.user_for_phone("+201000000000") is None
    linked = service.verify_inbound_code("+201000000000", challenge["verification_code"])
    assert linked == {"user_id": user_id, "phone": "+201000000000", "linked": True}
    assert service.user_for_phone("+201000000000") == user_id
    assert service.verify_inbound_code("+201000000000", challenge["verification_code"]) is None


def test_whatsapp_link_rejects_non_e164_phone_numbers():
    service = WhatsAppIdentityService()
    try:
        service.create_challenge(1, "01000000000")
    except ValueError as exc:
        assert "E.164" in str(exc)
    else:
        raise AssertionError("Expected invalid phone format to be rejected")


def test_persisted_inbound_messages_are_scoped_to_linked_account(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-that-is-at-least-32-characters")
    user_id = create_user()
    identities = WhatsAppIdentityService()
    challenge = identities.create_challenge(user_id, "+201000000000")
    identities.verify_inbound_code("+201000000000", challenge["verification_code"])
    result = WebhookEventStore().save_many([{
        "provider": "meta",
        "provider_message_id": "wamid.linked-event",
        "sender": "201000000000",
        "event_type": "text",
        "text": "hello",
    }])
    assert result["inserted"] == 1
    assert WebhookEventStore().list_recent()[0]["user_id"] == user_id


def test_worker_claims_only_linked_pending_events_once():
    user_id = create_user()
    with SessionLocal() as db:
        db.add(WhatsAppIdentity(user_id=user_id, phone="+201000000000"))
        db.commit()
    store = WebhookEventStore()
    result = store.save_many([{
        "provider": "meta",
        "provider_message_id": "wamid.worker-claim",
        "sender": "201000000000",
        "event_type": "text",
        "text": "hello",
    }])
    assert result["inserted"] == 1
    event_id = store.claim_next()
    assert event_id == result["event_ids"][0]
    assert store.get(event_id)["status"] == "processing"
    store.set_status(event_id, "failed")
    assert store.claim_next() is None  # Exponential retry delay is active.
    with SessionLocal() as db:
        row = db.get(WebhookEvent, event_id)
        row.next_attempt_at_unix = 0  # Simulate the retry delay expiring.
        db.commit()
    assert store.claim_next() == event_id
    assert store.get(event_id)["attempts"] == 2
    assert store.claim_next() is None
