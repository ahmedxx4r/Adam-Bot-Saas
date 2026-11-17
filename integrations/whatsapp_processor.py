"""Process verified inbound WhatsApp events into account-scoped Adam task drafts."""

from io import BytesIO
import logging

from fastapi.concurrency import run_in_threadpool

from agent_core import AgentPlanner
from ai_brain import AIBrain
from config import settings
from integrations.meta_whatsapp import MetaWhatsAppClient
from task_store import TaskStore
from webhook_store import WebhookEventStore


logger = logging.getLogger("adam.whatsapp")
events = WebhookEventStore()
tasks = TaskStore()


async def process_whatsapp_event(event_id: int, already_claimed: bool = False) -> None:
    event = events.get(event_id)
    allowed_statuses = {"processing"} if already_claimed else {"received"}
    if event is None or event["status"] not in allowed_statuses:
        return
    if event["user_id"] is None:
        events.set_status(event_id, "ignored")
        return
    payload = event["payload"]
    if payload.get("link_verification") == "verified":
        events.set_status(event_id, "processed")
        return
    if not already_claimed:
        events.set_status(event_id, "processing")
    try:
        if event["event_type"] == "text":
            instruction = (payload.get("text") or "").strip()
        elif event["event_type"] == "audio":
            media_id = payload.get("media_id")
            if not media_id:
                raise ValueError("WhatsApp audio event did not include a media ID")
            audio_bytes, mime_type = await MetaWhatsAppClient().download_media(media_id)
            audio = BytesIO(audio_bytes)
            extension = "ogg" if "ogg" in mime_type else "mp3" if "mpeg" in mime_type else "m4a"
            audio.name = f"whatsapp-voice.{extension}"
            instruction = await run_in_threadpool(AIBrain().transcribe, audio)
        else:
            events.set_status(event_id, "ignored")
            return
        if not instruction:
            raise ValueError("No message text or speech was detected")
        plan = await run_in_threadpool(AgentPlanner().plan, instruction)
        initial_status = "awaiting_user_input" if plan["missing_fields"] else "awaiting_confirmation"
        task = tasks.create(
            user_id=event["user_id"],
            input_text=instruction,
            task_type=plan["task_type"],
            extracted_data={
                **plan["extracted_data"],
                "summary": plan["summary"],
                "missing_fields": plan["missing_fields"],
                "clarification_question": plan["clarification_question"],
                "proposed_steps": plan["proposed_steps"],
                "requires_confirmation": plan["requires_confirmation"],
                "safe_to_execute": False,
                "source": "whatsapp",
                "source_event_id": event_id,
            },
            initial_status=initial_status,
        )
        if settings.whatsapp_access_token and settings.whatsapp_phone_number_id:
            reply = plan["clarification_question"] or (
                f"فهمت طلبك وجهزت له خطة: {plan['summary']}\n"
                "راجع المهمة في لوحة Adam وأكدها قبل أي تنفيذ. لسه ما نفذتش أي إجراء خارجي."
            )
            try:
                await MetaWhatsAppClient().send_text(event["sender"], reply)
            except Exception:
                # The task remains safely saved even if the outbound acknowledgement fails.
                logger.exception("Could not send WhatsApp acknowledgement for task %s", task["id"])
        events.set_status(event_id, "processed")
    except Exception:
        logger.exception("WhatsApp event processing failed: %s", event_id)
        events.set_status(event_id, "failed")
