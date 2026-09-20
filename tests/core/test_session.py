"""Unit tests for conversation session management."""

import pytest

from app.core.session import Session, SessionManager


def test_session_message_management() -> None:
    """Verify adding messages and retrieving history in a session."""
    session = Session(session_id="test-session")
    assert session.session_id == "test-session"
    assert len(session.messages) == 0

    session.add_user_message("Hello JARVIS")
    session.add_assistant_message("Hello sir")

    history = session.get_history()
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[0].content == "Hello JARVIS"
    assert history[1].role == "assistant"
    assert history[1].content == "Hello sir"


def test_session_history_limit() -> None:
    """Verify get_history respects max_messages truncation."""
    session = Session()
    for i in range(10):
        session.add_user_message(f"Message {i}")

    truncated = session.get_history(max_messages=4)
    assert len(truncated) == 4
    assert truncated[0].content == "Message 6"
    assert truncated[-1].content == "Message 9"


def test_session_clear() -> None:
    """Verify clearing session history."""
    session = Session()
    session.add_user_message("Test")
    assert len(session.messages) == 1

    session.clear()
    assert len(session.messages) == 0


def test_session_manager() -> None:
    """Verify SessionManager creates, retrieves, isolates, and deletes sessions."""
    manager = SessionManager()

    s1 = manager.get_or_create_session("session-1")
    s2 = manager.get_or_create_session("session-2")

    s1.add_user_message("User 1 msg")
    s2.add_user_message("User 2 msg")

    assert len(s1.messages) == 1
    assert s1.messages[0].content == "User 1 msg"

    assert len(s2.messages) == 1
    assert s2.messages[0].content == "User 2 msg"

    assert "session-1" in manager.list_sessions()
    assert "session-2" in manager.list_sessions()

    assert manager.delete_session("session-1") is True
    assert manager.get_session("session-1") is None
