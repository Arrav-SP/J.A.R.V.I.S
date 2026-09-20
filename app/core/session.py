"""Session management for JARVIS conversations.

Maintains in-memory conversation history and session isolation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from app.core.model import ChatMessage


class Session:
    """Represents an ongoing conversation session."""

    def __init__(self, session_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.session_id: str = session_id or str(uuid.uuid4())
        self.messages: List[ChatMessage] = []
        self.metadata: Dict[str, Any] = metadata or {}
        now = datetime.now(timezone.utc)
        self.created_at: datetime = now
        self.updated_at: datetime = now

    def add_user_message(self, content: str) -> ChatMessage:
        """Append a user message to this session."""
        msg = ChatMessage(role="user", content=content)
        self.messages.append(msg)
        self.updated_at = datetime.now(timezone.utc)
        return msg

    def add_assistant_message(self, content: str) -> ChatMessage:
        """Append an assistant response to this session."""
        msg = ChatMessage(role="assistant", content=content)
        self.messages.append(msg)
        self.updated_at = datetime.now(timezone.utc)
        return msg

    def add_system_message(self, content: str) -> ChatMessage:
        """Append an explicit system message to this session."""
        msg = ChatMessage(role="system", content=content)
        self.messages.append(msg)
        self.updated_at = datetime.now(timezone.utc)
        return msg

    def get_history(self, max_messages: Optional[int] = None) -> List[ChatMessage]:
        """Get the chronological conversation history, optionally limited to the most recent messages."""
        if max_messages and max_messages > 0:
            return self.messages[-max_messages:]
        return list(self.messages)

    def clear(self) -> None:
        """Clear all messages from this session."""
        self.messages.clear()
        self.updated_at = datetime.now(timezone.utc)


class SessionManager:
    """Manages active conversation sessions across the JARVIS system."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}

    def create_session(self, session_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Session:
        """Create and store a new conversation session."""
        session = Session(session_id=session_id, metadata=metadata)
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve an existing session by ID."""
        return self._sessions.get(session_id)

    def get_or_create_session(self, session_id: str = "default") -> Session:
        """Retrieve an existing session or create a new one if it does not exist."""
        if session_id not in self._sessions:
            return self.create_session(session_id=session_id)
        return self._sessions[session_id]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session by ID."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> List[str]:
        """Return a list of all active session IDs."""
        return list(self._sessions.keys())
