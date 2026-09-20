"""Shared fixtures for JARVIS test suite."""

import os
from pathlib import Path
from typing import Generator
import pytest
import yaml

from app.config import Settings, load_settings, reload_settings


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Ensure environment variables don't leak between tests."""
    jarvis_env_vars = [k for k in os.environ if k.startswith("JARVIS_")]
    saved_env = {k: os.environ[k] for k in jarvis_env_vars}

    for k in jarvis_env_vars:
        del os.environ[k]

    yield

    for k in jarvis_env_vars:
        if k in os.environ:
            del os.environ[k]
    for k, v in saved_env.items():
        os.environ[k] = v


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace directory structure."""
    data_dir = tmp_path / "data"
    logs_dir = data_dir / "logs"
    memory_dir = data_dir / "memory"
    documents_dir = data_dir / "documents"

    for d in (data_dir, logs_dir, memory_dir, documents_dir):
        d.mkdir(parents=True, exist_ok=True)

    config_data = {
        "system": {
            "name": "JARVIS-Test",
            "version": "0.1.0-test",
            "environment": "testing",
            "mode": "terminal",
            "debug": True,
        },
        "logging": {
            "level": "DEBUG",
            "format": "%(levelname)s: %(message)s",
            "console": False,
            "file_logging": True,
            "log_file": "data/logs/test.log",
        },
        "paths": {
            "data_dir": "data",
            "logs_dir": "data/logs",
            "memory_dir": "data/memory",
            "documents_dir": "data/documents",
        },
    }

    config_file = tmp_path / "config.yaml"
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f)

    return tmp_path
