"""Audio input/output management for JARVIS.

Provides hardware device discovery, real-time microphone stream capture,
speaker playback, and deterministic virtual device simulation for testing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from queue import Empty, Queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import numpy as np

logger = logging.getLogger("jarvis.voice.audio")


class AudioError(Exception):
    """Base exception for all audio subsystem failures."""


class AudioDeviceUnavailableError(AudioError):
    """Raised when the specified or default audio hardware device cannot be accessed."""


class AudioPlaybackError(AudioError):
    """Raised when audio playback fails."""


class AudioCaptureError(AudioError):
    """Raised when microphone recording stream encounters an error."""


class AudioFrame:
    """Represents a chunk of PCM audio data."""

    def __init__(self, data: np.ndarray, sample_rate: int = 16000, timestamp: Optional[float] = None) -> None:
        self.data: np.ndarray = data.astype(np.float32)
        self.sample_rate: int = sample_rate
        self.timestamp: float = timestamp or time.time()

    @property
    def duration_seconds(self) -> float:
        """Return audio frame duration in seconds."""
        if len(self.data) == 0 or self.sample_rate == 0:
            return 0.0
        return len(self.data) / float(self.sample_rate)

    def to_int16(self) -> np.ndarray:
        """Convert float32 [-1.0, 1.0] audio to int16 PCM."""
        clamped = np.clip(self.data, -1.0, 1.0)
        return (clamped * 32767).astype(np.int16)

    @classmethod
    def from_int16(cls, int16_data: np.ndarray, sample_rate: int = 16000) -> AudioFrame:
        """Create an AudioFrame from int16 PCM."""
        float_data = int16_data.astype(np.float32) / 32768.0
        return cls(float_data, sample_rate=sample_rate)


class BaseAudioManager(ABC):
    """Abstract interface for audio recording and playback management."""

    @abstractmethod
    def start_recording(self, callback: Callable[[AudioFrame], None]) -> None:
        """Start capturing audio from the input device and forward frames to callback."""

    @abstractmethod
    def stop_recording(self) -> None:
        """Stop microphone capture."""

    @abstractmethod
    def is_recording(self) -> bool:
        """Check if microphone capture is active."""

    @abstractmethod
    def play(self, audio_data: np.ndarray, sample_rate: int = 16000, blocking: bool = False) -> None:
        """Play audio array through speaker output."""

    @abstractmethod
    def stop_playback(self) -> None:
        """Immediately stop and abort active speaker output."""

    @abstractmethod
    def is_playing(self) -> bool:
        """Check if speaker output is currently playing."""

    @abstractmethod
    def close(self) -> None:
        """Release underlying hardware streams and cleanup resources."""


class SoundDeviceAudioManager(BaseAudioManager):
    """Real audio device management using sounddevice and PortAudio."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_duration_ms: int = 30,
        input_device: Optional[int | str] = None,
        output_device: Optional[int | str] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = int(self.sample_rate * (chunk_duration_ms / 1000.0))
        self.input_device = input_device
        self.output_device = output_device

        self._stream: Optional[Any] = None
        self._callback: Optional[Callable[[AudioFrame], None]] = None
        self._is_recording: bool = False
        self._is_playing: bool = False
        self._lock = threading.Lock()

    @staticmethod
    def list_devices() -> Dict[str, List[Dict[str, Any]]]:
        """List available physical audio input and output devices."""
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            inputs = []
            outputs = []
            for i, dev in enumerate(devices):
                dev_info = {
                    "index": i,
                    "name": dev["name"],
                    "channels_in": dev["max_input_channels"],
                    "channels_out": dev["max_output_channels"],
                    "sample_rate": dev["default_samplerate"],
                }
                if dev["max_input_channels"] > 0:
                    inputs.append(dev_info)
                if dev["max_output_channels"] > 0:
                    outputs.append(dev_info)
            return {"inputs": inputs, "outputs": outputs}
        except Exception as err:
            logger.warning("Failed to query sound devices: %s", err)
            return {"inputs": [], "outputs": []}

    def start_recording(self, callback: Callable[[AudioFrame], None]) -> None:
        """Open audio input stream and begin streaming chunks."""
        with self._lock:
            if self._is_recording:
                return

            try:
                import sounddevice as sd

                self._callback = callback

                def _sd_callback(indata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
                    if status:
                        logger.debug("SoundDevice stream status: %s", status)
                    if self._callback and self._is_recording:
                        # Extract single channel if multichannel
                        mono_data = indata[:, 0] if indata.ndim > 1 else indata
                        frame = AudioFrame(mono_data.copy(), sample_rate=self.sample_rate)
                        try:
                            self._callback(frame)
                        except Exception as cb_err:
                            logger.exception("Error in audio stream callback: %s", cb_err)

                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype="float32",
                    blocksize=self.chunk_size,
                    device=self.input_device,
                    callback=_sd_callback,
                )
                self._stream.start()
                self._is_recording = True
                logger.info("Microphone stream started (rate=%d, chunk=%d)", self.sample_rate, self.chunk_size)
            except Exception as err:
                self._is_recording = False
                logger.error("Failed to start microphone stream: %s", err)
                raise AudioDeviceUnavailableError(f"Could not open microphone stream: {err}") from err

    def stop_recording(self) -> None:
        """Stop input stream and release stream handle."""
        with self._lock:
            if not self._is_recording:
                return
            self._is_recording = False
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as err:
                    logger.warning("Error closing input stream: %s", err)
                finally:
                    self._stream = None
            logger.info("Microphone stream stopped.")

    def is_recording(self) -> bool:
        return self._is_recording

    def play(self, audio_data: np.ndarray, sample_rate: int = 16000, blocking: bool = False) -> None:
        """Play PCM audio through speaker output."""
        try:
            import sounddevice as sd

            float_data = audio_data.astype(np.float32)
            self._is_playing = True
            sd.play(float_data, samplerate=sample_rate, device=self.output_device)
            if blocking:
                sd.wait()
                self._is_playing = False
        except Exception as err:
            self._is_playing = False
            logger.error("Audio playback failed: %s", err)
            raise AudioPlaybackError(f"Playback failed on output device: {err}") from err

    def stop_playback(self) -> None:
        """Stop any playing audio immediately."""
        try:
            import sounddevice as sd

            sd.stop()
            self._is_playing = False
            logger.debug("Playback stopped.")
        except Exception as err:
            logger.warning("Error stopping playback: %s", err)

    def is_playing(self) -> bool:
        return self._is_playing

    def close(self) -> None:
        self.stop_recording()
        self.stop_playback()


