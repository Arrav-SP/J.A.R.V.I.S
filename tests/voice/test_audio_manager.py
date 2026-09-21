"""Unit tests for Audio Manager, AudioFrame, and device abstractions."""

import time
import numpy as np
import pytest

from app.voice.audio_manager import (
    AudioDeviceUnavailableError,
    AudioError,
    AudioFrame,
    AudioPlaybackError,
    SoundDeviceAudioManager,
    VirtualAudioManager,
)


def test_audio_frame_properties() -> None:
    """Verify AudioFrame duration, int16 conversion, and timestamp."""
    # 1 second of 16kHz sine wave
    t = np.linspace(0, 1.0, 16000, endpoint=False)
    data = 0.5 * np.sin(2 * np.pi * 440 * t)
    frame = AudioFrame(data, sample_rate=16000)

    assert frame.sample_rate == 16000
    assert frame.duration_seconds == 1.0
    assert frame.timestamp > 0.0

    # Int16 round trip
    int16_pcm = frame.to_int16()
    assert int16_pcm.dtype == np.int16
    assert len(int16_pcm) == 16000

    recovered_frame = AudioFrame.from_int16(int16_pcm, sample_rate=16000)
    assert np.allclose(frame.data, recovered_frame.data, atol=1e-3)


def test_virtual_audio_manager_lifecycle() -> None:
    """Verify VirtualAudioManager recording stream and simulated audio feeding."""
    audio_mgr = VirtualAudioManager(sample_rate=16000)
    received_frames = []

    def _on_frame(frame: AudioFrame) -> None:
        received_frames.append(frame)

    assert not audio_mgr.is_recording()
    audio_mgr.start_recording(_on_frame)
    assert audio_mgr.is_recording()

    # Feed 3 simulated chunks
    test_chunk = np.ones(480, dtype=np.float32) * 0.1
    audio_mgr.feed_audio(test_chunk)
    audio_mgr.feed_audio(test_chunk)
    audio_mgr.feed_audio(test_chunk)

    time.sleep(0.15)
    audio_mgr.stop_recording()
    assert not audio_mgr.is_recording()
    assert len(received_frames) == 3

    # Test playback recording
    audio_mgr.play(test_chunk, sample_rate=16000, blocking=True)
    assert len(audio_mgr.played_audio) == 1
    assert np.array_equal(audio_mgr.played_audio[0], test_chunk)

    audio_mgr.close()


def test_sounddevice_device_listing() -> None:
    """Verify list_devices() returns dictionary structure with inputs and outputs."""
    devices = SoundDeviceAudioManager.list_devices()
    assert "inputs" in devices
    assert "outputs" in devices
    assert isinstance(devices["inputs"], list)
    assert isinstance(devices["outputs"], list)


def test_audio_exception_hierarchy() -> None:
    """Verify audio exception inheritance."""
    assert issubclass(AudioDeviceUnavailableError, AudioError)
    assert issubclass(AudioPlaybackError, AudioError)
