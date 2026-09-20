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


class Settings(BaseModel):
    """Complete application settings."""

    system: SystemConfig = Field(default_factory=SystemConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)

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

    paths_data["base_dir"] = root_dir

    # Instantiate and validate models
    try:
        system_cfg = SystemConfig(**system_data)
        logging_cfg = LoggingConfig(**logging_data)
        paths_cfg = PathsConfig(**paths_data)
        settings_instance = Settings(system=system_cfg, logging=logging_cfg, paths=paths_cfg)
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
