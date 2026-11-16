# Adam Bot — Voice & Text API

Adam is a Python API that supports voice conversations and text conversations with a shared session history.

## What it does

1. Receives an audio upload or a text message.
2. Transcribes audio with OpenAI Speech-to-Text.
3. Generates a contextual reply with an OpenAI chat model.
4. Converts replies to MP3 using ElevenLabs.
5. Keeps a bounded in-memory conversation history per session.

## Requirements

- Python 3.10+
- OpenAI API access for transcription and chat completions
- ElevenLabs API access and a voice ID

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure the required environment variables. Keep the real `.env` file out of source control.

## Run locally

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open `/docs` for interactive API documentation.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Service information |
| GET | `/health` | Health check |
| POST | `/voice/chat` | Audio in, MP3 out |
| POST | `/text/chat` | Text in, text reply out |
| DELETE | `/sessions/{session_id}` | Clear a session's conversation history |

### Voice conversation

Send multipart form data with:
- `audio`: audio file (MP3, WAV, M4A/MP4, or WebM)
- `session_id`: optional session identifier; reuse it to continue a conversation

Example:

```bash
curl -X POST http://localhost:8000/voice/chat \\
  -F "audio=@voice-note.m4a" \\
  -F "session_id=customer-123" \\
  --output adam-reply.mp3
```

The response is MP3 audio. It includes `X-Adam-Session-ID`, `X-Adam-Transcript`, and `X-Adam-Reply` headers. Text headers are URL-encoded.

### Text conversation

```bash
curl -X POST http://localhost:8000/text/chat \\
  -H "Content-Type: application/json" \\
  -d '{"message":"Hello Adam","session_id":"customer-123"}'
```

The response contains `session_id`, `transcript`, and `reply`. Reuse the same session ID for context across text and voice messages.

### Clear a conversation

```bash
curl -X DELETE http://localhost:8000/sessions/customer-123
```

## Session behavior and limitations

- Conversation history is held in process memory, expires after 30 minutes of inactivity, and is bounded to the latest 24 messages per session.
- Sessions are lost when the server restarts and are not shared between multiple server instances.
- There is no user authentication, persistent database, rate limiting, billing enforcement, or platform-specific WhatsApp/Telegram integration yet.
- The API is a backend service; a website or messaging adapter must call these endpoints.

## Environment variables

See `.env.example` for model, voice, upload-size, and credential settings.
