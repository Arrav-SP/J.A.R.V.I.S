"""Unit tests for InterruptionController and barge-in coordination."""

import numpy as np
import pytest

from app.voice.audio_manager import VirtualAudioManager
from app.voice.interruption import InterruptionController
from app.voice.tts import MockTTSProvider


def test_interruption_controller_halts_speech() -> None:
    """Verify InterruptionController stops active TTS and audio playback immediately."""
    tts = MockTTSProvider()
    audio_mgr = VirtualAudioManager()
    controller = InterruptionController(tts=tts, audio_manager=audio_mgr)

    # When idle, interrupt returns False
    assert controller.interrupt(reason="test") is False
    assert controller.was_interrupted() is False

    # Simulate speaking
    tts._is_speaking = True
    assert controller.interrupt(reason="barge_in") is True
    assert tts.is_speaking() is False
    assert controller.was_interrupted() is True

    # Clear flag
    controller.clear()
    assert controller.was_interrupted() is False


def test_interruption_controller_halts_audio_playback() -> None:
    """Verify InterruptionController halts audio manager playback."""
    tts = MockTTSProvider()
    audio_mgr = VirtualAudioManager()
    controller = InterruptionController(tts=tts, audio_manager=audio_mgr)

    # Simulate playing audio stream
    audio_mgr._is_playing = True
    assert controller.interrupt(reason="user_talking") is True
    assert audio_mgr.is_playing() is False
    assert controller.was_interrupted() is True
