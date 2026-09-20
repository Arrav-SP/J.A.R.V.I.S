"""Unit tests for ContextManager."""

from app.core.context import ContextManager
from app.core.model import ChatMessage


def test_context_manager_build_context() -> None:
    """Verify context manager prepends system prompt."""
    cm = ContextManager(system_prompt="Custom System Prompt")
    history = [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Greetings"),
    ]

    context = cm.build_context(history)
    assert len(context) == 3
    assert context[0].role == "system"
    assert context[0].content == "Custom System Prompt"
    assert context[1].role == "user"
    assert context[2].role == "assistant"


def test_context_manager_truncation() -> None:
    """Verify context manager enforces sliding window limit."""
    cm = ContextManager(max_context_messages=3)
    history = [ChatMessage(role="user", content=f"Msg {i}") for i in range(10)]

    context = cm.build_context(history)
    # 1 system message + 3 most recent history messages
    assert len(context) == 4
    assert context[0].role == "system"
    assert context[1].content == "Msg 7"
    assert context[2].content == "Msg 8"
    assert context[3].content == "Msg 9"
