import importlib
import os
import pathlib
import re


def test_env_example_contains_no_real_keys():
    """.env.example must never carry live-looking provider keys again."""
    content = pathlib.Path(".env.example").read_text()
    assert not re.search(r"sk-proj-[A-Za-z0-9_-]{20,}", content), "OpenAI key committed"
    assert not re.search(r"(?m)^ELEVENLABS_API_KEY=sk_[a-f0-9]{20,}$", content), "ElevenLabs key committed"
    assert "replace-with-your-openai-api-key" in content
    assert "replace-with-your-elevenlabs-api-key" in content


def test_openai_base_url_defaults_empty(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    import config
    importlib.reload(config)
    assert config.settings.openai_base_url == ""


def test_openai_base_url_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    import config
    importlib.reload(config)
    assert config.settings.openai_base_url == "https://example.invalid/v1"
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    importlib.reload(config)


def test_ai_brain_uses_base_url_only_when_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    import config
    import ai_brain

    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    importlib.reload(config)
    importlib.reload(ai_brain)
    monkeypatch.setattr(ai_brain, "OpenAI", FakeOpenAI)
    ai_brain.AIBrain()
    assert captured == {"api_key": "test-key"}

    captured.clear()
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    importlib.reload(config)
    importlib.reload(ai_brain)
    monkeypatch.setattr(ai_brain, "OpenAI", FakeOpenAI)
    ai_brain.AIBrain()
    assert captured["base_url"] == "https://example.invalid/v1"

    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    importlib.reload(config)
    importlib.reload(ai_brain)
