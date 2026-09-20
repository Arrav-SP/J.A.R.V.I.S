"""Structured logging framework for JARVIS.

Provides uniform console and rotating file logging.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.config.settings import LoggingConfig

_is_logging_configured: bool = False


def setup_logging(
    config: Optional[LoggingConfig] = None,
    base_dir: Optional[Path] = None,
) -> logging.Logger:
    """Initialize and configure logging for the entire JARVIS system."""
    global _is_logging_configured

    if config is None:
        from app.config.settings import get_settings

        settings = get_settings()
        config = settings.logging
        if base_dir is None:
            base_dir = settings.paths.base_dir

    root_logger = logging.getLogger("jarvis")
    root_logger.setLevel(getattr(logging, config.level, logging.INFO))

    # Clear existing handlers to prevent log duplication
    root_logger.handlers.clear()

    formatter = logging.Formatter(config.format)

    # Console handler
    if config.console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.level, logging.INFO))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Rotating file handler
    if config.file_logging:
        log_path = Path(config.log_file)
        if not log_path.is_absolute() and base_dir is not None:
            log_path = (base_dir / log_path).resolve()

        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = RotatingFileHandler(
                filename=str(log_path),
                maxBytes=config.max_bytes,
                backupCount=config.backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(getattr(logging, config.level, logging.INFO))
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except OSError as err:
            from app.core.exceptions import InitializationError

            raise InitializationError(f"Failed to initialize file logger at '{log_path}': {err}") from err

    # Prevent propagation to Python default root logger
    root_logger.propagate = False
    _is_logging_configured = True

    return root_logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a namespaced logger within the JARVIS hierarchy.

    Example:
        get_logger("config") -> logger named "jarvis.config"
    """
    if not name or name == "jarvis":
        return logging.getLogger("jarvis")

    clean_name = name.removeprefix("jarvis.")
    return logging.getLogger(f"jarvis.{clean_name}")
