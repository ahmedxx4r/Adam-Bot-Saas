"""Provider-neutral contracts for Adam communication channels.

Concrete providers (Twilio, a local SIP carrier, Meta Cloud API, etc.) must
implement these contracts. The agent core must not depend on a vendor SDK.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class OutboundCallRequest:
    to_number: str
    task_id: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OutboundMessage:
    to_number: str
    text: str | None = None
    audio_url: str | None = None
    audio_mime_type: str | None = None
    is_voice_note: bool = False


@dataclass(slots=True)
class InboundEvent:
    provider: str
    channel: str
    sender: str
    event_type: str
    text: str | None = None
    media_id: str | None = None
    media_mime_type: str | None = None
    provider_message_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PhoneProvider(Protocol):
    """A PSTN/SIP provider capable of starting and controlling phone calls."""

    async def start_outbound_call(self, request: OutboundCallRequest) -> str:
        """Start a call and return the provider call ID."""
        ...

    async def hangup(self, call_id: str) -> None:
        ...


class WhatsAppProvider(Protocol):
    """WhatsApp transport; voice-note transcription belongs to the agent layer."""

    async def send_message(self, message: OutboundMessage) -> str:
        """Send text or audio and return the provider message ID."""
        ...

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        """Return media bytes and the provider-reported MIME type."""
        ...


class EventProcessor(Protocol):
    async def handle_inbound_event(self, event: InboundEvent) -> None:
        ...
