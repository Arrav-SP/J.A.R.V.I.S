import subprocess
import sys
import time
import numpy as np
import pytest

from app.config.settings import Settings, VoiceConfig
from app.core.orchestrator import Orchestrator
from app.voice.audio_manager import AudioFrame, VirtualAudioManager
from app.voice.pipeline import PipelineState, VoicePipeline
from app.voice.stt import MockSTTProvider
from app.voice.tts import MockTTSProvider
from app.voice.vad import MockVAD
from app.voice.wake_word import MockWakeWordDetector


def test_voice_pipeline_initialization() -> None:
    """Verify pipeline initializes with given components and status reflects config."""
    config = VoiceConfig(enabled=True, mode="wake_word")
    orchestrator = Orchestrator(settings=Settings())
    audio_mgr = VirtualAudioManager()
    wake_detector = MockWakeWordDetector()
    vad = MockVAD()
    stt = MockSTTProvider()
    tts = MockTTSProvider()

    pipeline = VoicePipeline(
        config=config,
        orchestrator=orchestrator,
        audio_manager=audio_mgr,
        wake_word_detector=wake_detector,
        vad=vad,
        stt=stt,
        tts=tts,
    )

    status = pipeline.get_status()
    assert status["enabled"] is True
    assert status["mode"] == "wake_word"
    assert status["running"] is False
    assert status["state"] == "idle"


def test_voice_pipeline_push_to_talk_turn() -> None:
    """Verify push-to-talk lifecycle: trigger -> speech -> STT -> Core -> TTS -> completion."""
    config = VoiceConfig(enabled=True, mode="push_to_talk")
    orchestrator = Orchestrator(settings=Settings())
    audio_mgr = VirtualAudioManager(sample_rate=16000)
    wake_detector = MockWakeWordDetector()
    vad = MockVAD()
    stt = MockSTTProvider(default_response="Explain recursion.")
    tts = MockTTSProvider()

    pipeline = VoicePipeline(
        config=config,
        orchestrator=orchestrator,
        audio_manager=audio_mgr,
        wake_word_detector=wake_detector,
        vad=vad,
        stt=stt,
        tts=tts,
    )

    # Use short silence duration for fast test execution
    pipeline.segmenter.silence_duration_ms = 60
    pipeline.segmenter.min_speech_duration_ms = 30

    completed_turns = []
    pipeline.set_turn_callback(lambda u, a: completed_turns.append((u, a)))

    pipeline.start()
    pipeline.trigger_push_to_talk()
    assert pipeline.state == PipelineState.RECORDING_SPEECH

    # Feed speech frames
    chunk = np.ones(480, dtype=np.float32) * 0.1
    vad.set_speech(True)
    audio_mgr.feed_audio(chunk)
    audio_mgr.feed_audio(chunk)

    # Feed silence frames to complete utterance
    time.sleep(0.05)
    vad.set_speech(False)
    audio_mgr.feed_audio(chunk)
    audio_mgr.feed_audio(chunk)
    audio_mgr.feed_audio(chunk)

    # Wait for background worker to complete turn
    time.sleep(0.3)

    assert len(completed_turns) == 1
    user_query, assistant_resp = completed_turns[0]
    assert user_query == "Explain recursion."
    assert "recursion" in assistant_resp.lower()
    assert len(tts.spoken_texts) >= 1

    # Verify telemetry
    assert "total_latency_ms" in pipeline.last_telemetry
    assert pipeline.last_telemetry["total_latency_ms"] > 0.0

    pipeline.stop()


