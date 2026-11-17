"""Official Meta WhatsApp Cloud API transport adapter."""

import httpx

from config import settings
from integrations.audio import mp3_to_ogg_opus


class MetaWhatsAppClient:
    def __init__(self, access_token: str | None = None, phone_number_id: str | None = None, graph_version: str | None = None):
        self.access_token = access_token or settings.whatsapp_access_token
        self.phone_number_id = phone_number_id or settings.whatsapp_phone_number_id
        self.graph_version = graph_version or settings.whatsapp_graph_api_version
        self.base_url = f"https://graph.facebook.com/{self.graph_version}"

    def _require_config(self):
        if not self.access_token or not self.phone_number_id:
            raise RuntimeError("WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID are required")

    def _headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        self._require_config()
        timeout = httpx.Timeout(45.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            metadata = await client.get(f"{self.base_url}/{media_id}", headers=self._headers())
            metadata.raise_for_status()
            media_url = metadata.json().get("url")
            mime_type = metadata.json().get("mime_type", "application/octet-stream")
            if not media_url:
                raise RuntimeError("Meta did not return a media download URL")
            response = await client.get(media_url, headers=self._headers())
            response.raise_for_status()
            return response.content, response.headers.get("content-type", mime_type)

    async def send_text(self, to_number: str, text: str) -> str:
        self._require_config()
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/{self.phone_number_id}/messages",
                headers={**self._headers(), "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            messages = response.json().get("messages", [])
            if not messages:
                raise RuntimeError("Meta did not return a WhatsApp message ID")
            return messages[0]["id"]

    async def send_voice_note(self, to_number: str, audio_bytes: bytes, filename: str = "reply.ogg", mime_type: str = "audio/ogg") -> str:
        """Upload an OGG/Opus file and send it as a WhatsApp voice message."""
        self._require_config()
        if not audio_bytes:
            raise ValueError("Audio payload cannot be empty")
        if mime_type.split(";", 1)[0].strip().lower() != "audio/ogg":
            raise ValueError("WhatsApp voice notes must be provided as OGG audio; transcode to Opus first")
        timeout = httpx.Timeout(60.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            upload = await client.post(
                f"{self.base_url}/{self.phone_number_id}/media",
                headers=self._headers(),
                data={"messaging_product": "whatsapp", "type": mime_type},
                files={"file": (filename, audio_bytes, mime_type)},
            )
            upload.raise_for_status()
            media_id = upload.json().get("id")
            if not media_id:
                raise RuntimeError("Meta did not return an uploaded media ID")
            response = await client.post(
                f"{self.base_url}/{self.phone_number_id}/messages",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": to_number,
                    "type": "audio",
                    "audio": {"id": media_id, "voice": True},
                },
            )
            response.raise_for_status()
            messages = response.json().get("messages", [])
            if not messages:
                raise RuntimeError("Meta did not return a WhatsApp message ID")
            return messages[0]["id"]

    async def send_voice_note_from_mp3(self, to_number: str, mp3_bytes: bytes) -> str:
        """Convert Adam TTS MP3 output and deliver it as a WhatsApp voice note."""
        ogg_bytes = mp3_to_ogg_opus(mp3_bytes)
        return await self.send_voice_note(to_number, ogg_bytes, filename="adam-reply.ogg", mime_type="audio/ogg")
