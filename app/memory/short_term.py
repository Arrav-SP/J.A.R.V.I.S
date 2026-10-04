"""Short-term conversational memory manager.

Maintains recent conversation turns within sensible bounded limits so the prompt context
does not grow indefinitely. Distinct from persistent long-term storage.
"""

from __future__ import annotations

from typing import List, Optional
from app.core.model import ChatMessage


class ShortTermMemory:
    """Bounded in-memory buffer of recent conversation turns."""

    def __init__(self, max_messages: int = 20) -> None:
        self.max_messages = max(2, max_messages)
        self._messages: List[ChatMessage] = []

    def add_message(self, role: str, content: str) -> None:
        """Add a single message to the conversation buffer with truncation."""
        self._messages.append(ChatMessage(role=role, content=content))
        self._trim()

    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        self.add_message("user", content)

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message."""
        self.add_message("assistant", content)

    def get_messages(self, limit: Optional[int] = None) -> List[ChatMessage]:
        """Return conversational history up to the specified limit."""
        if limit is not None:
            return self._messages[-limit:]
        return list(self._messages)

    def get_recent_summary(self, max_turns: int = 4) -> str:
        """Construct a lightweight string summary of the most recent turns."""
        turns = self._messages[-max_turns:]
        if not turns:
            return ""
        lines = [f"{msg.role.upper()}: {msg.content}" for msg in turns]
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear short-term conversational history."""
        self._messages.clear()

    def count(self) -> int:
        """Return current message count."""
        return len(self._messages)

    def _trim(self) -> None:
        """Enforce maximum buffer capacity."""
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages:]