def test_voice_pipeline_wake_word_trigger_turn() -> None:
    """Verify wake-word triggers speech recording and processes turn."""
    config = VoiceConfig(enabled=True, mode="wake_word")
    orchestrator = Orchestrator(settings=Settings())
    audio_mgr = VirtualAudioManager(sample_rate=16000)
    wake_detector = MockWakeWordDetector(wake_word="jarvis")
    vad = MockVAD()
    stt = MockSTTProvider(default_response="Switch to coding mode.")
    tts = MockTTSProvider()

    pipeline = VoicePipeline(
        config=config,
        orchestrator=orchestrator,
        audio_manager=audio_mgr,
        wake_word_detector=wake_detector,
        vad=vad,
        stt=stt,
        tts=tts,
    )

    pipeline.segmenter.silence_duration_ms = 60
    pipeline.segmenter.min_speech_duration_ms = 30

    pipeline.start()
    assert pipeline.state == PipelineState.LISTENING_WAKE_WORD

    # Trigger wake word
    wake_detector.trigger()
    chunk = np.ones(480, dtype=np.float32) * 0.1
    audio_mgr.feed_audio(chunk)

    time.sleep(0.05)
    assert pipeline.state == PipelineState.RECORDING_SPEECH

    # Feed speech
    vad.set_speech(True)
    audio_mgr.feed_audio(chunk)
    audio_mgr.feed_audio(chunk)

    # Feed silence
    time.sleep(0.05)
    vad.set_speech(False)
    audio_mgr.feed_audio(chunk)
    audio_mgr.feed_audio(chunk)
    audio_mgr.feed_audio(chunk)

    time.sleep(0.3)
    assert any("CODING" in text.upper() for text in tts.spoken_texts)
    pipeline.stop()


def test_voice_pipeline_barge_in_interruption() -> None:
    """Verify barge-in halts TTS playback when user speaks."""
    config = VoiceConfig(enabled=True, mode="wake_word")
    orchestrator = Orchestrator(settings=Settings())
    audio_mgr = VirtualAudioManager(sample_rate=16000)
    wake_detector = MockWakeWordDetector()
    vad = MockVAD()
    stt = MockSTTProvider()
    tts = MockTTSProvider()

    pipeline = VoicePipeline(
        config=config,
        orchestrator=orchestrator,
        audio_manager=audio_mgr,
        wake_word_detector=wake_detector,
        vad=vad,
        stt=stt,
        tts=tts,
    )

    pipeline.start()

    # Manually transition pipeline to SPEAKING state
    pipeline.state = PipelineState.SPEAKING
    tts._is_speaking = True

    # Feed audio frame with speech detected
    vad.set_speech(True)
    frame = AudioFrame(np.ones(480, dtype=np.float32) * 0.2)
    pipeline._on_audio_frame(frame)

    assert pipeline.interruption.was_interrupted() is True
    assert pipeline.state == PipelineState.RECORDING_SPEECH
    assert tts.is_speaking() is False

    pipeline.stop()


def test_voice_pipeline_push_to_talk_without_prior_start() -> None:
    """Verify trigger_push_to_talk activates pipeline even if start() was not called."""
    config = VoiceConfig(enabled=True, mode="push_to_talk")
    orchestrator = Orchestrator(settings=Settings())
    audio_mgr = VirtualAudioManager(sample_rate=16000)
    wake_detector = MockWakeWordDetector()
    vad = MockVAD()
    stt = MockSTTProvider()
    tts = MockTTSProvider()

    pipeline = VoicePipeline(
        config=config,
        orchestrator=orchestrator,
        audio_manager=audio_mgr,
        wake_word_detector=wake_detector,
        vad=vad,
        stt=stt,
        tts=tts,
    )

    assert pipeline._running is False
    pipeline.trigger_push_to_talk()
    assert pipeline._running is True
    assert pipeline.state == PipelineState.RECORDING_SPEECH
    assert audio_mgr.is_recording() is True

    pipeline.stop()
    assert pipeline._running is False
    assert audio_mgr.is_recording() is False


def test_subprocess_repl_voice_commands() -> None:
    """Verify REPL handles voice commands (status, switching modes) when initially disabled."""
    input_cmds = "voice\nvoice mode push_to_talk\nvoice mode text\nexit\n"
    result = subprocess.run(
        [sys.executable, "-m", "app"],
        input=input_cmds,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Voice subsystem is currently disabled" in result.stdout or "VOICE PIPELINE STATUS" in result.stdout
    assert "Voice mode switched to 'push_to_talk'" in result.stdout
    assert "Voice mode switched to 'text'" in result.stdout
    assert "JARVIS CORE OFFLINE" in result.stdout


