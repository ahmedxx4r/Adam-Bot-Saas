import asyncio

import pytest

from integrations.meta_whatsapp import MetaWhatsAppClient


def test_meta_adapter_requires_credentials():
    client = MetaWhatsAppClient(access_token="", phone_number_id="")
    with pytest.raises(RuntimeError):
        client._require_config()


def test_voice_note_requires_ogg_audio_before_network_call():
    client = MetaWhatsAppClient(access_token="test-token", phone_number_id="123")
    async def run():
        with pytest.raises(ValueError, match="OGG"):
            await client.send_voice_note("201000000000", b"fake-mp3", mime_type="audio/mpeg")
    asyncio.run(run())
