"""Model abstraction layer and LLM provider implementations for JARVIS.

Provides a decoupled interface for LLMs, supporting local runtimes
like Ollama as well as deterministic mock providers for testing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import urllib.error
import urllib.request

from app.core.exceptions import (
    ConfigurationError,
    ModelError,
    ModelTimeoutError,
    ModelUnavailableError,
)
from app.core.logger import get_logger

if TYPE_CHECKING:
    from app.config.settings import ModelConfig

logger = get_logger("model")


@dataclass
class ChatMessage:
    """A single chat message in a conversation."""

    role: str
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, str]:
        """Convert message to a dictionary for API payloads."""
        return {
            "role": self.role,
            "content": self.content,
        }


@dataclass
class ModelResponse:
    """Structured response returned by an LLM provider."""

    content: str
    model_name: str
    token_usage: Optional[Dict[str, int]] = None
    finish_reason: str = "stop"


class BaseLLMProvider(ABC):
    """Abstract base class for all replaceable LLM providers."""

    @abstractmethod
    def generate(self, messages: List[ChatMessage], **kwargs: Any) -> ModelResponse:
        """Generate a response given a list of conversation messages."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the model provider and underlying service are reachable."""
        pass


class MockLLMProvider(BaseLLMProvider):
    """Deterministic and context-aware mock provider for development and testing."""

    def __init__(self, model_name: str = "mock-jarvis-v1") -> None:
        self.model_name = model_name

    def is_available(self) -> bool:
        return True

    def generate(self, messages: List[ChatMessage], **kwargs: Any) -> ModelResponse:
        if not messages:
            return ModelResponse(
                content="Greetings. I am JARVIS. How may I assist you today?",
                model_name=self.model_name,
            )

        # Get the latest user message
        user_messages = [m for m in messages if m.role == "user"]
        if not user_messages:
            return ModelResponse(
                content="Standing by for instructions, sir.",
                model_name=self.model_name,
            )

        latest_user_msg = user_messages[-1].content.strip()
        lower_msg = latest_user_msg.lower()

        # Extract mode and address from system instructions
        system_content = next((m.content for m in messages if m.role == "system"), "")
        is_coding = "OPERATING MODE: CODING" in system_content
        is_study = "OPERATING MODE: STUDY" in system_content
        is_emergency = "OPERATING MODE: EMERGENCY" in system_content
        is_professional = "OPERATING MODE: PROFESSIONAL" in system_content
        is_research = "OPERATING MODE: RESEARCH" in system_content

        # Context-aware query recall: "what did i just ask you?"
        if any(phrase in lower_msg for phrase in ["what did i just ask", "what was my last question", "what did i ask"]):
            if len(user_messages) >= 2:
                previous_msg = user_messages[-2].content.strip()
                response_text = f"You previously asked: '{previous_msg}'"
            else:
                response_text = "This is the first question in our current session, sir."

        # Concept explanation test: recursion (adapts style based on active mode)
        elif "recursion" in lower_msg:
            if is_coding:
                response_text = (
                    "```python\ndef recurse(n):\n    if n <= 0:\n        return\n    recurse(n - 1)\n```\n"
                    "Recursion: function invokes itself until a base termination condition is satisfied."
                )
            elif is_study:
                response_text = (
                    "Let's break down recursion step-by-step! Imagine Russian nesting dolls: each doll contains "
                    "a smaller one inside, until you reach the solid base doll that cannot be opened further. "
                    "In code, a function solves a small piece of work and calls itself on the remainder until "
                    "it reaches the base case. Shall we write a simple factorial together?"
                )
            elif is_emergency:
                response_text = (
                    "RECURSION: Function self-invocation. CRITICAL: Requires verified base condition to prevent stack overflow."
                )
            elif is_professional:
                response_text = (
                    "Recursion is an algorithmic paradigm in which a procedure invokes itself on successive "
                    "subproblems, bounded by a designated base termination criterion."
                )
            elif is_research:
                response_text = (
                    "Recursion represents inductive computation. Formal analysis demonstrates recurrence relations "
                    "yielding execution time T(n) and auxiliary stack frame allocation proportional to recursion depth."
                )
            else:
                response_text = (
                    "Recursion is a programming concept where a function calls itself directly or indirectly "
                    "to solve smaller instances of a problem. Every recursive function must define a base case "
                    "to terminate execution and prevent infinite stack overflow."
                )

        # Greetings
        elif any(greeting in lower_msg for greeting in ["hello", "hi", "hey", "greetings"]):
            if is_coding:
                response_text = "JARVIS operational in CODING mode. Ready for code tasks."
            elif is_study:
                response_text = "Hello! JARVIS study assistant ready. What topic are we exploring today?"
            elif is_emergency:
                response_text = "JARVIS EMERGENCY MODE ACTIVE. State immediate priority."
            else:
                response_text = "Hello. JARVIS systems are operational and ready."

        # Status query
        elif "status" in lower_msg:
            response_text = "All core systems are nominal. Intelligence layer is active."

        # Default conversational echo/reasoning
        else:
            if is_coding:
                response_text = f"[CODING] Task acknowledged: '{latest_user_msg}'."
            elif is_emergency:
                response_text = f"[EMERGENCY] Critical instruction: '{latest_user_msg}'."
            else:
                response_text = (
                    f"Understood: '{latest_user_msg}'. Processing this request through the JARVIS intelligence layer."
                )

        return ModelResponse(
            content=response_text,
            model_name=self.model_name,
            token_usage={"prompt_tokens": len(messages) * 10, "completion_tokens": len(response_text.split())},
            finish_reason="stop",
        )


