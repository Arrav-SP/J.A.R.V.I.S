"""End-to-End Voice Pipeline for JARVIS.

Coordinates the complete voice lifecycle:
Microphone -> Wake Word -> VAD -> STT -> JARVIS Core -> TTS -> Speaker
with barge-in interruption and latency telemetry logging.
"""

from __future__ import annotations

from enum import Enum
import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional
import numpy as np

from app.voice.audio_manager import AudioFrame, BaseAudioManager, SoundDeviceAudioManager, VirtualAudioManager
from app.voice.interruption import InterruptionController
from app.voice.stt import BaseSTTProvider, TranscriptionResult, get_stt_provider
from app.voice.tts import BaseTTSProvider, get_tts_provider
from app.voice.vad import BaseVAD, EnergyVAD, VADSegmenter
from app.voice.wake_word import BaseWakeWordDetector, get_wake_word_detector

if TYPE_CHECKING:
    from app.config.settings import VoiceConfig
    from app.core.orchestrator import Orchestrator

logger = logging.getLogger("jarvis.voice.pipeline")


class PipelineState(str, Enum):
    """Lifecycle state of the voice pipeline."""

    IDLE = "idle"
    LISTENING_WAKE_WORD = "listening_wake_word"
    RECORDING_SPEECH = "recording_speech"
    TRANSCRIBING = "transcribing"
    PROCESSING_CORE = "processing_core"
    SPEAKING = "speaking"


