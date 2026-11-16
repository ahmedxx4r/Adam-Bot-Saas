# Adam Bot — Voice API

A Python voice pipeline for Adam:

1. Accept an uploaded voice note.
2. Transcribe it with OpenAI Speech-to-Text.
3. Generate a reply with an OpenAI chat model.
4. Convert the reply to MP3 with ElevenLabs.
5. Return the MP3 audio to the caller.

## Requirements

- Python 3.10+
- An OpenAI API key with access to audio transcription and chat completions
- An ElevenLabs API key
- An ElevenLabs voice ID

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in:

- `OPENAI_API_KEY`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`

Set these as environment variables in your deployment platform. Do not commit the real `.env` file or expose API keys in client-side code.

## Run locally

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

- Health check: `GET /health`
- Interactive API docs: `GET /docs`
- Voice endpoint: `POST /voice/chat` with multipart form field named `audio`

Example:

```bash
curl -X POST http://localhost:8000/voice/chat \
  -F "audio=@voice-note.m4a" \
  --output adam-reply.mp3
```

The endpoint returns `audio/mpeg`. The response headers `X-Adam-Transcript` and `X-Adam-Reply` contain URL-encoded text (decode them in the client if needed).

## Important integration note

This repository currently provides a standalone HTTP voice API. It does not yet connect to WhatsApp, Telegram, or a website frontend. A platform adapter must download incoming voice notes, call `POST /voice/chat`, and send the returned MP3 to the conversation.

Conversation history, user authentication, persistent memory, rate limiting, and production deployment configuration are not implemented yet. Add those before exposing the service publicly.

## Environment variables

See [.env.example](.env.example) for the full list of settings.
