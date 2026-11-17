import hashlib
import hmac

from database import Base, engine
from integrations.whatsapp_webhook import normalize_webhook, verify_signature, verify_webhook_challenge
from webhook_store import WebhookEventStore


def test_meta_signature_verification():
    secret = "test-app-secret"
    body = b'{"object":"whatsapp_business_account"}'
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(secret, body, "sha256=" + digest)
    assert not verify_signature(secret, body, "sha256=wrong")
    assert not verify_signature("", body, "sha256=" + digest)


def test_webhook_challenge_requires_matching_token():
    assert verify_webhook_challenge("subscribe", "verify-me", "123", "verify-me") == "123"
    assert verify_webhook_challenge("subscribe", "wrong", "123", "verify-me") is None


def test_normalize_text_and_audio_messages_and_ignore_statuses():
    payload = {"entry": [{"changes": [{"value": {
        "contacts": [{"wa_id": "201000000000", "profile": {"name": "Ahmed"}}],
        "messages": [
            {"id": "wamid.text", "from": "201000000000", "type": "text", "text": {"body": "احجزلي مطعم"}},
            {"id": "wamid.audio", "from": "201000000000", "type": "audio", "audio": {"id": "media-1", "mime_type": "audio/ogg"}},
        ],
        "statuses": [{"id": "wamid.status", "status": "delivered"}],
    }}]}]}
    events = normalize_webhook(payload)
    assert len(events) == 2
    assert events[0]["text"] == "احجزلي مطعم"
    assert events[1]["media_id"] == "media-1"
    assert events[1]["event_type"] == "audio"


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_webhook_events_are_persisted_and_duplicate_message_ids_are_ignored():
    store = WebhookEventStore()
    event = {
        "provider": "meta",
        "provider_message_id": "wamid.unique-1",
        "sender": "201000000000",
        "event_type": "text",
        "text": "Hello Adam",
    }
    first = store.save_many([event])
    second = store.save_many([event])
    assert first["inserted"] == 1
    assert first["duplicates"] == 0
    assert second["inserted"] == 0
    assert second["duplicates"] == 1
    saved = store.list_recent()
    assert len(saved) == 1
    assert saved[0]["payload"]["text"] == "Hello Adam"
