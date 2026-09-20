"""Unit and integration tests for JARVIS Orchestrator."""

from unittest.mock import MagicMock
import pytest

from app.config.settings import ModelConfig, Settings
from app.core.exceptions import ModelTimeoutError, ModelUnavailableError
from app.core.orchestrator import Orchestrator


def test_orchestrator_single_turn() -> None:
    """Verify processing a single message through the Orchestrator."""
    settings = Settings(model=ModelConfig(provider="mock"))
    orchestrator = Orchestrator(settings=settings)

    response = orchestrator.process_message("Explain recursion.")
    assert "Recursion" in response
    assert "base case" in response.lower()

    history = orchestrator.get_session_history()
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[0].content == "Explain recursion."
    assert history[1].role == "assistant"


def test_orchestrator_multi_turn_context_retention() -> None:
    """Verify multi-turn conversation retains context across turns (Roadmap Part 1 Completion Test)."""
    settings = Settings(model=ModelConfig(provider="mock"))
    orchestrator = Orchestrator(settings=settings)

    # Turn 1
    resp1 = orchestrator.process_message("Explain recursion.")
    assert "Recursion" in resp1

    # Turn 2
    resp2 = orchestrator.process_message("What did I just ask you?")
    assert "Explain recursion." in resp2

    history = orchestrator.get_session_history()
    assert len(history) == 4
    assert history[0].content == "Explain recursion."
    assert history[2].content == "What did I just ask you?"


def test_orchestrator_empty_message() -> None:
    """Verify orchestrator handles whitespace/empty input gracefully."""
    settings = Settings(model=ModelConfig(provider="mock"))
    orchestrator = Orchestrator(settings=settings)

    response = orchestrator.process_message("   ")
    assert "Please provide an instruction" in response


def test_orchestrator_reset_session() -> None:
    """Verify resetting session history."""
    settings = Settings(model=ModelConfig(provider="mock"))
    orchestrator = Orchestrator(settings=settings)

    orchestrator.process_message("Hello")
    assert len(orchestrator.get_session_history()) == 2

    orchestrator.reset_session()
    assert len(orchestrator.get_session_history()) == 0


def test_orchestrator_handles_provider_unavailable() -> None:
    """Verify graceful handling when model provider is unreachable."""
    settings = Settings(model=ModelConfig(provider="mock"))
    orchestrator = Orchestrator(settings=settings)

    # Mock provider to raise ModelUnavailableError
    mock_provider = MagicMock()
    mock_provider.generate.side_effect = ModelUnavailableError("Connection refused on port 11434")
    orchestrator.router.register_provider("default", mock_provider)

    response = orchestrator.process_message("Explain recursion.")
    assert "currently unreachable" in response
    assert "Connection refused" in response


def test_orchestrator_handles_provider_timeout() -> None:
    """Verify graceful handling when model provider times out."""
    settings = Settings(model=ModelConfig(provider="mock"))
    orchestrator = Orchestrator(settings=settings)

    mock_provider = MagicMock()
    mock_provider.generate.side_effect = ModelTimeoutError("Request timed out after 30s")
    orchestrator.router.register_provider("default", mock_provider)

    response = orchestrator.process_message("Explain recursion.")
    assert "did not respond in time" in response
