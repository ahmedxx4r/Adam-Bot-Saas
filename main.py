import logging
from io import BytesIO
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from fastapi.responses import Response

from config import settings
from conversation_store import ConversationStore
from voice_handler import VoiceHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("adam")

app = FastAPI(
    title="Adam Voice API",
    description="Session-aware voice and text assistant API for Adam.",
    version="1.1.0",
)

voice_handler = None
conversations = ConversationStore()


class TextChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    session_id: str | None = Field(default=None, max_length=128)


class TextChatResponse(BaseModel):
    session_id: str
    transcript: str
    reply: str


def get_voice_handler():
    global voice_handler
    if voice_handler is None:
        try:
            voice_handler = VoiceHandler()
        except Exception as exc:
            logger.exception("Could not initialize Adam voice services")
            raise HTTPException(status_code=503, detail="Voice services are not configured") from exc
    return voice_handler


def resolve_session_id(value):
    if value and (len(value) > 128 or not value.strip()):
        raise HTTPException(status_code=400, detail="Invalid session_id")
    return value.strip() if value else str(uuid4())


def save_turn(session_id, result):
    conversations.add_turn(session_id, result["transcript"], result["reply"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "adam-voice-api", "version": app.version}


@app.post("/voice/chat")
async def voice_chat(
    audio: UploadFile = File(...),
    session_id: str | None = Form(default=None, max_length=128),
):
    """Upload a voice note; receive Adam's spoken answer as an MP3."""
    if not audio.filename:
        raise HTTPException(status_code=400, detail="An audio file is required")

    allowed_types = {
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
        "audio/mp4", "audio/m4a", "audio/x-m4a", "audio/webm",
        "application/octet-stream",
    }
    content_type = (audio.content_type or "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in allowed_types:
        raise HTTPException(status_code=415, detail="Unsupported audio content type")

    current_session = resolve_session_id(session_id)
    try:
        data = await audio.read(settings.max_upload_bytes + 1)
        if not data:
            raise HTTPException(status_code=400, detail="The audio file is empty")
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Audio file is too large")

        audio_stream = BytesIO(data)
        audio_stream.name = audio.filename
        history = conversations.get_history(current_session)
        result = await run_in_threadpool(
            get_voice_handler().process_audio, audio_stream, history
        )
        save_turn(current_session, result)
        return Response(
            content=result["audio"],
            media_type="audio/mpeg",
            headers={
                "X-Adam-Session-ID": current_session,
                "X-Adam-Transcript": quote(result["transcript"][:500]),
                "X-Adam-Reply": quote(result["reply"][:500]),
                "Content-Disposition": 'inline; filename="adam_reply.mp3"',
            },
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Voice request failed")
        raise HTTPException(status_code=502, detail="Voice processing failed; check server logs") from exc
    finally:
        await audio.close()


@app.post("/text/chat", response_model=TextChatResponse)
async def text_chat(payload: TextChatRequest):
    """Send a text message and receive Adam's text reply."""
    current_session = resolve_session_id(payload.session_id)
    history = conversations.get_history(current_session)
    try:
        result = await run_in_threadpool(
            get_voice_handler().process_text, payload.message, history
        )
        save_turn(current_session, result)
        return TextChatResponse(
            session_id=current_session,
            transcript=result["transcript"],
            reply=result["reply"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Text request failed")
        raise HTTPException(status_code=502, detail="Text processing failed; check server logs") from exc


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Clear the in-memory conversation history for one session."""
    conversations.clear(session_id)
    return {"status": "cleared", "session_id": session_id}


@app.get("/")
def root():
    return {
        "service": "Adam Voice API",
        "health": "/health",
        "voice_endpoint": "POST /voice/chat",
        "text_endpoint": "POST /text/chat",
        "session_endpoint": "DELETE /sessions/{session_id}",
        "docs": "/docs",
    }
