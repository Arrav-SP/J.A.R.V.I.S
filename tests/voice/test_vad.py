"""Unit tests for Voice Activity Detection (VAD) and VADSegmenter."""

import numpy as np
import pytest

from app.voice.audio_manager import AudioFrame
from app.voice.vad import EnergyVAD, MockVAD, VADResult, VADSegmenter


def test_energy_vad_speech_detection() -> None:
    """Verify EnergyVAD distinguishes between silence and high-energy speech."""
    vad = EnergyVAD(threshold=0.02)

    # 1. Silence (amplitude 0.001)
    silence = np.ones(480, dtype=np.float32) * 0.001
    silence_frame = AudioFrame(silence)
    res_silence = vad.process(silence_frame)
    assert res_silence.is_speech is False
    assert res_silence.energy < 0.01

    # 2. Loud speech signal (amplitude 0.2)
    loud_speech = np.ones(480, dtype=np.float32) * 0.2
    speech_frame = AudioFrame(loud_speech)
    res_speech = vad.process(speech_frame)
    assert res_speech.is_speech is True
    assert res_speech.confidence > 0.5


def test_mock_vad() -> None:
    """Verify MockVAD provides deterministic forced speech states."""
    mock_vad = MockVAD(default_speech=False)
    frame = AudioFrame(np.zeros(480, dtype=np.float32))

    assert mock_vad.process(frame).is_speech is False

    mock_vad.set_speech(True)
    assert mock_vad.process(frame).is_speech is True

    mock_vad.reset()
    assert mock_vad.process(frame).is_speech is False


def test_vad_segmenter_utterance_assembly() -> None:
    """Verify VADSegmenter captures speech onset and emits utterance after silence."""
    mock_vad = MockVAD(default_speech=False)
    # 30ms frames at 16kHz = 480 samples per frame
    segmenter = VADSegmenter(
        vad=mock_vad,
        sample_rate=16000,
        silence_duration_ms=100,  # 3-4 frames of silence triggers utterance completion
        min_speech_duration_ms=50,
        pre_speech_padding_ms=60,
    )

    frame_chunk = np.ones(480, dtype=np.float32) * 0.1
    frame = AudioFrame(frame_chunk)

    # 1. Pre-speech silence frames
    assert segmenter.process_frame(frame) is None
    assert not segmenter.is_in_speech()

    # 2. Speech onset (3 frames of speech = 90ms)
    mock_vad.set_speech(True)
    for _ in range(3):
        assert segmenter.process_frame(frame) is None
        assert segmenter.is_in_speech()

    # 3. Post-speech silence (4 frames = 120ms > 100ms silence_duration_ms)
    mock_vad.set_speech(False)
    result = None
    for _ in range(4):
        res = segmenter.process_frame(frame)
        if res is not None:
            result = res
            break

    assert result is not None
    assert isinstance(result, np.ndarray)
    assert len(result) > 480 * 3
    assert not segmenter.is_in_speech()
