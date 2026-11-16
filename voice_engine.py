import json
import os
import urllib.request


class VoiceEngine:
    """Generate speech using the ElevenLabs API."""

    def __init__(self):
        self.api_key = os.environ.get("ELEVENLABS_API_KEY")
        self.base_url = "https://api.elevenlabs.io/v1"

    def _build_request(self, endpoint, *, data=None, headers=None, method=None):
        request_headers = {"xi-api-key": self.api_key}
        if headers:
            request_headers.update(headers)

        return urllib.request.Request(
            f"{self.base_url}{endpoint}",
            data=data,
            headers=request_headers,
            method=method,
        )

    def _require_api_key(self):
        if not self.api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is missing")

    def connect(self):
        """Return the voices available to the configured ElevenLabs account."""
        self._require_api_key()
        request = self._build_request("/voices")

        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def speak(self, text, voice_id):
        """Generate an MP3 file for the supplied text and voice ID."""
        self._require_api_key()

        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
        }

        request = self._build_request(
            f"/text-to-speech/{voice_id}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=90) as response:
            audio = response.read()

        output_path = "adam_voice.mp3"
        with open(output_path, "wb") as audio_file:
            audio_file.write(audio)

        return f"تم إنشاء الصوت في {output_path}"


adam_voice = VoiceEngine()


if __name__ == "__main__":
    print("ADAM Voice Engine loaded.")
    print("Voice engine is ready.")
