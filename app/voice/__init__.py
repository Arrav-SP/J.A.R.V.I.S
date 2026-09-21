"""Voice subsystem for JARVIS.

Provides hardware audio management, local speech recognition (Whisper),
Voice Activity Detection (VAD), Wake Word detection, Text-to-Speech (TTS),
barge-in interruption, and end-to-end voice pipeline orchestration.
"""

from app.voice.audio_manager import (
    AudioCaptureError,
    AudioDeviceUnavailableError,
    AudioError,
    AudioFrame,
    AudioPlaybackError,
    BaseAudioManager,
    SoundDeviceAudioManager,
    VirtualAudioManager,
)
from app.voice.interruption import InterruptionController
from app.voice.pipeline import PipelineState, VoicePipeline
from app.voice.stt import (
    BaseSTTProvider,
    FasterWhisperSTTProvider,
    MockSTTProvider,
    STTError,
    STTModelUnavailableError,
    TranscriptionResult,
    get_stt_provider,
)
from app.voice.tts import (
    BaseTTSProvider,
    MockTTSProvider,
    SynthesisResult,
    TTSError,
    WindowsSapiTTSProvider,
    get_tts_provider,
)
from app.voice.vad import BaseVAD, EnergyVAD, MockVAD, VADResult, VADSegmenter
from app.voice.wake_word import (
    BaseWakeWordDetector,
    KeywordWakeWordDetector,
    MockWakeWordDetector,
    OpenWakeWordDetector,
    WakeWordResult,
    get_wake_word_detector,
)

__all__ = [
    "AudioCaptureError",
    "AudioDeviceUnavailableError",
    "AudioError",
    "AudioFrame",
    "AudioPlaybackError",
    "BaseAudioManager",
    "BaseSTTProvider",
    "BaseTTSProvider",
    "BaseVAD",
    "BaseWakeWordDetector",
    "EnergyVAD",
    "FasterWhisperSTTProvider",
    "InterruptionController",
    "KeywordWakeWordDetector",
    "MockSTTProvider",
    "MockTTSProvider",
    "MockVAD",
    "MockWakeWordDetector",
    "OpenWakeWordDetector",
    "PipelineState",
    "STTError",
    "STTModelUnavailableError",
    "SoundDeviceAudioManager",
    "SynthesisResult",
    "TTSError",
    "TranscriptionResult",
    "VADResult",
    "VADSegmenter",
    "VirtualAudioManager",
    "VoicePipeline",
    "WindowsSapiTTSProvider",
    "WakeWordResult",
    "get_stt_provider",
    "get_tts_provider",
    "get_wake_word_detector",
]
