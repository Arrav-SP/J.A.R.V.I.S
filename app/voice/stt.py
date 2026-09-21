"""Speech-to-Text (STT) abstraction and providers for JARVIS.

Transcribes recorded speech waveforms into clean text using local
Whisper models or deterministic mock engines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
import time
from typing import Any, List, Optional
import numpy as np

logger = logging.getLogger("jarvis.voice.stt")


class STTError(Exception):
    """Base exception for speech-to-text failures."""


class STTModelUnavailableError(STTError):
    """Raised when the specified STT model cannot be loaded."""


@dataclass
class TranscriptionResult:
    """Outcome of a speech-to-text transcription."""

    text: str
    confidence: float = 1.0
    language: str = "en"
    duration: float = 0.0
    transcription_time_ms: float = 0.0


class BaseSTTProvider(ABC):
    """Abstract interface for speech transcription providers."""

    @abstractmethod
    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> TranscriptionResult:
        """Transcribe an audio buffer into text."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the STT engine is loaded and operational."""


class FasterWhisperSTTProvider(BaseSTTProvider):
    """Local offline STT engine using faster-whisper (CTranslate2)."""

    def __init__(
        self,
        model_name: str = "tiny.en",
        device: str = "cpu",
        compute_type: str = "int8",
        download_root: Optional[str] = None,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.download_root = download_root
        self._model: Optional[Any] = None
        self._initialized: bool = False
        self._init_model()

    def _init_model(self) -> None:
        try:
            from faster_whisper import WhisperModel

            logger.info(
                "Loading FasterWhisper model '%s' (device=%s, compute=%s)...",
                self.model_name,
                self.device,
                self.compute_type,
            )
            start_t = time.time()
            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
                download_root=self.download_root,
            )
            self._initialized = True
            logger.info("FasterWhisper loaded in %.2f seconds.", time.time() - start_t)
        except Exception as err:
            logger.error("Failed to load FasterWhisper model: %s", err)
            self._initialized = False

    def is_available(self) -> bool:
        return self._initialized and self._model is not None

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> TranscriptionResult:
        if not self.is_available() or self._model is None:
            raise STTModelUnavailableError(
                f"FasterWhisper model '{self.model_name}' is not loaded or unavailable."
            )

        if len(audio_data) == 0:
            return TranscriptionResult(text="", confidence=0.0, duration=0.0)

        start_t = time.time()
        # faster-whisper accepts float32 16kHz audio directly
        float_data = audio_data.astype(np.float32)

        try:
            segments, info = self._model.transcribe(
                float_data,
                beam_size=5,
                language="en",
                condition_on_previous_text=False,
            )

            text_chunks: List[str] = []
            for segment in segments:
                text_chunks.append(segment.text.strip())

            full_text = " ".join(text_chunks).strip()
            elapsed_ms = (time.time() - start_t) * 1000.0

            logger.info(
                "STT transcribed %.2fs of audio in %.1fms: '%s'",
                len(audio_data) / sample_rate,
                elapsed_ms,
                full_text,
            )

            return TranscriptionResult(
                text=full_text,
                confidence=getattr(info, "transcription_probability", 1.0) or 1.0,
                language=getattr(info, "language", "en") or "en",
                duration=float(len(audio_data) / sample_rate),
                transcription_time_ms=elapsed_ms,
            )
        except Exception as err:
            logger.error("STT transcription error: %s", err)
            raise STTError(f"Transcription failed: {err}") from err


class MockSTTProvider(BaseSTTProvider):
    """Deterministic STT provider for unit tests and offline testing."""

    def __init__(self, default_response: str = "Explain recursion.") -> None:
        self.default_response = default_response
        self.responses_queue: List[str] = []
        self.call_count: int = 0

    def queue_transcription(self, text: str) -> None:
        """Queue a specific transcription for the next call."""
        self.responses_queue.append(text)

    def is_available(self) -> bool:
        return True

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> TranscriptionResult:
        self.call_count += 1
        text = self.responses_queue.pop(0) if self.responses_queue else self.default_response
        duration = float(len(audio_data) / sample_rate) if len(audio_data) > 0 else 1.0
        return TranscriptionResult(
            text=text,
            confidence=1.0,
            language="en",
            duration=duration,
            transcription_time_ms=5.0,
        )


def get_stt_provider(
    provider: str = "faster-whisper",
    model: str = "tiny.en",
    device: str = "cpu",
    compute_type: str = "int8",
    fallback_to_mock: bool = True,
) -> BaseSTTProvider:
    """Factory to instantiate the configured STT provider with graceful fallback."""
    clean = provider.strip().lower()
    if clean == "mock":
        return MockSTTProvider()

    if clean == "faster-whisper":
        try:
            stt = FasterWhisperSTTProvider(model_name=model, device=device, compute_type=compute_type)
            if stt.is_available():
                return stt
            if fallback_to_mock:
                logger.warning("FasterWhisper unavailable. Falling back to MockSTTProvider.")
                return MockSTTProvider()
            raise STTModelUnavailableError("FasterWhisper model failed to initialize.")
        except Exception as err:
            if fallback_to_mock:
                logger.warning("FasterWhisper error (%s). Falling back to MockSTTProvider.", err)
                return MockSTTProvider()
            raise

    raise ValueError(f"Unsupported STT provider: '{provider}'")
