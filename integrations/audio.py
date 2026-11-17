"""Audio format helpers for channel-specific voice delivery."""

import shutil
import subprocess


def mp3_to_ogg_opus(audio_bytes: bytes) -> bytes:
    """Convert generated MP3 speech to OGG/Opus for WhatsApp voice notes."""
    if not audio_bytes:
        raise ValueError("Audio payload cannot be empty")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for WhatsApp OGG/Opus voice-note conversion")
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-vn",
         "-c:a", "libopus", "-b:a", "32k", "-application", "voip", "-f", "ogg", "pipe:1"],
        input=audio_bytes, capture_output=True, check=False, timeout=45,
    )
    if result.returncode != 0 or not result.stdout:
        raise ValueError("Could not convert generated audio to OGG/Opus")
    return result.stdout
