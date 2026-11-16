import json
import os
import urllib.request


class VoiceEngine:
    """Generate speech using the ElevenLabs text-to-speech API."""

    def __init__(self):
        self.api_key = os.environ.get("ELEVENLABS_API_KEY")
        self.base_url = "https://api.elevenlabs.io/v1"

    def _require_api_key(self):
        if not self.api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is missing")

    def connect(self):
        """Return voices available to the configured ElevenLabs account."""
        self._require_api_key()
        request = urllib.request.Request(
            f"{self.base_url}/voices",
            headers={"xi-api-key": self.api_key},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def speak_bytes(self, text, voice_id, model_id="eleven_multilingual_v2"):
        """Return generated MP3 audio bytes without writing a local file."""
        self._require_api_key()
        if not text or not text.strip():
            raise ValueError("Text to synthesize cannot be empty")
        if not voice_id:
            raise ValueError("ELEVENLABS_VOICE_ID is missing")

        payload = {"text": text, "model_id": model_id}
        request = urllib.request.Request(
            f"{self.base_url}/text-to-speech/{voice_id}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.read()

    def speak(self, text, voice_id, output_path="adam_voice.mp3"):
        """Generate speech and save it as an MP3 file."""
        audio = self.speak_bytes(text, voice_id)
        with open(output_path, "wb") as audio_file:
            audio_file.write(audio)
        return output_path


adam_voice = VoiceEngine()


if __name__ == "__main__":
    print("ADAM Voice Engine loaded.")
    print("Configure ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID to generate speech.")
