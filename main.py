import logging
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from config import settings
from database import engine
from database import init_database
from conversation_store import ConversationStore
from voice_handler import VoiceHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("adam")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="Adam Voice API",
    description="Persistent session-aware voice and text assistant API for Adam.",
    version="1.2.0",
    lifespan=lifespan,
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


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception:
        logger.exception("Database health check failed")
        database_status = "error"
    return {
        "status": "ok" if database_status == "ok" else "degraded",
        "database": database_status,
        "service": "adam-voice-api",
        "version": app.version,
    }


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
        history = await run_in_threadpool(conversations.get_history, current_session)
        result = await run_in_threadpool(
            get_voice_handler().process_audio, audio_stream, history
        )
        await run_in_threadpool(
            conversations.add_turn, current_session, result["transcript"], result["reply"]
        )
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
    current_session = resolve_session_id(payload.session_id)
    history = await run_in_threadpool(conversations.get_history, current_session)
    try:
        result = await run_in_threadpool(
            get_voice_handler().process_text, payload.message, history
        )
        await run_in_threadpool(
            conversations.add_turn, current_session, result["transcript"], result["reply"]
        )
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
async def delete_session(session_id: str):
    await run_in_threadpool(conversations.clear, session_id)
    return {"status": "cleared", "session_id": session_id}
