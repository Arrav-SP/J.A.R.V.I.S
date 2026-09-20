"""Unit and integration tests for JARVIS startup, banner, and CLI entry points."""

import subprocess
import sys
from pathlib import Path
import pytest

from app.__main__ import main, parse_args
from app.core.banner import get_banner, get_shutdown_banner, get_status_text


def test_status_text_format() -> None:
    """Verify status text strictly adheres to Part 0 completion requirements."""
    expected = "JARVIS CORE ONLINE\nMode: terminal\nStatus: ready"
    assert get_status_text(mode="terminal", status="ready") == expected


def test_banner_content() -> None:
    """Verify startup and shutdown banners."""
    banner = get_banner(mode="terminal", status="ready")
    assert "JARVIS CORE ONLINE" in banner
    assert "Mode: terminal" in banner
    assert "Status: ready" in banner

    shutdown = get_shutdown_banner()
    assert "JARVIS CORE OFFLINE" in shutdown


def test_cli_parse_args() -> None:
    """Verify CLI argument parsing."""
    args = parse_args(["--status"])
    assert args.status is True
    assert args.check is False

    args2 = parse_args(["--mode", "custom", "--check"])
    assert args2.mode == "custom"
    assert args2.check is True


def test_main_status_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify main(["--status"]) prints required status block and returns 0."""
    exit_code = main(["--status"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "JARVIS CORE ONLINE\nMode: terminal\nStatus: ready" in captured.out


def test_main_check_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify main(["--check"]) passes validation without errors."""
    exit_code = main(["--check"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "JARVIS configuration check passed" in captured.out


def test_subprocess_python_m_app_status() -> None:
    """Verify executing `python -m app --status` as an external process."""
    result = subprocess.run(
        [sys.executable, "-m", "app", "--status"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "JARVIS CORE ONLINE\nMode: terminal\nStatus: ready" in result.stdout.strip()


def test_subprocess_main_py_status() -> None:
    """Verify executing `python main.py --status` as an external process."""
    result = subprocess.run(
        [sys.executable, "main.py", "--status"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "JARVIS CORE ONLINE\nMode: terminal\nStatus: ready" in result.stdout.strip()


def test_subprocess_repl_exit_flow() -> None:
    """Verify typing 'status' and 'exit' in interactive terminal shuts down cleanly."""
    input_cmds = "status\nexit\n"
    result = subprocess.run(
        [sys.executable, "-m", "app"],
        input=input_cmds,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "JARVIS CORE ONLINE" in result.stdout
    assert "JARVIS CORE OFFLINE" in result.stdout
