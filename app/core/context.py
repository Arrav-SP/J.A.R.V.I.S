"""Context management for JARVIS reasoning and prompt assembly.

Manages system instructions, personality baseline, and conversation context window.
"""

from __future__ import annotations

from typing import List

from app.core.model import ChatMessage

DEFAULT_SYSTEM_PROMPT = (
    "You are JARVIS, a highly capable, articulate, and disciplined personal AI assistant. "
    "You communicate with clarity, precision, and calm confidence. "
    "You assist the user across computer tasks, programming, research, and analysis."
)


class ContextManager:
    """Assembles prompt context for the LLM from system instructions and conversation history."""

    def __init__(self, system_prompt: str = DEFAULT_SYSTEM_PROMPT, max_context_messages: int = 20) -> None:
        self.system_prompt: str = system_prompt
        self.max_context_messages: int = max_context_messages

    def set_system_prompt(self, prompt: str) -> None:
        """Update the system prompt."""
        self.system_prompt = prompt

    def get_system_prompt(self) -> str:
        """Retrieve the current system prompt."""
        return self.system_prompt

    def build_context(self, history: List[ChatMessage]) -> List[ChatMessage]:
        """Construct the complete message payload for the LLM.

        Prepends the system prompt and applies sliding-window message truncation.
        """
        # Apply sliding window truncation to history if it exceeds the limit
        truncated_history = history[-self.max_context_messages:] if len(history) > self.max_context_messages else history

        messages: List[ChatMessage] = [
            ChatMessage(role="system", content=self.system_prompt),
        ]
        messages.extend(truncated_history)
        return messages
