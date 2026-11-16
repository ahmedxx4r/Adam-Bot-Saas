from ai_brain import AIBrain
from config import settings
from voice_engine import VoiceEngine


class VoiceHandler:
    """Coordinate transcription, AI responses, and speech synthesis."""

    def __init__(self):
        self.brain = AIBrain()
        self.voice = VoiceEngine()

    def process_text(self, user_text, history=None):
        """Generate an AI text response and its spoken MP3 version."""
        settings.validate_voice_settings()
        clean_text = (user_text or "").strip()
        if not clean_text:
            raise ValueError("Message cannot be empty")

        reply_text = self.brain.reply(clean_text, history=history)
        audio_bytes = self.voice.speak_bytes(
            reply_text,
            settings.elevenlabs_voice_id,
            model_id=settings.elevenlabs_model_id,
        )
        return {"transcript": clean_text, "reply": reply_text, "audio": audio_bytes}

    def process_audio(self, audio_file, history=None):
        """Transcribe audio, generate a reply, and synthesize the reply as MP3."""
        settings.validate_voice_settings()
        transcript = self.brain.transcribe(audio_file)
        if not transcript:
            raise ValueError("No speech was detected in the uploaded audio")
        return self.process_text(transcript, history=history)
