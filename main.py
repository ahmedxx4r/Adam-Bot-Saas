import logging
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from auth import create_access_token, get_current_user, hash_password, verify_password
from agent_core import AgentPlanner
from config import settings
from database import SessionLocal, engine, init_database
from database_models import User
from task_store import TaskStore
from conversation_store import ConversationStore
from voice_handler import VoiceHandler
from integrations.whatsapp_webhook import normalize_webhook, verify_signature, verify_webhook_challenge
from integrations.whatsapp_identity import WhatsAppIdentityService
from webhook_store import WebhookEventStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("adam")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="Adam Voice API",
    description="Authenticated, persistent voice and text assistant API for Adam.",
    version="2.0.0",
    lifespan=lifespan,
)

voice_handler = None
conversations = ConversationStore()
tasks = TaskStore()
webhook_events = WebhookEventStore()
whatsapp_identities = WhatsAppIdentityService()


class AuthRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=10, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str


class TextChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    session_id: str | None = Field(default=None, max_length=128)


class TextChatResponse(BaseModel):
    session_id: str
    transcript: str
    reply: str


class CreateTaskRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=12000)
    task_type: str = Field(default="general", max_length=64)
    details: dict = Field(default_factory=dict)


class AgentPlanRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=12000)
    session_id: str | None = Field(default=None, max_length=128)


class TaskDetailsRequest(BaseModel):
    details: dict = Field(default_factory=dict)
    missing_fields: list[str] | None = None


class WhatsAppLinkRequest(BaseModel):
    phone: str = Field(min_length=9, max_length=16)


class TaskStatusRequest(BaseModel):
    status: str = Field(min_length=3, max_length=32)
    result: str | None = Field(default=None, max_length=12000)
    error: str | None = Field(default=None, max_length=4000)


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


def scoped_session_id(user: User, external_session_id: str) -> str:
    # Internal IDs are deterministic per account, preventing cross-account history access.
    return str(uuid5(NAMESPACE_URL, f"adam:{user.id}:{external_session_id}"))


def auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(user.id),
        user_id=user.id,
        email=user.email,
    )


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.post("/auth/register", response_model=AuthResponse, status_code=201)
def register(payload: AuthRequest):
    email = payload.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(status_code=422, detail="A valid email address is required")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        user = User(email=email, password_hash=hash_password(payload.password))
        db.add(user)
        try:
            db.flush()
            response = auth_response(user)  # Validate signing configuration before committing.
            db.commit()
            return response
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="An account with this email already exists") from exc


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: AuthRequest):
    email = payload.email.strip().lower()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        return auth_response(user)


@app.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"user_id": user.id, "email": user.email}


@app.post("/agent/plan")
def plan_agent_task(payload: AgentPlanRequest, user: User = Depends(get_current_user)):
    """Understand a request and return a proposed plan without executing actions."""
    try:
        plan = AgentPlanner().plan(payload.instruction.strip())
        return {
            **plan,
            "execution_started": False,
            "notice": "Planning only. No external call, message, booking, or purchase was made.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Agent planning failed")
        raise HTTPException(status_code=503, detail="Agent planner is unavailable") from exc


@app.post("/agent/tasks", status_code=201)
def create_agent_task(payload: AgentPlanRequest, user: User = Depends(get_current_user)):
    """Plan a request and save it as a draft awaiting details or user confirmation."""
    try:
        plan = AgentPlanner().plan(payload.instruction.strip())
        initial_status = "awaiting_user_input" if plan["missing_fields"] else "awaiting_confirmation"
        task = tasks.create(
            user_id=user.id,
            input_text=payload.instruction.strip(),
            task_type=plan["task_type"],
            extracted_data={
                **plan["extracted_data"],
                "summary": plan["summary"],
                "missing_fields": plan["missing_fields"],
                "clarification_question": plan["clarification_question"],
                "proposed_steps": plan["proposed_steps"],
                "requires_confirmation": plan["requires_confirmation"],
                "safe_to_execute": False,
            },
            initial_status=initial_status,
        )
        return {
            "task": task,
            "plan": plan,
            "execution_started": False,
            "notice": "Task saved only. No external action was executed.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Agent task creation failed")
        raise HTTPException(status_code=503, detail="Agent planner is unavailable") from exc


@app.post("/tasks", status_code=201)
def create_task(payload: CreateTaskRequest, user: User = Depends(get_current_user)):
    """Create a task draft. External actions are never executed automatically."""
    return tasks.create(
        user_id=user.id,
        input_text=payload.instruction.strip(),
        task_type=payload.task_type.strip().lower() or "general",
        extracted_data=payload.details,
    )