class OllamaProvider(BaseLLMProvider):
    """Local LLM provider interfacing with an Ollama daemon."""

    def __init__(
        self,
        model_name: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.7,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        """Verify connectivity to Ollama server."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate(self, messages: List[ChatMessage], **kwargs: Any) -> ModelResponse:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": [m.to_dict() for m in messages],
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
            },
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                content = result.get("message", {}).get("content", "")
                return ModelResponse(
                    content=content,
                    model_name=self.model_name,
                    token_usage={
                        "prompt_tokens": result.get("prompt_eval_count", 0),
                        "completion_tokens": result.get("eval_count", 0),
                    },
                    finish_reason="stop",
                )
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="ignore")
            logger.error("Ollama HTTP %d error: %s", err.code, err_body)
            raise ModelError(f"Ollama HTTP error {err.code}: {err.reason} ({err_body})") from err
        except urllib.error.URLError as err:
            if isinstance(err.reason, TimeoutError) or "timed out" in str(err.reason).lower():
                logger.error("Ollama request timed out after %.1f seconds", self.timeout_seconds)
                raise ModelTimeoutError(
                    f"Ollama request timed out after {self.timeout_seconds} seconds."
                ) from err
            logger.warning("Ollama connection failed: %s", err.reason)
            raise ModelUnavailableError(
                f"Unable to connect to Ollama at '{self.base_url}'. Ensure 'ollama serve' is running."
            ) from err
        except TimeoutError as err:
            logger.error("Ollama request timed out after %.1f seconds", self.timeout_seconds)
            raise ModelTimeoutError(
                f"Ollama request timed out after {self.timeout_seconds} seconds."
            ) from err


def get_model_provider(config: ModelConfig) -> BaseLLMProvider:
    """Factory function to instantiate the configured LLM provider."""
    provider_type = config.provider.lower()

    if provider_type == "mock":
        return MockLLMProvider(model_name=config.model_name)

    if provider_type == "ollama":
        provider = OllamaProvider(
            model_name=config.model_name,
            base_url=config.base_url,
            temperature=config.temperature,
            timeout_seconds=config.timeout_seconds,
        )

        # If Ollama is unavailable but fallback is enabled, fall back gracefully
        if config.fallback_to_mock and not provider.is_available():
            logger.warning(
                "Ollama is unreachable at '%s'. Falling back to MockLLMProvider as configured.",
                config.base_url,
            )
            return MockLLMProvider(model_name=f"{config.model_name} (offline-fallback)")

        return provider

    raise ConfigurationError(f"Unsupported model provider: '{config.provider}'")
