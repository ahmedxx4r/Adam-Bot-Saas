"""Secure phone-origin verification for linking WhatsApp senders to accounts."""

import hashlib
import hmac
import os
import re
import secrets
import time

from sqlalchemy import delete, select

from database import SessionLocal
from database_models import WhatsAppIdentity, WhatsAppLinkChallenge


PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
CHALLENGE_TTL_SECONDS = 600
MAX_ATTEMPTS = 5


def _code_hash(user_id: int, phone: str, code: str) -> str:
    secret = os.getenv("AUTH_SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("AUTH_SECRET_KEY must be configured before linking WhatsApp")
    message = f"{user_id}:{phone}:{code}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


class WhatsAppIdentityService:
    def create_challenge(self, user_id: int, phone: str) -> dict:
        normalized = phone.strip()
        if not PHONE_PATTERN.fullmatch(normalized):
            raise ValueError("Enter the phone number in international E.164 format, for example +201XXXXXXXXX")
        code = f"{secrets.randbelow(100_000_000):08d}"
        digest = _code_hash(user_id, normalized, code)
        now = int(time.time())
        with SessionLocal() as db:
            linked = db.scalar(select(WhatsAppIdentity).where(WhatsAppIdentity.phone == normalized))
            if linked and linked.user_id != user_id:
                raise ValueError("This WhatsApp number is already linked to another account")
            active = db.scalar(select(WhatsAppLinkChallenge).where(
                WhatsAppLinkChallenge.user_id == user_id,
                WhatsAppLinkChallenge.phone == normalized,
                WhatsAppLinkChallenge.expires_at_unix >= now,
            ))
            if active is not None:
                raise ValueError("A verification code is already active. Wait for it to expire before requesting another.")
            db.execute(delete(WhatsAppLinkChallenge).where(WhatsAppLinkChallenge.user_id == user_id))
            db.add(WhatsAppLinkChallenge(
                user_id=user_id, phone=normalized, code_hash=digest,
                expires_at_unix=now + CHALLENGE_TTL_SECONDS, attempts=0,
            ))
            db.commit()
        return {"phone": normalized, "verification_code": code, "expires_in_seconds": CHALLENGE_TTL_SECONDS}

    def verify_inbound_code(self, phone: str, text: str) -> dict | None:
        code = (text or "").strip()
        if not re.fullmatch(r"\d{8}", code):
            return None
        now = int(time.time())
        with SessionLocal() as db:
            challenge = db.scalar(
                select(WhatsAppLinkChallenge)
                .where(WhatsAppLinkChallenge.phone == phone, WhatsAppLinkChallenge.expires_at_unix >= now)
                .order_by(WhatsAppLinkChallenge.created_at.desc())
            )
            if challenge is None or challenge.attempts >= MAX_ATTEMPTS:
                return None
            expected = _code_hash(challenge.user_id, phone, code)
            if not hmac.compare_digest(expected, challenge.code_hash):
                challenge.attempts += 1
                db.commit()
                return None
            existing = db.scalar(select(WhatsAppIdentity).where(WhatsAppIdentity.phone == phone))
            if existing and existing.user_id != challenge.user_id:
                db.delete(challenge)
                db.commit()
                return None
            if existing is None:
                db.add(WhatsAppIdentity(user_id=challenge.user_id, phone=phone))
            user_id = challenge.user_id
            db.delete(challenge)
            db.commit()
            return {"user_id": user_id, "phone": phone, "linked": True}

    def user_for_phone(self, phone: str) -> int | None:
        with SessionLocal() as db:
            identity = db.scalar(select(WhatsAppIdentity).where(WhatsAppIdentity.phone == phone))
            return identity.user_id if identity else None


    def linked_phone_for_user(self, user_id: int) -> str | None:
        with SessionLocal() as db:
            identity = db.scalar(select(WhatsAppIdentity).where(WhatsAppIdentity.user_id == user_id))
            return identity.phone if identity else None

    def unlink_user(self, user_id: int) -> bool:
        with SessionLocal() as db:
            identity = db.scalar(select(WhatsAppIdentity).where(WhatsAppIdentity.user_id == user_id))
            if identity is None:
                return False
            db.delete(identity)
            db.execute(delete(WhatsAppLinkChallenge).where(WhatsAppLinkChallenge.user_id == user_id))
            db.commit()
            return True
