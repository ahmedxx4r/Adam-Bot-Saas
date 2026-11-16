import logging
from io import BytesIO
from urllib.parse import quote

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response

from config import settings
from voice_handler import VoiceHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("adam")

app = FastAPI(
    title="Adam Voice API",
    description="Voice-in, AI response, voice-out API for Adam.",
    version="1.0.0",
)

voice_handler = None


def get_voice_handler():
    global voice_handler
    if voice_handler is None:
        try:
            voice_handler = VoiceHandler()
        except Exception as exc:
            logger.exception("Could not initialize Adam voice services")
            raise HTTPException(status_code=503, detail="Voice services are not configured") from exc
    return voice_handler


@app.get("/health")
def health():
    return {"status": "ok", "service": "adam-voice-api"}


@app.post("/voice/chat")
async def voice_chat(audio: UploadFile = File(...)):
    """Upload a voice note; receive Adam's spoken answer as an MP3."""
    if not audio.filename:
        raise HTTPException(status_code=400, detail="An audio file is required")

    allowed_types = {
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
        "audio/mp4", "audio/m4a", "audio/x-m4a", "audio/ogg",
        "audio/webm", "audio/aac", "audio/3gpp",
        "application/octet-stream",
    }
    content_type = (audio.content_type or "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in allowed_types:
        raise HTTPException(status_code=415, detail="Unsupported audio content type")

    try:
        data = await audio.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Audio file is too large")
        audio_stream = BytesIO(data)
        audio_stream.name = audio.filename
        result = get_voice_handler().process_audio(audio_stream)
        return Response(
            content=result["audio"],
            media_type="audio/mpeg",
            headers={
                "X-Adam-Transcript": quote(result["transcript"][:500]),
                "X-Adam-Reply": quote(result["reply"][:500]),
                "Content-Disposition": 'inline; filename="adam_reply.mp3"',
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Voice request failed")
        raise HTTPException(status_code=502, detail="Voice processing failed; check server logs and API credentials") from exc
    finally:
        await audio.close()


@app.get("/")
def root():
    return {
        "service": "Adam Voice API",
        "health": "/health",
        "voice_endpoint": "POST /voice/chat",
        "docs": "/docs",
    }
