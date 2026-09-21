"""Unit tests for Wake Word detection subsystem."""

import numpy as np
import pytest

from app.voice.audio_manager import AudioFrame
from app.voice.wake_word import (
    KeywordWakeWordDetector,
    MockWakeWordDetector,
    get_wake_word_detector,
)


def test_mock_wake_word_trigger() -> None:
    """Verify MockWakeWordDetector triggers on demand and frame delay."""
    detector = MockWakeWordDetector(wake_word="jarvis")
    frame = AudioFrame(np.zeros(480, dtype=np.float32))

    # Not triggered
    res = detector.process_frame(frame)
    assert res.detected is False

    # Manual trigger
    detector.trigger()
    res = detector.process_frame(frame)
    assert res.detected is True
    assert res.wake_word == "jarvis"

    # Reset
    detector.reset()
    res = detector.process_frame(frame)
    assert res.detected is False

    # Trigger after N frames
    detector.trigger_after(3)
    assert detector.process_frame(frame).detected is False
    assert detector.process_frame(frame).detected is False
    assert detector.process_frame(frame).detected is True


def test_keyword_wake_word_detector() -> None:
    """Verify KeywordWakeWordDetector manual trigger and reset."""
    detector = KeywordWakeWordDetector(phrase="hey jarvis")
    frame = AudioFrame(np.zeros(480, dtype=np.float32))

    assert detector.process_frame(frame).detected is False

    detector.trigger()
    assert detector.process_frame(frame).detected is True
    assert detector.process_frame(frame).detected is False


def test_get_wake_word_detector_factory() -> None:
    """Verify wake-word factory instantiates configured engines."""
    mock_det = get_wake_word_detector(provider="mock", phrase="jarvis")
    assert isinstance(mock_det, MockWakeWordDetector)

    keyword_det = get_wake_word_detector(provider="keyword", phrase="computer")
    assert isinstance(keyword_det, KeywordWakeWordDetector)
    assert keyword_det.phrase == "computer"