@app.get("/tasks")
def list_tasks(user: User = Depends(get_current_user)):
    return {"tasks": tasks.list(user.id)}


@app.get("/tasks/{task_id}")
def get_task(task_id: str, user: User = Depends(get_current_user)):
    task = tasks.get(user.id, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.patch("/tasks/{task_id}/details")
def update_task_details(
    task_id: str,
    payload: TaskDetailsRequest,
    user: User = Depends(get_current_user),
):
    try:
        task = tasks.update_details(user.id, task_id, payload.details, payload.missing_fields)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.patch("/tasks/{task_id}/status")
def update_task_status(
    task_id: str,
    payload: TaskStatusRequest,
    user: User = Depends(get_current_user),
):
    try:
        task = tasks.transition(
            user_id=user.id,
            task_id=task_id,
            new_status=payload.status,
            result=payload.result,
            error=payload.error,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/integrations/whatsapp/link")
def create_whatsapp_link(payload: WhatsAppLinkRequest, user: User = Depends(get_current_user)):
    """Create a short-lived code that the account owner must send from their WhatsApp number."""
    try:
        return whatsapp_identities.create_challenge(user.id, payload.phone)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

@app.get("/webhooks/whatsapp")
def verify_whatsapp_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    challenge = verify_webhook_challenge(
        hub_mode, hub_verify_token, hub_challenge, settings.whatsapp_verify_token
    )
    if challenge is None:
        raise HTTPException(status_code=403, detail="WhatsApp webhook verification failed")
    return Response(content=challenge, media_type="text/plain")


@app.post("/webhooks/whatsapp")
async def receive_whatsapp_webhook(request: Request):
    body = await request.body()
    if len(body) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Webhook payload is too large")
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_signature(settings.whatsapp_app_secret, body, signature):
        raise HTTPException(status_code=401, detail="Invalid WhatsApp webhook signature")
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc
    events = normalize_webhook(payload)
    verified_links = 0
    for event in events:
        if event["event_type"] == "text" and event.get("text"):
            link = whatsapp_identities.verify_inbound_code("+" + event["sender"], event["text"])
            if link:
                event["text"] = "[WhatsApp verification code redacted]"
                event["link_verification"] = "verified"
                verified_links += 1
    try:
        persistence = webhook_events.save_many(events)
    except Exception as exc:
        logger.exception("Could not persist WhatsApp webhook events")
        raise HTTPException(status_code=503, detail="Webhook event storage is temporarily unavailable") from exc
    # Persist first; a separate worker claims linked events from the durable queue.
    return {
        "status": "accepted",
        "received": len(events),
        "verified_links": verified_links,
        "persisted": persistence["inserted"],
        "duplicates": persistence["duplicates"],
        "event_ids": persistence["event_ids"],
        "processed": False,
    }


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
    user: User = Depends(get_current_user),
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

    external_session = resolve_session_id(session_id)
    storage_session = scoped_session_id(user, external_session)
    try:
        data = await audio.read(settings.max_upload_bytes + 1)
        if not data:
            raise HTTPException(status_code=400, detail="The audio file is empty")
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Audio file is too large")
        audio_stream = BytesIO(data)
        audio_stream.name = audio.filename
        history = await run_in_threadpool(conversations.get_history, storage_session)
        result = await run_in_threadpool(
            get_voice_handler().process_audio, audio_stream, history
        )
        await run_in_threadpool(
            conversations.add_turn, storage_session, result["transcript"], result["reply"]
        )
        return Response(
            content=result["audio"],
            media_type="audio/mpeg",
            headers={
                "X-Adam-Session-ID": external_session,
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
async def text_chat(payload: TextChatRequest, user: User = Depends(get_current_user)):
    external_session = resolve_session_id(payload.session_id)
    storage_session = scoped_session_id(user, external_session)
    history = await run_in_threadpool(conversations.get_history, storage_session)
    try:
        result = await run_in_threadpool(
            get_voice_handler().process_text, payload.message, history
        )
        await run_in_threadpool(
            conversations.add_turn, storage_session, result["transcript"], result["reply"]
        )
        return TextChatResponse(
            session_id=external_session,
            transcript=result["transcript"],
            reply=result["reply"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Text request failed")
        raise HTTPException(status_code=502, detail="Text processing failed; check server logs") from exc


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: User = Depends(get_current_user)):
    external_session = resolve_session_id(session_id)
    storage_session = scoped_session_id(user, external_session)
    await run_in_threadpool(conversations.clear, storage_session)
    return {"status": "cleared", "session_id": external_session}
