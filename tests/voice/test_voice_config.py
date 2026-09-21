"""Unit tests for JARVIS voice configuration loading and validation."""

import os
import pytest
from pydantic import ValidationError

from app.config.settings import Settings, VoiceConfig, load_settings


def test_default_voice_config() -> None:
    """Verify default voice configuration values."""
    cfg = VoiceConfig()
    assert cfg.enabled is False
    assert cfg.mode == "wake_word"
    assert cfg.sample_rate == 16000
    assert cfg.channels == 1
    assert cfg.chunk_duration_ms == 30
    assert cfg.stt.provider == "faster-whisper"
    assert cfg.stt.model == "tiny.en"
    assert cfg.tts.provider == "sapi5"
    assert cfg.tts.speed == 1.0
    assert cfg.vad.enabled is True
    assert cfg.wake_word.phrase == "jarvis"


def test_invalid_voice_mode_validation() -> None:
    """Verify invalid voice mode raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        VoiceConfig(mode="telepathic")
    assert "Invalid voice mode" in str(exc_info.value)


def test_voice_env_overrides(tmp_path: pytest.TempPathFactory) -> None:
    """Verify JARVIS_VOICE_* environment variables override config values."""
    env_vars = {
        "JARVIS_VOICE_ENABLED": "true",
        "JARVIS_VOICE_MODE": "push_to_talk",
        "JARVIS_VOICE_STT_PROVIDER": "mock",
        "JARVIS_VOICE_STT_MODEL": "base.en",
        "JARVIS_VOICE_TTS_PROVIDER": "mock",
        "JARVIS_VOICE_TTS_SPEED": "1.25",
        "JARVIS_VOICE_VAD_ENABLED": "false",
        "JARVIS_VOICE_WAKE_WORD_PHRASE": "computer",
    }

    old_env = os.environ.copy()
    try:
        os.environ.update(env_vars)
        settings = load_settings(base_dir=tmp_path)
        assert settings.voice.enabled is True
        assert settings.voice.mode == "push_to_talk"
        assert settings.voice.stt.provider == "mock"
        assert settings.voice.stt.model == "base.en"
        assert settings.voice.tts.provider == "mock"
        assert settings.voice.tts.speed == 1.25
        assert settings.voice.vad.enabled is False
        assert settings.voice.wake_word.phrase == "computer"
    finally:
        os.environ.clear()
        os.environ.update(old_env)
