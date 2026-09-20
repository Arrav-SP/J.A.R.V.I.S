"""Unit tests for JARVIS logging subsystem."""

import logging
from pathlib import Path

from app.config.settings import LoggingConfig
from app.core.logger import get_logger, setup_logging


def test_setup_logging_creates_file(tmp_path: Path) -> None:
    """Verify setup_logging creates the specified log file and writes to it."""
    log_file = tmp_path / "test_logs" / "jarvis.log"
    config = LoggingConfig(
        level="DEBUG",
        format="%(levelname)s: %(message)s",
        console=False,
        file_logging=True,
        log_file=str(log_file),
    )

    logger = setup_logging(config=config, base_dir=tmp_path)
    test_msg = "Test diagnostic message"
    logger.debug(test_msg)

    # Flush handlers
    for handler in logger.handlers:
        handler.flush()

    assert log_file.is_file()
    content = log_file.read_text(encoding="utf-8")
    assert test_msg in content


def test_logger_hierarchy(tmp_path: Path) -> None:
    """Verify namespaced loggers correctly prepend 'jarvis.'."""
    config = LoggingConfig(level="INFO", console=False, file_logging=False)
    setup_logging(config=config, base_dir=tmp_path)

    core_logger = get_logger("core")
    assert core_logger.name == "jarvis.core"

    sub_logger = get_logger("jarvis.subsystem")
    assert sub_logger.name == "jarvis.subsystem"


def test_log_level_filtering(tmp_path: Path) -> None:
    """Verify messages below configured log level are not recorded."""
    log_file = tmp_path / "filter_test.log"
    config = LoggingConfig(
        level="WARNING",
        format="%(levelname)s: %(message)s",
        console=False,
        file_logging=True,
        log_file=str(log_file),
    )
    logger = setup_logging(config=config, base_dir=tmp_path)

    logger.debug("Debug message that should be ignored")
    logger.info("Info message that should be ignored")
    logger.warning("Warning message that should be recorded")

    for handler in logger.handlers:
        handler.flush()

    content = log_file.read_text(encoding="utf-8")
    assert "Debug message" not in content
    assert "Info message" not in content
    assert "Warning message that should be recorded" in content
