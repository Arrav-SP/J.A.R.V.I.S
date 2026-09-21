"""Voice Activity Detection (VAD) for JARVIS.

Detects speech boundaries, start/end of utterances, and silence intervals
using lightweight energy analysis or neural VAD.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
import math
from typing import List, Optional
import numpy as np

from app.voice.audio_manager import AudioFrame

logger = logging.getLogger("jarvis.voice.vad")


@dataclass
class VADResult:
    """Outcome of a single audio chunk VAD assessment."""

    is_speech: bool
    confidence: float
    energy: float


class BaseVAD(ABC):
    """Abstract interface for Voice Activity Detection."""

    @abstractmethod
    def process(self, frame: AudioFrame) -> VADResult:
        """Evaluate whether the given audio frame contains active speech."""

    @abstractmethod
    def reset(self) -> None:
        """Reset internal speech state and background estimators."""


class EnergyVAD(BaseVAD):
    """Zero-dependency adaptive RMS energy and zero-crossing rate VAD.

    Tracks an adaptive background noise floor and classifies frames with
    energy significantly above ambient noise as speech.
    """

    def __init__(
        self,
        threshold: float = 0.02,
        adapt_rate: float = 0.05,
        min_noise_floor: float = 0.005,
    ) -> None:
        self.threshold = threshold
        self.adapt_rate = adapt_rate
        self.min_noise_floor = min_noise_floor
        self.noise_floor = min_noise_floor

    def calculate_rms(self, data: np.ndarray) -> float:
        """Calculate Root Mean Square (RMS) energy of the audio chunk."""
        if len(data) == 0:
            return 0.0
        # Compute mean square safely
        mean_sq = np.mean(np.square(data, dtype=np.float64))
        return float(np.sqrt(max(0.0, mean_sq)))

    def process(self, frame: AudioFrame) -> VADResult:
        rms = self.calculate_rms(frame.data)

        # Dynamic speech threshold
        speech_cutoff = self.noise_floor + self.threshold
        is_speech = rms > speech_cutoff

        # Adapt noise floor on quiet frames
        if not is_speech:
            self.noise_floor = (1.0 - self.adapt_rate) * self.noise_floor + self.adapt_rate * rms
            self.noise_floor = max(self.min_noise_floor, self.noise_floor)

        # Estimate confidence bounded in [0.0, 1.0]
        confidence = min(1.0, max(0.0, (rms - self.noise_floor) / max(0.01, self.threshold * 2)))

        return VADResult(is_speech=is_speech, confidence=confidence, energy=rms)

    def reset(self) -> None:
        self.noise_floor = self.min_noise_floor


class MockVAD(BaseVAD):
    """Mock VAD for deterministic testing."""

    def __init__(self, default_speech: bool = False) -> None:
        self.default_speech = default_speech
        self.forced_speech: Optional[bool] = None

    def set_speech(self, is_speech: bool) -> None:
        self.forced_speech = is_speech

    def process(self, frame: AudioFrame) -> VADResult:
        active = self.forced_speech if self.forced_speech is not None else self.default_speech
        return VADResult(is_speech=active, confidence=1.0 if active else 0.0, energy=0.1 if active else 0.0)

    def reset(self) -> None:
        self.forced_speech = None


class VADSegmenter:
    """Stateful utterance segmenter.

    Accumulates continuous audio frames, transitions from LISTENING -> RECORDING -> UTTERANCE_COMPLETE,
    and returns full speech audio segments when a sentence/query finishes.
    """

    def __init__(
        self,
        vad: BaseVAD,
        sample_rate: int = 16000,
        silence_duration_ms: int = 800,
        min_speech_duration_ms: int = 250,
        pre_speech_padding_ms: int = 200,
    ) -> None:
        self.vad = vad
        self.sample_rate = sample_rate
        self.silence_duration_ms = silence_duration_ms
        self.min_speech_duration_ms = min_speech_duration_ms
        self.pre_speech_padding_ms = pre_speech_padding_ms

        self._in_speech: bool = False
        self._speech_frames: List[np.ndarray] = []
        self._pre_buffer: List[np.ndarray] = []
        self._consecutive_silence_ms: float = 0.0
        self._speech_duration_ms: float = 0.0
        self.max_pre_buffer_frames = max(1, int(pre_speech_padding_ms / 30))

    def process_frame(self, frame: AudioFrame) -> Optional[np.ndarray]:
        """Process an audio frame.

        Returns complete audio array (float32) when speech finishes; otherwise None.
        """
        vad_res = self.vad.process(frame)
        frame_ms = frame.duration_seconds * 1000.0

        if vad_res.is_speech:
            if not self._in_speech:
                # Speech onset detected
                self._in_speech = True
                self._speech_frames = list(self._pre_buffer)
                self._speech_duration_ms = 0.0
                self._consecutive_silence_ms = 0.0
                logger.debug("VAD speech onset detected.")

            self._speech_frames.append(frame.data)
            self._speech_duration_ms += frame_ms
            self._consecutive_silence_ms = 0.0
        else:
            if self._in_speech:
                self._speech_frames.append(frame.data)
                self._consecutive_silence_ms += frame_ms

                # Check if silence duration met to finish utterance
                if self._consecutive_silence_ms >= self.silence_duration_ms:
                    self._in_speech = False
                    if self._speech_duration_ms >= self.min_speech_duration_ms:
                        utterance = np.concatenate(self._speech_frames)
                        logger.info(
                            "VAD utterance completed (duration=%.2fs, silence=%.2fs)",
                            len(utterance) / self.sample_rate,
                            self._consecutive_silence_ms / 1000.0,
                        )
                        self.reset()
                        return utterance
                    else:
                        logger.debug("Discarding short noise burst (%.2fms)", self._speech_duration_ms)
                        self.reset()
            else:
                # Maintain circular pre-speech ring buffer
                self._pre_buffer.append(frame.data)
                if len(self._pre_buffer) > self.max_pre_buffer_frames:
                    self._pre_buffer.pop(0)

        return None

    def is_in_speech(self) -> bool:
        """Check if currently in active speech capture."""
        return self._in_speech

    def reset(self) -> None:
        """Reset segmenter buffers and VAD state."""
        self._in_speech = False
        self._speech_frames.clear()
        self._pre_buffer.clear()
        self._consecutive_silence_ms = 0.0
        self._speech_duration_ms = 0.0
        self.vad.reset()
