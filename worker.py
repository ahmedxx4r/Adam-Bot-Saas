"""Durable polling worker for persisted WhatsApp webhook events.

Run as a separate process: python worker.py
"""

import asyncio
import logging
import os

from integrations.whatsapp_processor import process_whatsapp_event
from webhook_store import WebhookEventStore


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("adam.worker")


async def run_worker() -> None:
    store = WebhookEventStore()
    poll_seconds = max(1.0, float(os.getenv("WORKER_POLL_SECONDS", "2")))
    logger.info("Adam WhatsApp worker started; polling every %.1f seconds", poll_seconds)
    while True:
        try:
            event_id = store.claim_next()
            if event_id is None:
                await asyncio.sleep(poll_seconds)
                continue
            logger.info("Claimed WhatsApp event %s", event_id)
            await process_whatsapp_event(event_id, already_claimed=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Worker loop failed; retrying after delay")
            await asyncio.sleep(poll_seconds)


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Adam WhatsApp worker stopped")
