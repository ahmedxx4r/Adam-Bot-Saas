from openai import OpenAI

from config import settings


class AIBrain:
    """Transcribe user audio and generate Adam's text responses."""

    def __init__(self):
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is missing")
        client_kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        self.client = OpenAI(**client_kwargs)

    def transcribe(self, audio_file):
        """Convert an uploaded audio file into text."""
        audio_file.seek(0)
        result = self.client.audio.transcriptions.create(
            model=settings.openai_stt_model,
            file=audio_file,
        )
        return result.text.strip()

    def reply(self, user_text, history=None):
        """Generate a response, optionally using recent conversation messages."""
        messages = [{"role": "system", "content": settings.system_prompt}]
        if history:
            messages.extend(history[-12:])
        messages.append({"role": "user", "content": user_text})

        result = self.client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=messages,
            temperature=0.7,
        )
        return result.choices[0].message.content.strip()
