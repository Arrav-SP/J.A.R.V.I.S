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
    parser.add_argument(
        "--voice",
        action="store_true",
        help="Enable the JARVIS voice subsystem.",
    )
    parser.add_argument(
        "--voice-mode",
        type=str,
        choices=["text", "push_to_talk", "wake_word"],
        default=None,
        help="Set voice operational mode (text, push_to_talk, wake_word).",
    )
    parser.add_argument(
        "--groq-key",
        "--api-key",
        dest="groq_key",
        type=str,
        default=None,
        help="Groq Cloud API key for cloud LLM intelligence.",
    )
    return parser.parse_args(args)


def run_terminal_repl(mode: str, orchestrator: Orchestrator, voice_pipeline: Optional[Any] = None) -> int:
    """Run the interactive terminal conversation loop."""
    print("JARVIS Core is ready in terminal mode.")
    print("Commands: 'status', 'personality', 'voice', 'listen', 'mode <name>', 'reset', 'help', 'clear', 'exit' / 'quit'\n")

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
        elif cmd == "voice" or cmd.startswith("voice "):
            if cmd == "voice":
                if not voice_pipeline:
                    print("[JARVIS] Voice subsystem is currently disabled in configuration.\n")
                else:
                    v_stat = voice_pipeline.get_status()
                    print("\n" + "=" * 50)
                    print("JARVIS VOICE PIPELINE STATUS")
                    print(f"Enabled      : {v_stat['enabled']}")
                    print(f"Mode         : {v_stat['mode']}")
                    print(f"State        : {v_stat['state']}")
                    print(f"STT Provider : {v_stat['stt_provider']}")
                    print(f"TTS Provider : {v_stat['tts_provider']}")
                    if v_stat.get("last_telemetry"):
                        telem = v_stat["last_telemetry"]
                        print(f"Last Turn    : Speech={telem.get('speech_duration_s', 0):.2f}s | STT={telem.get('stt_latency_ms', 0):.1f}ms | LLM={telem.get('llm_latency_ms', 0):.1f}ms | Total={telem.get('total_latency_ms', 0):.1f}ms")
                    print("=" * 50 + "\n")
            elif cmd == "voice on":
                if not voice_pipeline:
                    try:
                        from app.voice import VoicePipeline

                        settings = orchestrator.settings
                        settings.voice.enabled = True
                        voice_pipeline = VoicePipeline(config=settings.voice, orchestrator=orchestrator)
                    except Exception as err:
                        print(f"[JARVIS Error] Could not initialize voice pipeline: {err}\n")
                        continue
                voice_pipeline.config.enabled = True
                voice_pipeline.start()
                print(f"[JARVIS] Voice pipeline enabled in '{voice_pipeline.config.mode}' mode.\n")
            elif cmd == "voice off":
                if voice_pipeline:
                    voice_pipeline.stop()
                    voice_pipeline.config.enabled = False
                print("[JARVIS] Voice pipeline disabled.\n")
            elif cmd.startswith("voice mode "):
                new_vmode = cmd.removeprefix("voice mode ").strip()
                if new_vmode in {"text", "push_to_talk", "wake_word"}:
                    if not voice_pipeline:
                        try:
                            from app.voice import VoicePipeline

                            settings = orchestrator.settings
                            settings.voice.enabled = (new_vmode != "text")
                            settings.voice.mode = new_vmode
                            voice_pipeline = VoicePipeline(config=settings.voice, orchestrator=orchestrator)
                        except Exception as err:
                            print(f"[JARVIS Error] Could not initialize voice pipeline: {err}\n")
                            continue
                    else:
                        voice_pipeline.stop()
                        voice_pipeline.config.mode = new_vmode
                        if new_vmode != "text":
                            voice_pipeline.config.enabled = True
                            voice_pipeline.start()
                        else:
                            voice_pipeline.config.enabled = False
                    print(f"[JARVIS] Voice mode switched to '{new_vmode}'.\n")
                else:
                    print(f"[JARVIS Error] Invalid voice mode '{new_vmode}'. Allowed: text, push_to_talk, wake_word\n")
        elif cmd == "listen":
            if voice_pipeline and voice_pipeline.config.enabled:
                print("[JARVIS] Listening... (speak now)\n")
                voice_pipeline.trigger_push_to_talk()
            else:
                print("[JARVIS] Voice pipeline is not active. Enable with 'voice on' or run with --voice.\n")
        elif cmd.startswith("key ") or cmd.startswith("groq "):
            parts = prompt_input.split(maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                new_key = parts[1].strip()
                orchestrator.settings.model.api_key = new_key
                from app.core.model import get_model_provider
                orchestrator.llm_provider = get_model_provider(orchestrator.settings.model)

                # Persist to .env automatically
                try:
                    from pathlib import Path
                    env_p = Path(".env")
                    lines = env_p.read_text(encoding="utf-8").splitlines() if env_p.exists() else []
                    new_lines = []
                    key_replaced = False
                    for line in lines:
                        if line.startswith("GROQ_API_KEY="):
                            new_lines.append(f"GROQ_API_KEY={new_key}")
                            key_replaced = True
                        else:
                            new_lines.append(line)
                    if not key_replaced:
                        new_lines.append(f"GROQ_API_KEY={new_key}")
                    env_p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                except Exception as save_err:
                    logger.warning("Could not persist GROQ_API_KEY to .env: %s", save_err)

                print(f"[JARVIS] Cloud API key activated ({new_key[:8]}...) and saved to .env!\n")
            else:
                print("Usage: key <your_groq_api_key>\n")
        elif cmd == "help":
            print("JARVIS Terminal Mode Commands:")
            print("  status                   : Display current core system status")
            print("  personality              : Display active personality profile and traits")
            print("  voice                    : Show voice pipeline status and telemetry")
            print("  voice on / off           : Enable or disable voice capture")
            print("  voice mode <mode>        : Switch voice mode (text, push_to_talk, wake_word)")
            print("  listen                   : Trigger a push-to-talk voice recording turn")
            print("  key <api_key>            : Set Groq Cloud API key and activate online mode")
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

    if voice_pipeline:
        voice_pipeline.stop()

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

        if parsed_args.voice:
            settings.voice.enabled = True

        if parsed_args.voice_mode:
            settings.voice.mode = parsed_args.voice_mode
            if parsed_args.voice_mode != "text":
                settings.voice.enabled = True

        if parsed_args.groq_key:
            settings.model.api_key = parsed_args.groq_key

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
            voice_status_str = f"Voice: {'enabled' if settings.voice.enabled else 'disabled'} (mode={settings.voice.mode}, stt={settings.voice.stt.provider}, tts={settings.voice.tts.provider})"
            print(voice_status_str)
            return 0

        # Initialize full logging
        setup_logging(settings.logging, settings.paths.base_dir)
        logger = get_logger("core")
        logger.info(
            "JARVIS Core initialized (name=%s, version=%s, env=%s, mode=%s, model_provider=%s, voice=%s)",
            settings.system.name,
            settings.system.version,
            settings.system.environment,
            settings.system.mode,
            settings.model.provider,
            "enabled" if settings.voice.enabled else "disabled",
        )

        if parsed_args.check:
            print(f"JARVIS configuration check passed. Base dir: {settings.paths.base_dir}")
            return 0

        # Output startup banner
        print(get_banner(mode=mode, status="ready"))

        # Initialize Orchestrator
        orchestrator = Orchestrator(settings=settings)

        # Initialize Voice Pipeline only if enabled
        voice_pipeline = None
        if settings.voice.enabled:
            try:
                from app.voice import VoicePipeline

                voice_pipeline = VoicePipeline(config=settings.voice, orchestrator=orchestrator)
                if settings.voice.mode != "text":
                    voice_pipeline.start()
            except Exception as v_err:
                logger.warning("Voice pipeline could not be initialized: %s", v_err)

        # Run terminal conversation REPL
        return run_terminal_repl(mode, orchestrator, voice_pipeline=voice_pipeline)

    except ConfigurationError as err:
        sys.stderr.write(f"Configuration error: {err}\n")
        return 1
    except Exception as err:
        sys.stderr.write(f"Fatal initialization error: {err}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

