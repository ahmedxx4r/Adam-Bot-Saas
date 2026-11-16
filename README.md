# Adam Bot — Voice & Text API

Adam is a Python API for voice and text conversations, with persistent conversation history and a small developer playground.

## Features

- OpenAI speech transcription and chat responses.
- ElevenLabs MP3 speech generation.
- Shared context across voice and text messages.
- Persistent SQL conversation storage (SQLite by default; PostgreSQL supported).
- Conversation expiration and bounded message history.
- Docker runtime and automated test workflow.
- Browser-based developer playground at `/`; interactive API docs at `/docs`.

## Setup

Python 3.10+ is required.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

Set the required environment variables from `.env.example` in your local environment. Keep actual credentials out of source control.

Optional database configuration:
- `DATABASE_URL=sqlite:///./adam.db` (default)
- PostgreSQL example: `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/adam`

## Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open the developer playground at `/` and API docs at `/docs`.

## Accounts and authentication

- Create an account with `POST /auth/register` using an email and a password of at least 10 characters.
- Sign in with `POST /auth/login`; both endpoints return a 24-hour bearer token.
- Send `Authorization: Bearer <token>` with text chat, voice chat, and session deletion requests.
- Set `AUTH_SECRET_KEY` to a cryptographically random value of at least 32 characters. Authentication endpoints remain unavailable until it is configured.
- Conversation storage IDs are scoped by authenticated account, so users cannot read another account's history by guessing a session ID.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Developer playground |
| GET | `/health` | Health check |
| POST | `/voice/chat` | Audio in, MP3 out |
| POST | `/text/chat` | Text in, text reply out |
| DELETE | `/sessions/{session_id}` | Delete one conversation |

### Text chat

```bash
curl -X POST http://localhost:8000/text/chat \\
  -H "Content-Type: application/json" \\
  -d '{"message":"Hello Adam","session_id":"demo-01"}'
```

### Voice chat

```bash
curl -X POST http://localhost:8000/voice/chat \\
  -F "audio=@voice-note.m4a" \\
  -F "session_id=demo-01" \\
  --output adam-reply.mp3
```

Reuse the same session ID to share context between voice and text.

## Database and session behavior

- SQLite is used by default and creates `adam.db` automatically.
- Set `DATABASE_URL` to use PostgreSQL.
- Conversation history expires after 30 days of inactivity and retains the latest 24 messages per session.
- Run database migrations before deploying schema changes to an established production database; the current bootstrap creates missing tables but does not migrate existing schemas.

## Current limitations

- No account registration, authentication, per-user authorization, or billing/usage metering yet.
- The root page is a developer playground, not a secured multi-user admin dashboard.
- WhatsApp/Telegram provider integration is not connected; it requires a chosen provider and its account credentials/webhook configuration.
- Audio processing has not been validated against live provider credentials or all mobile voice-note codecs.
- For production, add migrations, authentication, rate limiting, monitoring, and a persistent PostgreSQL service.

## Environment

See `.env.example` for AI, voice, upload, and database settings.
