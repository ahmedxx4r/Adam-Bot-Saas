from ai_brain import AIBrain
from config import settings
from voice_engine import VoiceEngine


class VoiceHandler:
    """Coordinate speech recognition, AI response generation, and speech output."""

    def __init__(self):
        self.brain = AIBrain()
        self.voice = VoiceEngine()

    def process_audio(self, audio_file, history=None):
        """Return transcript, text response, and synthesized MP3 bytes."""
        settings.validate_voice_settings()
        transcript = self.brain.transcribe(audio_file)
        if not transcript:
            raise ValueError("No speech was detected in the uploaded audio")

        reply_text = self.brain.reply(transcript, history=history)
        audio_bytes = self.voice.speak_bytes(
            reply_text,
            settings.elevenlabs_voice_id,
            model_id=settings.elevenlabs_model_id,
        )
        return {"transcript": transcript, "reply": reply_text, "audio": audio_bytes}
