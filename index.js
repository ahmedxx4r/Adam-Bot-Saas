import os
import json
import urllib.request
import urllib.error

class VoiceEngine:
    def __init__(self):
        self.api_key = os.environ.get("ELEVENLABS_API_KEY")
        self.base_url = "https://api.elevenlabs.io/v1"

    def connect(self):
        if not self.api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is missing")

        req = urllib.request.Request(
            self.base_url + "/voices",
            headers={"xi-api-key": self.api_key}
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def speak(self, text, voice_id):
        if not self.api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is missing")

        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2"
        }

        req = urllib.request.Request(
            self.base_url + "/text-to-speech/" + voice_id,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=90) as response:
            audio = response.read()

        with open("adam_voice.mp3", "wb") as audio_file:
            audio_file.write(audio)

        return "تم إنشاء الصوت في adam_voice.mp3"


adam_voice = VoiceEngine()

if __name__ == "__main__":
    print("ADAM Voice Engine loaded.")
    print("Voice engine is ready.")