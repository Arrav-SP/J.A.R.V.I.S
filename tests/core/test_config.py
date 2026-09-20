"""Unit tests for JARVIS configuration subsystem."""

from pathlib import Path
import pytest
from pydantic import ValidationError

from app.config import (
    LoggingConfig,
    PathsConfig,
    Settings,
    SystemConfig,
    load_settings,
)
from app.core.exceptions import ConfigurationError


def test_default_settings(clean_env: None) -> None:
    """Verify default settings instantiation."""
    settings = Settings()
    assert settings.system.name == "JARVIS"
    assert settings.system.environment == "development"
    assert settings.system.mode == "terminal"
    assert settings.system.debug is False
    assert settings.logging.level == "INFO"
    assert settings.logging.console is True


def test_load_settings_from_workspace(temp_workspace: Path, clean_env: None) -> None:
    """Verify loading from config.yaml in workspace."""
    settings = load_settings(base_dir=temp_workspace)
    assert settings.system.name == "JARVIS-Test"
    assert settings.system.environment == "testing"
    assert settings.system.debug is True
    assert settings.logging.level == "DEBUG"
    assert settings.paths.base_dir == temp_workspace


def test_env_overrides(temp_workspace: Path, monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    """Verify environment variables override file configuration."""
    monkeypatch.setenv("JARVIS_ENV", "production")
    monkeypatch.setenv("JARVIS_MODE", "terminal")
    monkeypatch.setenv("JARVIS_DEBUG", "false")
    monkeypatch.setenv("JARVIS_LOG_LEVEL", "WARNING")

    settings = load_settings(base_dir=temp_workspace)
    assert settings.system.environment == "production"
    assert settings.system.mode == "terminal"
    assert settings.system.debug is False
    assert settings.logging.level == "WARNING"


def test_invalid_environment_direct_validation() -> None:
    """Verify invalid environment string raises ValidationError on model creation."""
    with pytest.raises(ValidationError) as exc_info:
        SystemConfig(environment="invalid_environment")
    assert "Invalid environment" in str(exc_info.value)


def test_invalid_log_level_direct_validation() -> None:
    """Verify invalid log level string raises ValidationError on model creation."""
    with pytest.raises(ValidationError) as exc_info:
        LoggingConfig(level="VERBOSE")
    assert "Invalid log level" in str(exc_info.value)


def test_invalid_environment_in_load_settings(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    """Verify invalid environment variable causes load_settings to raise ConfigurationError."""
    monkeypatch.setenv("JARVIS_ENV", "invalid_environment")
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings()
    assert "Invalid environment" in str(exc_info.value)


def test_invalid_log_level_in_load_settings(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    """Verify invalid log level variable causes load_settings to raise ConfigurationError."""
    monkeypatch.setenv("JARVIS_LOG_LEVEL", "VERBOSE")
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings()
    assert "Invalid log level" in str(exc_info.value)


def test_invalid_yaml_file(tmp_path: Path) -> None:
    """Verify malformed YAML raises ConfigurationError."""
    bad_config = tmp_path / "config.yaml"
    bad_config.write_text("system: [unclosed list", encoding="utf-8")

    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(config_file=bad_config, base_dir=tmp_path)
    assert "Failed to parse YAML" in str(exc_info.value)


def test_paths_ensure_directories(tmp_path: Path) -> None:
    """Verify ensure_directories creates missing folders."""
    paths_cfg = PathsConfig(
        base_dir=tmp_path,
        data_dir=Path("custom_data"),
        logs_dir=Path("custom_data/logs"),
        memory_dir=Path("custom_data/memory"),
        documents_dir=Path("custom_data/documents"),
    )
    paths_cfg.ensure_directories()
    assert (tmp_path / "custom_data").is_dir()
    assert (tmp_path / "custom_data" / "logs").is_dir()
    assert (tmp_path / "custom_data" / "memory").is_dir()
    assert (tmp_path / "custom_data" / "documents").is_dir()


def test_specified_config_not_found(tmp_path: Path) -> None:
    """Verify specifying a non-existent config file raises ConfigurationError."""
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(config_file=missing)
    assert "Specified configuration file does not exist" in str(exc_info.value)


def test_specified_env_not_found(tmp_path: Path) -> None:
    """Verify specifying a non-existent env file raises ConfigurationError."""
    missing = tmp_path / "does_not_exist.env"
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(env_file=missing)
    assert "Specified environment file does not exist" in str(exc_info.value)

