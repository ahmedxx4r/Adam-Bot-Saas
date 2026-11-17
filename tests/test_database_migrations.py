from sqlalchemy import create_engine, inspect, text

from database import ensure_webhook_event_schema


def test_additive_webhook_schema_migration_adds_new_columns():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("""
            CREATE TABLE webhook_events (
                id INTEGER PRIMARY KEY,
                provider VARCHAR(32) NOT NULL,
                provider_message_id VARCHAR(255),
                sender VARCHAR(64) NOT NULL,
                event_type VARCHAR(32) NOT NULL,
                payload TEXT NOT NULL,
                status VARCHAR(24) NOT NULL,
                created_at DATETIME
            )
        """))

    ensure_webhook_event_schema(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("webhook_events")}
    assert {
        "user_id",
        "attempts",
        "next_attempt_at_unix",
        "processing_started_at_unix",
    }.issubset(columns)
