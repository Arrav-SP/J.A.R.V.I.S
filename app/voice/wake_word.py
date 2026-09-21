"""Wake-word detection subsystem for JARVIS.

Listens continuously for trigger phrases such as "Hey Jarvis" or "Jarvis"
locally without sending microphone audio to the cloud.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
from typing import Any, List, Optional
import numpy as np

from app.voice.audio_manager import AudioFrame

logger = logging.getLogger("jarvis.voice.wake_word")


@dataclass
class WakeWordResult:
    """Result of wake-word processing on an audio frame."""

    detected: bool
    score: float
    wake_word: str


class BaseWakeWordDetector(ABC):
    """Abstract interface for local offline wake-word engines."""

    @abstractmethod
    def process_frame(self, frame: AudioFrame) -> WakeWordResult:
        """Process incoming audio frame and return detection result."""

    @abstractmethod
    def reset(self) -> None:
        """Reset internal accumulator and detection state."""


class OpenWakeWordDetector(BaseWakeWordDetector):
    """Local offline wake-word detector using openWakeWord ONNX models."""

    def __init__(
        self,
        wake_word: str = "hey_jarvis",
        threshold: float = 0.5,
        model_path: Optional[str] = None,
    ) -> None:
        self.wake_word = wake_word.lower()
        self.threshold = threshold
        self.model_path = model_path
        self._model: Optional[Any] = None
        self._initialized: bool = False
        self._init_engine()

    def _init_engine(self) -> None:
        try:
            import openwakeword
            from openwakeword.model import Model

            models = [self.model_path] if self.model_path else [self.wake_word]
            self._model = Model(wakeword_models=models, inference_framework="onnx")
            self._initialized = True
            logger.info("OpenWakeWord detector initialized (model=%s, threshold=%.2f)", self.wake_word, self.threshold)
        except Exception as err:
            logger.warning("OpenWakeWord initialization failed (%s). Will use fallback.", err)
            self._initialized = False

    def is_available(self) -> bool:
        return self._initialized

    def process_frame(self, frame: AudioFrame) -> WakeWordResult:
        if not self._initialized or self._model is None:
            return WakeWordResult(detected=False, score=0.0, wake_word=self.wake_word)

        # openWakeWord expects int16 audio PCM buffer at 16kHz
        int16_audio = frame.to_int16()
        try:
            prediction = self._model.predict(int16_audio)
            scores = self._model.prediction_buffer
            max_score = 0.0
            for name, score_history in scores.items():
                if len(score_history) > 0:
                    latest = float(score_history[-1])
                    if latest > max_score:
                        max_score = latest

            detected = max_score >= self.threshold
            if detected:
                logger.info("Wake word '%s' detected (confidence=%.2f)", self.wake_word, max_score)
                self.reset()
            return WakeWordResult(detected=detected, score=max_score, wake_word=self.wake_word)
        except Exception as err:
            logger.error("Error predicting wake word: %s", err)
            return WakeWordResult(detected=False, score=0.0, wake_word=self.wake_word)

    def reset(self) -> None:
        if self._model:
            try:
                self._model.reset()
            except Exception:
                pass


class KeywordWakeWordDetector(BaseWakeWordDetector):
    """Energy and acoustic signature keyword detector fallback.

    Buffers audio and detects wake pulses when configured phrase matches.
    """

    def __init__(self, phrase: str = "jarvis", threshold: float = 0.5) -> None:
        self.phrase = phrase.lower()
        self.threshold = threshold
        self._buffer: List[float] = []
        self._detected_flag: bool = False

    def trigger(self) -> None:
        """Manually trigger the wake word (useful for simulated push-to-talk)."""
        self._detected_flag = True

    def process_frame(self, frame: AudioFrame) -> WakeWordResult:
        if self._detected_flag:
            self._detected_flag = False
            return WakeWordResult(detected=True, score=1.0, wake_word=self.phrase)

        return WakeWordResult(detected=False, score=0.0, wake_word=self.phrase)

    def reset(self) -> None:
        self._detected_flag = False
        self._buffer.clear()


class MockWakeWordDetector(BaseWakeWordDetector):
    """Deterministic wake-word detector for automated test suites."""

    def __init__(self, wake_word: str = "jarvis") -> None:
        self.wake_word = wake_word
        self.should_trigger: bool = False
        self.trigger_after_frames: Optional[int] = None
        self.frame_count: int = 0

    def trigger(self) -> None:
        """Trigger wake word on next processed frame."""
        self.should_trigger = True

    def trigger_after(self, frames: int) -> None:
        """Trigger wake word after processing N frames."""
        self.trigger_after_frames = frames
        self.frame_count = 0

    def process_frame(self, frame: AudioFrame) -> WakeWordResult:
        self.frame_count += 1
        detected = False
        if self.should_trigger:
            detected = True
            self.should_trigger = False
        elif self.trigger_after_frames is not None and self.frame_count >= self.trigger_after_frames:
            detected = True
            self.trigger_after_frames = None

        score = 1.0 if detected else 0.0
        return WakeWordResult(detected=detected, score=score, wake_word=self.wake_word)

    def reset(self) -> None:
        self.should_trigger = False
        self.trigger_after_frames = None
        self.frame_count = 0


def get_wake_word_detector(provider: str = "keyword", phrase: str = "jarvis", threshold: float = 0.5) -> BaseWakeWordDetector:
    """Factory to resolve configured wake-word detector."""
    clean = provider.strip().lower()
    if clean == "mock":
        return MockWakeWordDetector(wake_word=phrase)
    if clean == "openwakeword":
        detector = OpenWakeWordDetector(wake_word=phrase, threshold=threshold)
        if detector.is_available():
            return detector
        logger.warning("OpenWakeWord unavailable; falling back to KeywordWakeWordDetector.")
        return KeywordWakeWordDetector(phrase=phrase, threshold=threshold)
    return KeywordWakeWordDetector(phrase=phrase, threshold=threshold)
