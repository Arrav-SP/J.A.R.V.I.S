"""Unit tests for Text-to-Speech (TTS) providers."""

import numpy as np
import pytest

from app.voice.tts import (
    MockTTSProvider,
    SynthesisResult,
    TTSError,
    WindowsSapiTTSProvider,
    get_tts_provider,
)


def test_mock_tts_provider() -> None:
    """Verify MockTTSProvider tracks spoken phrases and produces test waveforms."""
    tts = MockTTSProvider(voice_name="JARVIS", speed=1.1)

    tts.speak("Good morning, sir.", blocking=True)
    assert tts.spoken_texts == ["Good morning, sir."]
    assert tts.call_count == 1
    assert tts.is_speaking() is False

    # Synthesize audio waveform
    synth_res = tts.synthesize("Synthesize this.")
    assert isinstance(synth_res, SynthesisResult)
    assert isinstance(synth_res.audio_data, np.ndarray)
    assert synth_res.duration > 0.0

    tts.stop()
    assert tts.is_speaking() is False


def test_get_tts_provider_factory() -> None:
    """Verify get_tts_provider factory returns correct instance."""
    mock_tts = get_tts_provider(provider="mock")
    assert isinstance(mock_tts, MockTTSProvider)

    sapi_tts = get_tts_provider(provider="sapi5", fallback_to_mock=True)
    assert isinstance(sapi_tts, (WindowsSapiTTSProvider, MockTTSProvider))

    with pytest.raises(ValueError):
        get_tts_provider(provider="invalid-tts-engine", fallback_to_mock=False)
