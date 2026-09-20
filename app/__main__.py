"""Main entry point for running JARVIS via `python -m app`."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from app import __version__
from app.config import get_settings, reload_settings
from app.core import (
    ConfigurationError,
    get_banner,
    get_logger,
    get_shutdown_banner,
    get_status_text,
    setup_logging,
)


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments for JARVIS entry point."""
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="JARVIS — Cross-Platform Multimodal Personal AI",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Display JARVIS operational status and exit.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate configuration, paths, and environment without starting terminal REPL.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"JARVIS Core v{__version__}",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom config.yaml file.",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default=None,
        help="Override operational mode (e.g. terminal).",
    )
    return parser.parse_args(args)


def run_terminal_repl(mode: str) -> int:
    """Run the basic interactive terminal loop for Part 0."""
    print("JARVIS Core is ready in terminal mode.")
    print("Commands: 'status', 'help', 'clear', 'exit' / 'quit'\n")

    logger = get_logger("terminal")
    while True:
        try:
            prompt_input = input("JARVIS> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not prompt_input:
            continue

        cmd = prompt_input.lower()
        if cmd in {"exit", "quit"}:
            break
        elif cmd == "status":
            print(get_status_text(mode=mode, status="ready"))
        elif cmd == "help":
            print("JARVIS Terminal Mode (Part 0 — Project Foundation)")
            print("  status : Display current core system status")
            print("  help   : Show this help message")
            print("  clear  : Clear terminal screen")
            print("  exit   : Shut down JARVIS Core")
        elif cmd == "clear":
            print("\033[H\033[J", end="")
        else:
            print(f"[JARVIS Foundation] Received: '{prompt_input}'")
            print("Part 0 is active. Core brain & LLM reasoning will be connected in Part 1.")
            logger.debug("Terminal input received: %s", prompt_input)

    print(get_shutdown_banner())
    logger.info("JARVIS Core shut down cleanly.")
    return 0


def main(args: Optional[List[str]] = None) -> int:
    """Initialize system and start JARVIS."""
    parsed_args = parse_args(args)

    try:
        # Load and configure settings
        if parsed_args.config:
            settings = reload_settings(config_file=parsed_args.config)
        else:
            settings = get_settings()

        if parsed_args.mode:
            settings.system.mode = parsed_args.mode

        # Ensure filesystem directories exist
        settings.ensure_directories()

        mode = settings.system.mode

        # If --status requested, suppress console logging to ensure clean status output
        if parsed_args.status:
            status_logging = settings.logging.model_copy()
            status_logging.console = False
            setup_logging(status_logging, settings.paths.base_dir)
            logger = get_logger("core")
            logger.info("Status flag query executed.")
            print(get_status_text(mode=mode, status="ready"))
            return 0

        # Initialize full logging
        setup_logging(settings.logging, settings.paths.base_dir)
        logger = get_logger("core")
        logger.info(
            "JARVIS Core initialized (name=%s, version=%s, env=%s, mode=%s)",
            settings.system.name,
            settings.system.version,
            settings.system.environment,
            settings.system.mode,
        )

        if parsed_args.check:
            print(f"JARVIS configuration check passed. Base dir: {settings.paths.base_dir}")
            return 0

        # Output startup banner
        print(get_banner(mode=mode, status="ready"))

        # Run terminal REPL
        return run_terminal_repl(mode)

    except ConfigurationError as err:
        sys.stderr.write(f"Configuration error: {err}\n")
        return 1
    except Exception as err:
        sys.stderr.write(f"Fatal initialization error: {err}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
