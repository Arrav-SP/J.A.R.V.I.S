"""Unit tests for Speech-to-Text (STT) providers and abstraction."""

import numpy as np
import pytest

from app.voice.stt import (
    FasterWhisperSTTProvider,
    MockSTTProvider,
    STTError,
    STTModelUnavailableError,
    TranscriptionResult,
    get_stt_provider,
)


def test_transcription_result_dataclass() -> None:
    """Verify TranscriptionResult dataclass attributes."""
    res = TranscriptionResult(text="Hello world", confidence=0.95, duration=1.2)
    assert res.text == "Hello world"
    assert res.confidence == 0.95
    assert res.duration == 1.2
    assert res.language == "en"


def test_mock_stt_provider() -> None:
    """Verify MockSTTProvider returns default and queued transcriptions."""
    stt = MockSTTProvider(default_response="Explain recursion.")
    dummy_audio = np.zeros(16000, dtype=np.float32)

    res1 = stt.transcribe(dummy_audio)
    assert res1.text == "Explain recursion."
    assert res1.duration == 1.0

    stt.queue_transcription("Switch to coding mode.")
    res2 = stt.transcribe(dummy_audio)
    assert res2.text == "Switch to coding mode."

    # Back to default
    res3 = stt.transcribe(dummy_audio)
    assert res3.text == "Explain recursion."
    assert stt.call_count == 3


def test_get_stt_provider_factory() -> None:
    """Verify get_stt_provider() returns correct instances and handles fallbacks."""
    mock_stt = get_stt_provider(provider="mock")
    assert isinstance(mock_stt, MockSTTProvider)

    with pytest.raises(ValueError):
        get_stt_provider(provider="unsupported-engine", fallback_to_mock=False)
