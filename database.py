import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def build_database_url():
    url = os.getenv("DATABASE_URL", "sqlite:///./adam.db")
    # Some hosts provide postgres://; SQLAlchemy expects postgresql://.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


DATABASE_URL = build_database_url()
engine_options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def ensure_webhook_event_schema(bind=engine):
    """Additive compatibility migration for databases created by earlier app versions."""
    inspector = inspect(bind)
    if "webhook_events" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("webhook_events")}
    additions = {
        "user_id": "INTEGER REFERENCES users(id) ON DELETE SET NULL",
        "attempts": "INTEGER NOT NULL DEFAULT 0",
        "next_attempt_at_unix": "INTEGER NOT NULL DEFAULT 0",
        "processing_started_at_unix": "INTEGER",
    }
    with bind.begin() as connection:
        for name, definition in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE webhook_events ADD COLUMN {name} {definition}"))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_webhook_events_user_id ON webhook_events (user_id)"
        ))


def init_database():
    from database_models import (  # noqa: F401
        AgentTask, Conversation, Message, User, WebhookEvent,
        WhatsAppIdentity, WhatsAppLinkChallenge,
    )
    Base.metadata.create_all(bind=engine)
    ensure_webhook_event_schema()
