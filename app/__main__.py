"""Main entry point for running JARVIS via `python -m app`."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from app import __version__
from app.config import get_settings, reload_settings
from app.core import (
    ConfigurationError,
    Orchestrator,
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


def run_terminal_repl(mode: str, orchestrator: Orchestrator) -> int:
    """Run the interactive terminal conversation loop."""
    print("JARVIS Core is ready in terminal mode.")
    print("Commands: 'status', 'personality', 'mode <name>', 'reset', 'help', 'clear', 'exit' / 'quit'\n")

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
        elif cmd in {"reset", "new"}:
            orchestrator.reset_session()
            print("Conversation session reset, sir.\n")
        elif cmd in {"personality", "persona"}:
            status = orchestrator.get_personality_status()
            traits = status["traits"]
            print("\n" + "=" * 50)
            print(f"JARVIS PERSONALITY PROFILE")
            print(f"Active Mode       : {status['mode_name'].upper()}")
            print(f"Description       : {status['mode_description']}")
            print(f"Preferred Address : {traits['preferred_address']}")
            print(f"Humor: {int(traits['humor']*100)}% | Sarcasm: {int(traits['sarcasm']*100)}% | Formality: {int(traits['formality']*100)}%")
            print(f"Warmth: {int(traits['warmth']*100)}% | Verbosity: {int(traits['verbosity']*100)}% | Confidence: {int(traits['confidence']*100)}%")
            print("=" * 50 + "\n")
        elif cmd.startswith("mode ") or ("switch to " in cmd and " mode" in cmd):
            if cmd.startswith("mode "):
                target_mode = cmd.removeprefix("mode ").strip()
            else:
                target_mode = cmd.split("switch to ")[1].split(" mode")[0].strip()
            try:
                result_msg = orchestrator.set_mode(target_mode)
                print(f"[JARVIS] {result_msg}\n")
            except ValueError as err:
                print(f"[JARVIS Error] {err}\n")
        elif cmd.startswith("trait "):
            parts = prompt_input.split()
            if len(parts) == 3:
                trait_name, trait_val = parts[1], parts[2]
                try:
                    val_float = float(trait_val)
                    result_msg = orchestrator.set_trait(trait_name, val_float)
                    print(f"[JARVIS] {result_msg}\n")
                except ValueError as err:
                    print(f"[JARVIS Error] Invalid trait value: {err}\n")
            else:
                print("Usage: trait <name> <value (0.0 - 1.0)>\n")
        elif cmd == "help":
            print("JARVIS Terminal Mode Commands:")
            print("  status                   : Display current core system status")
            print("  personality              : Display active personality profile and traits")
            print("  mode <name>              : Switch operating mode (normal, coding, study, research, professional, emergency)")
            print("  trait <name> <0.0-1.0>   : Adjust a personality trait (e.g. trait humor 0.8)")
            print("  reset                    : Reset the current conversation history")
            print("  clear                    : Clear terminal screen")
            print("  help                     : Show this help message")
            print("  exit / quit              : Shut down JARVIS Core\n")
        elif cmd == "clear":
            print("\033[H\033[J", end="")
        else:
            response = orchestrator.process_message(prompt_input)
            print(f"\nJARVIS: {response}\n")
            logger.debug("Dialogue turn completed.")

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
            "JARVIS Core initialized (name=%s, version=%s, env=%s, mode=%s, model_provider=%s)",
            settings.system.name,
            settings.system.version,
            settings.system.environment,
            settings.system.mode,
            settings.model.provider,
        )

        if parsed_args.check:
            print(f"JARVIS configuration check passed. Base dir: {settings.paths.base_dir}")
            return 0

        # Output startup banner
        print(get_banner(mode=mode, status="ready"))

        # Initialize Orchestrator
        orchestrator = Orchestrator(settings=settings)

        # Run terminal conversation REPL
        return run_terminal_repl(mode, orchestrator)

    except ConfigurationError as err:
        sys.stderr.write(f"Configuration error: {err}\n")
        return 1
    except Exception as err:
        sys.stderr.write(f"Fatal initialization error: {err}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
