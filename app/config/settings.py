"""Configuration management for JARVIS.

Handles configuration loading from YAML files, environment variables,
and default settings using Pydantic schemas.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
import yaml

from app.core.exceptions import ConfigurationError


class SystemConfig(BaseModel):
    """System-level configuration."""

    name: str = "JARVIS"
    version: str = "0.1.0"
    environment: str = Field(default="development", description="Environment: development, production, test")
    mode: str = Field(default="terminal", description="Default operational mode: terminal")
    debug: bool = False

    @field_validator("environment")
    @classmethod
    def validate_env(cls, v: str) -> str:
        valid_envs = {"development", "production", "test", "testing"}
        v_clean = v.strip().lower()
        if v_clean not in valid_envs:
            raise ValueError(f"Invalid environment '{v}'. Allowed: {', '.join(sorted(valid_envs))}")
        return v_clean


class LoggingConfig(BaseModel):
    """Logging subsystem configuration."""

    level: str = "INFO"
    format: str = "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
    console: bool = True
    file_logging: bool = True
    log_file: str = "data/logs/jarvis.log"
    max_bytes: int = 10_485_760  # 10 MB
    backup_count: int = 5

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.strip().upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level '{v}'. Allowed: {', '.join(sorted(valid_levels))}")
        return v_upper


class PathsConfig(BaseModel):
    """Filesystem path configurations."""

    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)
    data_dir: Path = Path("data")
    logs_dir: Path = Path("data/logs")
    memory_dir: Path = Path("data/memory")
    documents_dir: Path = Path("data/documents")

    def resolve_path(self, path: Path | str) -> Path:
        """Resolve a path relative to base_dir if it is not already absolute."""
        p = Path(path)
        if p.is_absolute():
            return p
        return (self.base_dir / p).resolve()

    @property
    def absolute_data_dir(self) -> Path:
        return self.resolve_path(self.data_dir)

    @property
    def absolute_logs_dir(self) -> Path:
        return self.resolve_path(self.logs_dir)

    @property
    def absolute_memory_dir(self) -> Path:
        return self.resolve_path(self.memory_dir)

    @property
    def absolute_documents_dir(self) -> Path:
        return self.resolve_path(self.documents_dir)

    def ensure_directories(self) -> None:
        """Ensure that all core data directories exist on disk."""
        for directory in (
            self.absolute_data_dir,
            self.absolute_logs_dir,
            self.absolute_memory_dir,
            self.absolute_documents_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


class ModelConfig(BaseModel):
    """LLM provider and model configuration."""

    provider: str = Field(default="mock", description="Model provider: mock, ollama")
    model_name: str = "llama3.2"
    base_url: str = "http://localhost:11434"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    timeout_seconds: float = Field(default=30.0, gt=0.0)
    max_context_messages: int = Field(default=20, gt=0)
    fallback_to_mock: bool = True

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        valid_providers = {"mock", "ollama"}
        v_clean = v.strip().lower()
        if v_clean not in valid_providers:
            raise ValueError(f"Invalid model provider '{v}'. Allowed: {', '.join(sorted(valid_providers))}")
        return v_clean


class PersonalityConfig(BaseModel):
    """Personality and behavioral configuration."""

    name: str = "JARVIS"
    mode: str = Field(default="normal", description="Operating mode: normal, coding, study, research, professional, emergency")
    humor: float = Field(default=0.6, ge=0.0, le=1.0)
    sarcasm: float = Field(default=0.4, ge=0.0, le=1.0)
    formality: float = Field(default=0.7, ge=0.0, le=1.0)
    warmth: float = Field(default=0.6, ge=0.0, le=1.0)
    verbosity: float = Field(default=0.4, ge=0.0, le=1.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    proactivity: float = Field(default=0.5, ge=0.0, le=1.0)
    preferred_address: str = "sir"
    response_style: str = "concise"

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        valid_modes = {"normal", "coding", "study", "research", "professional", "emergency"}
        v_clean = v.strip().lower()
        if v_clean not in valid_modes:
            raise ValueError(f"Invalid personality mode '{v}'. Allowed: {', '.join(sorted(valid_modes))}")
        return v_clean


class AudioDeviceConfig(BaseModel):
    """Audio input/output hardware device selection."""

    input_device: Optional[int | str] = None
    output_device: Optional[int | str] = None


class STTConfig(BaseModel):
    """Speech-to-text configuration."""

    provider: str = Field(default="faster-whisper", description="STT provider: 'faster-whisper' or 'mock'")
    model: str = Field(default="tiny.en", description="Whisper model: tiny.en, base.en, small.en, etc.")
    device: str = Field(default="cpu", description="Inference device: cpu, cuda, auto")
    compute_type: str = Field(default="int8", description="Quantization: int8, float16, float32")
    fallback_to_mock: bool = True


class TTSConfig(BaseModel):
    """Text-to-speech configuration."""

    provider: str = Field(default="sapi5", description="TTS provider: 'sapi5', 'edge-tts', or 'mock'")
    voice: str = Field(default="Microsoft David Desktop", description="Voice identifier or name")
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    fallback_to_mock: bool = True


class VADConfig(BaseModel):
    """Voice activity detection configuration."""

    enabled: bool = True
    provider: str = Field(default="energy", description="VAD provider: 'energy', 'silero', or 'mock'")
    threshold: float = Field(default=0.02, ge=0.0, le=1.0)
    silence_duration_ms: int = Field(default=800, ge=100, le=5000)


class WakeWordConfig(BaseModel):
    """Wake-word detection configuration."""

    provider: str = Field(default="keyword", description="Wake word engine: 'openwakeword', 'keyword', or 'mock'")
    phrase: str = Field(default="jarvis", description="Wake phrase")
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class VoiceConfig(BaseModel):
    """Voice subsystem configuration."""

    enabled: bool = False
    mode: str = Field(default="wake_word", description="Voice mode: text, push_to_talk, wake_word")
    sample_rate: int = Field(default=16000, description="Audio sample rate (Hz)")
    channels: int = Field(default=1, description="Number of audio channels (1=mono)")
    chunk_duration_ms: int = Field(default=30, description="Chunk size in milliseconds")
    audio: AudioDeviceConfig = Field(default_factory=AudioDeviceConfig)
    stt: STTConfig = Field(default_factory=STTConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    vad: VADConfig = Field(default_factory=VADConfig)
    wake_word: WakeWordConfig = Field(default_factory=WakeWordConfig)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        valid_modes = {"text", "push_to_talk", "wake_word"}
        clean = v.strip().lower()
        if clean not in valid_modes:
            raise ValueError(f"Invalid voice mode '{v}'. Allowed: {', '.join(sorted(valid_modes))}")
        return clean


class Settings(BaseModel):
    """Complete application settings."""

    system: SystemConfig = Field(default_factory=SystemConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    personality: PersonalityConfig = Field(default_factory=PersonalityConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)

    def ensure_directories(self) -> None:
        """Convenience method to ensure configured directories exist."""
        self.paths.ensure_directories()



# Singleton instance cache
_settings: Optional[Settings] = None


def load_settings(
    config_file: Optional[Path | str] = None,
    env_file: Optional[Path | str] = None,
    base_dir: Optional[Path | str] = None,
) -> Settings:
    """Load configuration from file, environment, and defaults.

    Order of precedence (highest to lowest):
    1. Environment variables
    2. .env file values
    3. config.yaml values
    4. Model default values
    """
    # 1. Determine base directory
    root_dir = Path(base_dir).resolve() if base_dir else Path(__file__).resolve().parent.parent.parent

    # 2. Load .env file
    if env_file:
        target_env_file = Path(env_file).resolve()
        if not target_env_file.exists():
            raise ConfigurationError(f"Specified environment file does not exist: {target_env_file}")
        load_dotenv(target_env_file, override=True)
    else:
        target_env_file = root_dir / ".env"
        if target_env_file.exists():
            load_dotenv(target_env_file, override=True)

    # 3. Load YAML configuration
    if config_file:
        target_config_file = Path(config_file).resolve()
        if not target_config_file.exists():
            raise ConfigurationError(f"Specified configuration file does not exist: {target_config_file}")
    else:
        target_config_file = root_dir / "config.yaml"

    raw_config: Dict[str, Any] = {}
    if target_config_file.exists():
        try:
            with open(target_config_file, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                if isinstance(content, dict):
                    raw_config = content
                elif content is not None:
                    raise ConfigurationError(f"Config file '{target_config_file}' must contain a YAML mapping.")
        except yaml.YAMLError as err:
            raise ConfigurationError(f"Failed to parse YAML config '{target_config_file}': {err}") from err
        except OSError as err:
            raise ConfigurationError(f"Error reading config file '{target_config_file}': {err}") from err

    # Extract sections
    system_data = raw_config.get("system", {})
    logging_data = raw_config.get("logging", {})
    paths_data = raw_config.get("paths", {})
    model_data = raw_config.get("model", {})
    personality_data = raw_config.get("personality", {})

    # Apply environment variable overrides
    if "JARVIS_ENV" in os.environ:
        system_data["environment"] = os.environ["JARVIS_ENV"]
    if "JARVIS_MODE" in os.environ:
        system_data["mode"] = os.environ["JARVIS_MODE"]
    if "JARVIS_DEBUG" in os.environ:
        debug_val = os.environ["JARVIS_DEBUG"].strip().lower()
        system_data["debug"] = debug_val in {"true", "1", "yes"}
    if "JARVIS_LOG_LEVEL" in os.environ:
        logging_data["level"] = os.environ["JARVIS_LOG_LEVEL"]

    if "JARVIS_MODEL_PROVIDER" in os.environ:
        model_data["provider"] = os.environ["JARVIS_MODEL_PROVIDER"]
    if "JARVIS_MODEL_NAME" in os.environ:
        model_data["model_name"] = os.environ["JARVIS_MODEL_NAME"]
    if "JARVIS_MODEL_BASE_URL" in os.environ:
        model_data["base_url"] = os.environ["JARVIS_MODEL_BASE_URL"]
    if "JARVIS_MODEL_TEMPERATURE" in os.environ:
        try:
            model_data["temperature"] = float(os.environ["JARVIS_MODEL_TEMPERATURE"])
        except ValueError as err:
            raise ConfigurationError(f"Invalid temperature in JARVIS_MODEL_TEMPERATURE: {err}") from err
    if "JARVIS_MODEL_FALLBACK" in os.environ:
        fallback_val = os.environ["JARVIS_MODEL_FALLBACK"].strip().lower()
        model_data["fallback_to_mock"] = fallback_val in {"true", "1", "yes"}

    # Personality environment overrides
    if "JARVIS_PERSONALITY_MODE" in os.environ:
        personality_data["mode"] = os.environ["JARVIS_PERSONALITY_MODE"]
    if "JARVIS_PERSONALITY_ADDRESS" in os.environ:
        personality_data["preferred_address"] = os.environ["JARVIS_PERSONALITY_ADDRESS"]
    if "JARVIS_PERSONALITY_STYLE" in os.environ:
        personality_data["response_style"] = os.environ["JARVIS_PERSONALITY_STYLE"]

    for trait in ["humor", "sarcasm", "formality", "warmth", "verbosity", "confidence", "proactivity"]:
        env_key = f"JARVIS_PERSONALITY_{trait.upper()}"
        if env_key in os.environ:
            try:
                personality_data[trait] = float(os.environ[env_key])
            except ValueError as err:
                raise ConfigurationError(f"Invalid float value in {env_key}: {err}") from err

    # Voice section
    voice_data = raw_config.get("voice", {})
    if not isinstance(voice_data, dict):
        voice_data = {}

    if "JARVIS_VOICE_ENABLED" in os.environ:
        voice_data["enabled"] = os.environ["JARVIS_VOICE_ENABLED"].strip().lower() in {"true", "1", "yes"}
    if "JARVIS_VOICE_MODE" in os.environ:
        voice_data["mode"] = os.environ["JARVIS_VOICE_MODE"]

    stt_data = voice_data.get("stt", {})
    if "JARVIS_VOICE_STT_PROVIDER" in os.environ:
        stt_data["provider"] = os.environ["JARVIS_VOICE_STT_PROVIDER"]
    if "JARVIS_VOICE_STT_MODEL" in os.environ:
        stt_data["model"] = os.environ["JARVIS_VOICE_STT_MODEL"]
    if "JARVIS_VOICE_STT_DEVICE" in os.environ:
        stt_data["device"] = os.environ["JARVIS_VOICE_STT_DEVICE"]
    voice_data["stt"] = stt_data

    tts_data = voice_data.get("tts", {})
    if "JARVIS_VOICE_TTS_PROVIDER" in os.environ:
        tts_data["provider"] = os.environ["JARVIS_VOICE_TTS_PROVIDER"]
    if "JARVIS_VOICE_TTS_VOICE" in os.environ:
        tts_data["voice"] = os.environ["JARVIS_VOICE_TTS_VOICE"]
    if "JARVIS_VOICE_TTS_SPEED" in os.environ:
        try:
            tts_data["speed"] = float(os.environ["JARVIS_VOICE_TTS_SPEED"])
        except ValueError as err:
            raise ConfigurationError(f"Invalid float in JARVIS_VOICE_TTS_SPEED: {err}") from err
    voice_data["tts"] = tts_data

    vad_data = voice_data.get("vad", {})
    if "JARVIS_VOICE_VAD_ENABLED" in os.environ:
        vad_data["enabled"] = os.environ["JARVIS_VOICE_VAD_ENABLED"].strip().lower() in {"true", "1", "yes"}
    if "JARVIS_VOICE_VAD_PROVIDER" in os.environ:
        vad_data["provider"] = os.environ["JARVIS_VOICE_VAD_PROVIDER"]
    voice_data["vad"] = vad_data

    wake_word_data = voice_data.get("wake_word", {})
    if "JARVIS_VOICE_WAKE_WORD_PROVIDER" in os.environ:
        wake_word_data["provider"] = os.environ["JARVIS_VOICE_WAKE_WORD_PROVIDER"]
    if "JARVIS_VOICE_WAKE_WORD_PHRASE" in os.environ:
        wake_word_data["phrase"] = os.environ["JARVIS_VOICE_WAKE_WORD_PHRASE"]
    voice_data["wake_word"] = wake_word_data

    paths_data["base_dir"] = root_dir

    # Instantiate and validate models
    try:
        system_cfg = SystemConfig(**system_data)
        logging_cfg = LoggingConfig(**logging_data)
        paths_cfg = PathsConfig(**paths_data)
        model_cfg = ModelConfig(**model_data)
        personality_cfg = PersonalityConfig(**personality_data)
        voice_cfg = VoiceConfig(**voice_data)
        settings_instance = Settings(
            system=system_cfg,
            logging=logging_cfg,
            paths=paths_cfg,
            model=model_cfg,
            personality=personality_cfg,
            voice=voice_cfg,
        )
    except Exception as err:
        raise ConfigurationError(f"Configuration validation error: {err}") from err

    return settings_instance


def get_settings() -> Settings:
    """Get the cached settings singleton, loading it if not already initialized."""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def reload_settings(
    config_file: Optional[Path | str] = None,
    env_file: Optional[Path | str] = None,
    base_dir: Optional[Path | str] = None,
) -> Settings:
    """Force reload the settings singleton with optional explicit paths."""
    global _settings
    _settings = load_settings(config_file=config_file, env_file=env_file, base_dir=base_dir)
    return _settings
