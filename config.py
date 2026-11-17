from dotenv import load_dotenv

load_dotenv()


import os


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.openai_chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        self.openai_stt_model = os.getenv("OPENAI_STT_MODEL", "whisper-1")
        self.elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "")
        self.elevenlabs_model_id = os.getenv(
            "ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"
        )
        self.system_prompt = os.getenv(
            "ADAM_SYSTEM_PROMPT",
            "You are Adam, a helpful, natural, concise AI voice assistant. "
            "Reply in the same language as the user unless asked otherwise.",
        )
        self.max_upload_bytes = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
        self.whatsapp_app_secret = os.getenv("WHATSAPP_APP_SECRET", "")
        self.whatsapp_verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
        self.whatsapp_access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        self.whatsapp_phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self.whatsapp_graph_api_version = os.getenv("WHATSAPP_GRAPH_API_VERSION", "v23.0")

    def validate_voice_settings(self):
        missing = [
            name
            for name, value in (
                ("OPENAI_API_KEY", self.openai_api_key),
                ("ELEVENLABS_API_KEY", self.elevenlabs_api_key),
                ("ELEVENLABS_VOICE_ID", self.elevenlabs_voice_id),
            )
            if not value
        ]
        if missing:
            raise RuntimeError("Missing required environment variables: " + ", ".join(missing))


settings = Settings()
