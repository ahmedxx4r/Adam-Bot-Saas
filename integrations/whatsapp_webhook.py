"""Meta WhatsApp webhook verification and inbound event normalization."""

import hashlib
import hmac
from typing import Any


def verify_signature(app_secret: str, body: bytes, signature_header: str | None) -> bool:
    if not app_secret or not signature_header:
        return False
    expected = "sha256=" + hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.strip())


def verify_webhook_challenge(mode: str | None, token: str | None, challenge: str | None, expected_token: str) -> str | None:
    if mode == "subscribe" and token and expected_token and hmac.compare_digest(token, expected_token) and challenge:
        return challenge
    return None


def normalize_webhook(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract user-originated text/audio messages; ignore status callbacks."""
    events = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            contacts = value.get("contacts", []) or []
            names = {item.get("wa_id"): (item.get("profile") or {}).get("name") for item in contacts}
            for message in value.get("messages", []) or []:
                kind = message.get("type")
                if kind == "text":
                    text = (message.get("text") or {}).get("body")
                    media_id = None
                    mime_type = None
                elif kind == "audio":
                    text = None
                    audio = message.get("audio") or {}
                    media_id = audio.get("id")
                    mime_type = audio.get("mime_type")
                else:
                    continue
                sender = message.get("from")
                if not sender:
                    continue
                events.append({
                    "provider": "meta",
                    "channel": "whatsapp",
                    "sender": sender,
                    "sender_name": names.get(sender),
                    "event_type": kind,
                    "text": text,
                    "media_id": media_id,
                    "media_mime_type": mime_type,
                    "provider_message_id": message.get("id"),
                    "timestamp": message.get("timestamp"),
                })
    return events