class VoicePipeline:
    """Orchestrates microphone stream, wake-word, VAD, STT, LLM core, and TTS."""

    def __init__(
        self,
        config: VoiceConfig,
        orchestrator: Orchestrator,
        audio_manager: Optional[BaseAudioManager] = None,
        wake_word_detector: Optional[BaseWakeWordDetector] = None,
        vad: Optional[BaseVAD] = None,
        stt: Optional[BaseSTTProvider] = None,
        tts: Optional[BaseTTSProvider] = None,
    ) -> None:
        self.config = config
        self.orchestrator = orchestrator
        self.state = PipelineState.IDLE

        # Initialize audio manager
        if audio_manager is not None:
            self.audio_manager = audio_manager
        else:
            try:
                self.audio_manager = SoundDeviceAudioManager(
                    sample_rate=config.sample_rate,
                    channels=config.channels,
                    chunk_duration_ms=config.chunk_duration_ms,
                    input_device=config.audio.input_device,
                    output_device=config.audio.output_device,
                )
            except Exception as err:
                logger.warning("Could not initialize SoundDeviceAudioManager (%s). Falling back to virtual.", err)
                self.audio_manager = VirtualAudioManager(sample_rate=config.sample_rate)

        # Initialize wake-word detector
        self.wake_word_detector = wake_word_detector or get_wake_word_detector(
            provider=config.wake_word.provider,
            phrase=config.wake_word.phrase,
            threshold=config.wake_word.threshold,
        )

        # Initialize VAD and Segmenter
        self.vad = vad or EnergyVAD(threshold=config.vad.threshold)
        self.segmenter = VADSegmenter(
            vad=self.vad,
            sample_rate=config.sample_rate,
            silence_duration_ms=config.vad.silence_duration_ms,
        )

        # Lazy STT & TTS handles
        self._stt: Optional[BaseSTTProvider] = stt
        self._tts: Optional[BaseTTSProvider] = tts

        # Initialize Interruption controller
        self.interruption = InterruptionController(tts=self._tts, audio_manager=self.audio_manager)

        self._running = False
        self._lock = threading.Lock()
        self._turn_callback: Optional[Callable[[str, str], None]] = None
        self.last_telemetry: Dict[str, Any] = {}
        self._preroll_buffer: List[AudioFrame] = []

    @property
    def stt(self) -> BaseSTTProvider:
        """Lazy-loaded speech-to-text provider."""
        if self._stt is None:
            self._stt = get_stt_provider(
                provider=self.config.stt.provider,
                model=self.config.stt.model,
                device=self.config.stt.device,
                compute_type=self.config.stt.compute_type,
                initial_prompt=self.config.stt.initial_prompt,
                fallback_to_mock=self.config.stt.fallback_to_mock,
            )
        return self._stt

    @stt.setter
    def stt(self, value: BaseSTTProvider) -> None:
        self._stt = value

    @property
    def tts(self) -> BaseTTSProvider:
        """Lazy-loaded text-to-speech provider."""
        if self._tts is None:
            self._tts = get_tts_provider(
                provider=self.config.tts.provider,
                voice=self.config.tts.voice,
                speed=self.config.tts.speed,
                fallback_to_mock=self.config.tts.fallback_to_mock,
            )
            self.interruption.tts = self._tts
        return self._tts

    @tts.setter
    def tts(self, value: BaseTTSProvider) -> None:
        self._tts = value
        if self.interruption:
            self.interruption.tts = value

    def set_turn_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register callback for completed turns: callback(user_text, assistant_text)."""
        self._turn_callback = callback

    def start(self) -> None:
        """Start the background voice listening pipeline."""
        with self._lock:
            if self._running:
                return

            if self.config.mode == "text" or not self.config.enabled:
                logger.info("Voice pipeline is in '%s' mode (not capturing audio).", self.config.mode)
                self.state = PipelineState.IDLE
                return

            self._running = True
            if self.config.mode == "wake_word":
                self.state = PipelineState.LISTENING_WAKE_WORD
            elif self.config.mode == "push_to_talk":
                self.state = PipelineState.IDLE

            self.audio_manager.start_recording(self._on_audio_frame)
            logger.info("Voice pipeline started (mode=%s, state=%s).", self.config.mode, self.state.value)

    def stop(self) -> None:
        """Stop voice listening and abort active components."""
        with self._lock:
            self._running = False
            self.interruption.interrupt(reason="pipeline_shutdown")
            self.audio_manager.stop_recording()
            self.state = PipelineState.IDLE
            self._preroll_buffer.clear()
            logger.info("Voice pipeline stopped.")

    def trigger_push_to_talk(self) -> None:
        """Trigger a push-to-talk recording session."""
        with self._lock:
            logger.info("Push-to-talk session triggered.")
            self._running = True
            self.segmenter.reset()
            self.state = PipelineState.RECORDING_SPEECH
            # Pre-seed segmenter with recent audio frames so onset syllable is not lost
            for pf in self._preroll_buffer:
                self.segmenter.process_frame(pf)
            self._preroll_buffer.clear()
            if not self.audio_manager.is_recording():
                self.audio_manager.start_recording(self._on_audio_frame)

    def _on_audio_frame(self, frame: AudioFrame) -> None:
        """Process incoming audio frame through pipeline state machine."""
        if not self._running:
            return

        # Idle buffer: maintain rolling ~180ms buffer to prevent onset word clipping
        if self.state == PipelineState.IDLE:
            self._preroll_buffer.append(frame)
            if len(self._preroll_buffer) > 6:
                self._preroll_buffer.pop(0)
            return

        # Barge-in: if JARVIS is speaking and user starts talking, interrupt playback!
        if self.state == PipelineState.SPEAKING:
            vad_res = self.vad.process(frame)
            if vad_res.is_speech and vad_res.confidence > 0.6:
                logger.info("Barge-in detected during playback. Interrupting speaker.")
                self.interruption.interrupt(reason="user_barge_in")
                self.state = PipelineState.RECORDING_SPEECH
                self.segmenter.reset()
                self.segmenter.process_frame(frame)
            return

        if self.state == PipelineState.LISTENING_WAKE_WORD:
            res = self.wake_word_detector.process_frame(frame)
            if res.detected:
                logger.info("Wake word detected! Transitioning to speech recording.")
                self.state = PipelineState.RECORDING_SPEECH
                self.segmenter.reset()
            return

        if self.state == PipelineState.RECORDING_SPEECH:
            complete_utterance = self.segmenter.process_frame(frame)
            if complete_utterance is not None:
                # Dispatch transcription and turn processing in a background worker
                threading.Thread(
                    target=self._process_completed_utterance,
                    args=(complete_utterance,),
                    daemon=True,
                ).start()

    def _process_completed_utterance(self, audio_data: np.ndarray) -> None:
        """Process completed speech audio turn: STT -> Core -> TTS."""
        total_start = time.time()
        speech_duration_s = len(audio_data) / float(self.config.sample_rate)

        # 1. STT Phase
        self.state = PipelineState.TRANSCRIBING
        stt_start = time.time()
        try:
            transcription = self.stt.transcribe(audio_data, sample_rate=self.config.sample_rate)
            user_text = transcription.text.strip()
        except Exception as err:
            logger.error("STT error in voice pipeline: %s", err)
            user_text = ""
        stt_elapsed_ms = (time.time() - stt_start) * 1000.0

        if not user_text:
            logger.info("No speech recognized. Returning to listening.")
            self._return_to_listening()
            return

        logger.info("Voice Input: '%s'", user_text)

        # 2. JARVIS Core Phase
        self.state = PipelineState.PROCESSING_CORE
        core_start = time.time()
        try:
            assistant_text = self.orchestrator.process_message(user_text)
        except Exception as err:
            logger.error("Core processing error in voice pipeline: %s", err)
            assistant_text = "I encountered an internal error processing your request."
        core_elapsed_ms = (time.time() - core_start) * 1000.0

        logger.info("JARVIS Response: '%s'", assistant_text)

        # 3. TTS Phase
        self.state = PipelineState.SPEAKING
        tts_start = time.time()
        self.interruption.clear()
        try:
            self.tts.speak(assistant_text, blocking=True)
        except Exception as err:
            logger.error("TTS playback error in voice pipeline: %s", err)
        tts_elapsed_ms = (time.time() - tts_start) * 1000.0

        total_elapsed_ms = (time.time() - total_start) * 1000.0

        # Telemetry logging
        self.last_telemetry = {
            "speech_duration_s": speech_duration_s,
            "stt_latency_ms": stt_elapsed_ms,
            "llm_latency_ms": core_elapsed_ms,
            "tts_latency_ms": tts_elapsed_ms,
            "total_latency_ms": total_elapsed_ms,
            "interrupted": self.interruption.was_interrupted(),
        }
        logger.info(
            "Voice Turn Completed: [Speech: %.2fs | STT: %.1fms | LLM: %.1fms | TTS: %.1fms | Total: %.1fms]",
            speech_duration_s,
            stt_elapsed_ms,
            core_elapsed_ms,
            tts_elapsed_ms,
            total_elapsed_ms,
        )

        if self._turn_callback:
            try:
                self._turn_callback(user_text, assistant_text)
            except Exception as cb_err:
                logger.exception("Error in turn callback: %s", cb_err)

        self._return_to_listening()

    def _return_to_listening(self) -> None:
        """Transition pipeline state back to waiting for next input."""
        with self._lock:
            if not self._running:
                self.state = PipelineState.IDLE
                return

            if self.config.mode == "wake_word":
                self.wake_word_detector.reset()
                self.segmenter.reset()
                self.state = PipelineState.LISTENING_WAKE_WORD
            else:
                self.state = PipelineState.IDLE
                self._preroll_buffer.clear()
                # Maintain warm audio stream to eliminate hardware restart latency between turns

    def get_status(self) -> Dict[str, Any]:
        """Return a structured dictionary describing active voice pipeline status."""
        return {
            "enabled": self.config.enabled,
            "mode": self.config.mode,
            "state": self.state.value,
            "running": self._running,
            "sample_rate": self.config.sample_rate,
            "stt_provider": self.config.stt.provider,
            "tts_provider": self.config.tts.provider,
            "last_telemetry": self.last_telemetry,
        }