class VirtualAudioManager(BaseAudioManager):
    """In-memory virtual audio manager for headless tests and simulated audio inputs."""

    def __init__(self, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self._is_recording: bool = False
        self._is_playing: bool = False
        self._callback: Optional[Callable[[AudioFrame], None]] = None
        self.played_audio: List[np.ndarray] = []
        self._input_queue: Queue[AudioFrame] = Queue()
        self._feed_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start_recording(self, callback: Callable[[AudioFrame], None]) -> None:
        self._callback = callback
        self._is_recording = True
        self._stop_event.clear()

        def _worker() -> None:
            while not self._stop_event.is_set():
                try:
                    frame = self._input_queue.get(timeout=0.05)
                    if self._callback and self._is_recording:
                        self._callback(frame)
                except Empty:
                    continue

        self._feed_thread = threading.Thread(target=_worker, daemon=True)
        self._feed_thread.start()
        logger.debug("Virtual audio manager recording started.")

    def feed_audio(self, audio_data: np.ndarray) -> None:
        """Feed simulated audio data into the virtual recording queue."""
        frame = AudioFrame(audio_data, sample_rate=self.sample_rate)
        self._input_queue.put(frame)

    def stop_recording(self) -> None:
        self._is_recording = False
        self._stop_event.set()
        if self._feed_thread and self._feed_thread.is_alive():
            self._feed_thread.join(timeout=0.5)
        logger.debug("Virtual audio manager recording stopped.")

    def is_recording(self) -> bool:
        return self._is_recording

    def play(self, audio_data: np.ndarray, sample_rate: int = 16000, blocking: bool = False) -> None:
        self._is_playing = True
        self.played_audio.append(audio_data.copy())
        if blocking:
            time.sleep(0.01)
            self._is_playing = False

    def stop_playback(self) -> None:
        self._is_playing = False

    def is_playing(self) -> bool:
        return self._is_playing

    def close(self) -> None:
        self.stop_recording()
        self.stop_playback()
