"""Text-to-Speech (TTS) subsystem for JARVIS.

Supports offline Windows SAPI5 speech synthesis, voice selection, speaking speed,
and instantaneous barge-in interruption.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
import re
import threading
import time
from typing import Any, List, Optional
import numpy as np

logger = logging.getLogger("jarvis.voice.tts")


class TTSError(Exception):
    """Base exception for text-to-speech failures."""


@dataclass
class SynthesisResult:
    """Outcome of audio waveform synthesis from text."""

    audio_data: np.ndarray
    sample_rate: int = 16000
    duration: float = 0.0
    synthesis_time_ms: float = 0.0


class BaseTTSProvider(ABC):
    """Abstract interface for speech synthesis providers."""

    @abstractmethod
    def speak(self, text: str, blocking: bool = True) -> None:
        """Synthesize and play speech directly through speaker."""

    @abstractmethod
    def synthesize(self, text: str) -> SynthesisResult:
        """Synthesize text into raw audio array."""

    @abstractmethod
    def stop(self) -> None:
        """Immediately stop and abort active speech."""

    @abstractmethod
    def is_speaking(self) -> bool:
        """Check if speech is currently outputting."""

    @abstractmethod
    def list_voices(self) -> List[str]:
        """Return list of available voice identifiers."""


# Phonetic replacements for words/proper nouns that US English SAPI voices mispronounce
_SAPI_PRONUNCIATION_OVERRIDES = {
    r"\bAarav\b": "Ah-rav",
    r"\bArav\b": "Ah-rav",
}


def _clean_text_for_sapi(text: str) -> str:
    """Format and strip markdown symbols, tables, and emojis for natural SAPI speech."""
    t = text
    # Remove code blocks
    t = re.sub(r"```[\s\S]*?```", " [code block omitted] ", t)
    t = re.sub(r"`[^`\n]*`", "", t)
    # Remove markdown table dividers like |---|---|
    t = re.sub(r"\|[-:\s|]+\|", "", t)
    # Replace table column separators with pauses
    t = t.replace("|", ", ")
    # Remove markdown headers and emphasis
    t = re.sub(r"#{1,6}\s*", "", t)
    t = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", t)
    t = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", t)
    # Remove bullet points and quote markers
    t = re.sub(r"^\s*[-*+>]\s*", "", t, flags=re.MULTILINE)
    # Strip emojis and astral unicode symbols
    t = re.sub(r"[\U00010000-\U0010ffff]", "", t)
    # Normalize special unicode spaces, quotes, dashes, and symbols
    t = (
        t.replace("\u202f", " ")
        .replace("\u00a0", " ")
        .replace("≈", "approximately ")
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("—", ", ")
        .replace("–", "-")
    )
    # Apply phonetic overrides for proper nouns
    for pattern, replacement in _SAPI_PRONUNCIATION_OVERRIDES.items():
        t = re.sub(pattern, replacement, t, flags=re.IGNORECASE)
    # Collapse multiple whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


class WindowsSapiTTSProvider(BaseTTSProvider):
    """Native offline Windows SAPI5 speech synthesizer via COM."""

    def __init__(self, voice_name: Optional[str] = None, speed: float = 1.0) -> None:
        self.voice_name = voice_name
        self.speed = speed
        self._is_speaking = False
        self._lock = threading.Lock()
        self._active_thread: Optional[threading.Thread] = None

    def _get_speaker(self) -> Any:
        """Create a thread-local or fresh SAPI SpVoice instance."""
        import win32com.client
        import pythoncom

        pythoncom.CoInitialize()
        speaker = win32com.client.Dispatch("SAPI.SpVoice")

        # Map speed [0.5, 2.0] to SAPI Rate [-10, 10]
        # 1.0 -> 0, 0.5 -> -5, 2.0 -> 10
        rate = int((self.speed - 1.0) * 10)
        speaker.Rate = max(-10, min(10, rate))

        # Select voice if specified
        if self.voice_name:
            voices = speaker.GetVoices()
            for i in range(voices.Count):
                v = voices.Item(i)
                if self.voice_name.lower() in v.GetDescription().lower():
                    speaker.Voice = v
                    break

        return speaker

    def list_voices(self) -> List[str]:
        try:
            import win32com.client
            import pythoncom

            pythoncom.CoInitialize()
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            voices = speaker.GetVoices()
            return [voices.Item(i).GetDescription() for i in range(voices.Count)]
        except Exception as err:
            logger.warning("Failed to list SAPI voices: %s", err)
            return []

    def speak(self, text: str, blocking: bool = True) -> None:
        clean_text = text.strip()
        if not clean_text:
            return

        spoken_text = _clean_text_for_sapi(clean_text)
        if not spoken_text:
            return

        def _speak_worker() -> None:
            self._is_speaking = True
            try:
                import pythoncom

                speaker = self._get_speaker()
                # 0 = SVSFDefault (synchronous inside this worker thread)
                speaker.Speak(spoken_text, 0)
            except Exception as err:
                logger.error("SAPI speak error: %s", err)
            finally:
                self._is_speaking = False

        if blocking:
            _speak_worker()
        else:
            self._active_thread = threading.Thread(target=_speak_worker, daemon=True)
            self._active_thread.start()

    def synthesize(self, text: str) -> SynthesisResult:
        """Synthesize text into Audio array (uses duration approximation for SAPI)."""
        start_t = time.time()
        words = len(text.split())
        approx_seconds = max(0.5, words / (2.5 * self.speed))
        # Generates a silent placeholder waveform of corresponding duration
        samples = int(16000 * approx_seconds)
        audio = np.zeros(samples, dtype=np.float32)
        elapsed_ms = (time.time() - start_t) * 1000.0

        return SynthesisResult(
            audio_data=audio,
            sample_rate=16000,
            duration=approx_seconds,
            synthesis_time_ms=elapsed_ms,
        )

    def stop(self) -> None:
        """Interrupt and purge speech output immediately."""
        if not self._is_speaking:
            return

        try:
            import win32com.client
            import pythoncom

            pythoncom.CoInitialize()
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            # Flag 2 = SVSFPurgeBeforeSpeak with empty string cancels immediately
            speaker.Speak("", 2)
            logger.debug("SAPI speech output purged.")
        except Exception:
            pass
        finally:
            self._is_speaking = False

    def is_speaking(self) -> bool:
        return self._is_speaking


class MockTTSProvider(BaseTTSProvider):
    """Deterministic TTS provider for automated unit tests."""

    def __init__(self, voice_name: str = "Mock Voice", speed: float = 1.0) -> None:
        self.voice_name = voice_name
        self.speed = speed
        self._is_speaking = False
        self.spoken_texts: List[str] = []
        self.call_count = 0

    def list_voices(self) -> List[str]:
        return ["Mock Voice (British)", "Mock Voice (Default)"]

    def speak(self, text: str, blocking: bool = True) -> None:
        self.call_count += 1
        self.spoken_texts.append(text)
        self._is_speaking = True
        if blocking:
            time.sleep(0.005)
            self._is_speaking = False

    def synthesize(self, text: str) -> SynthesisResult:
        self.spoken_texts.append(text)
        # 0.1 second sine wave for test verification
        t = np.linspace(0, 0.1, int(16000 * 0.1), endpoint=False)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        return SynthesisResult(
            audio_data=audio,
            sample_rate=16000,
            duration=0.1,
            synthesis_time_ms=1.0,
        )

    def stop(self) -> None:
        self._is_speaking = False

    def is_speaking(self) -> bool:
        return self._is_speaking


def get_tts_provider(
    provider: str = "sapi5",
    voice: Optional[str] = None,
    speed: float = 1.0,
    fallback_to_mock: bool = True,
) -> BaseTTSProvider:
    """Factory to instantiate the configured TTS provider with fallback."""
    clean = provider.strip().lower()
    if clean == "mock":
        return MockTTSProvider(voice_name=voice or "Mock Voice", speed=speed)

    if clean == "sapi5":
        try:
            return WindowsSapiTTSProvider(voice_name=voice, speed=speed)
        except Exception as err:
            if fallback_to_mock:
                logger.warning("SAPI5 initialization failed (%s). Falling back to MockTTSProvider.", err)
                return MockTTSProvider(voice_name=voice or "Mock Voice", speed=speed)
            raise TTSError(f"SAPI5 unavailable: {err}") from err

    raise ValueError(f"Unsupported TTS provider: '{provider}'")
