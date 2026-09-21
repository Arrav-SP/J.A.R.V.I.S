"""Barge-in and interruption management for the JARVIS Voice Subsystem.

Enables JARVIS to immediately halt speaking and return to listening
when user speech or an interruption signal is detected.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from app.voice.audio_manager import BaseAudioManager
from app.voice.tts import BaseTTSProvider

logger = logging.getLogger("jarvis.voice.interruption")


class InterruptionController:
    """Coordinates barge-in and speech cancellation across TTS and audio outputs."""

    def __init__(
        self,
        tts: Optional[BaseTTSProvider] = None,
        audio_manager: Optional[BaseAudioManager] = None,
    ) -> None:
        self.tts = tts
        self.audio_manager = audio_manager
        self._lock = threading.Lock()
        self._interrupted_event = threading.Event()

    def register_components(self, tts: BaseTTSProvider, audio_manager: BaseAudioManager) -> None:
        """Register the active TTS and audio manager components."""
        with self._lock:
            self.tts = tts
            self.audio_manager = audio_manager

    def interrupt(self, reason: str = "user_speech") -> bool:
        """Immediately stop all ongoing speech output.

        Returns True if active playback was interrupted, False if idle.
        """
        with self._lock:
            interrupted_any = False

            if self.tts and self.tts.is_speaking():
                logger.info("Interrupting active TTS output (reason=%s).", reason)
                self.tts.stop()
                interrupted_any = True

            if self.audio_manager and self.audio_manager.is_playing():
                logger.info("Interrupting active audio playback (reason=%s).", reason)
                self.audio_manager.stop_playback()
                interrupted_any = True

            if interrupted_any:
                self._interrupted_event.set()

            return interrupted_any

    def was_interrupted(self) -> bool:
        """Check if an interruption occurred since last clear."""
        return self._interrupted_event.is_set()

    def clear(self) -> None:
        """Reset the interruption flag."""
        self._interrupted_event.clear()
