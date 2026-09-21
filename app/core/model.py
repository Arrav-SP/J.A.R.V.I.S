"""Model abstraction layer and LLM provider implementations for JARVIS.

Provides a decoupled interface for LLMs, supporting local runtimes
like Ollama as well as deterministic mock providers for testing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import re
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

        # Regression explanation
        elif "regression" in lower_msg:
            if is_coding:
                response_text = (
                    "```python\nfrom sklearn.linear_model import LinearRegression\n"
                    "model = LinearRegression().fit(X, y)\n```\n"
                    "Regression models the mathematical relationship between dependent and independent variables."
                )
            elif is_study:
                response_text = (
                    "Regression is a way of finding trends in data! Imagine plotting your study hours on one axis "
                    "and test scores on the other. Regression draws the line that best predicts your score based on "
                    "how much you studied."
                )
            else:
                response_text = (
                    "Regression is a fundamental statistical method used to estimate relationships between variables. "
                    "It models how a dependent variable changes when one or more independent variables vary."
                )

        # Name introduction and recall
        elif any(phrase in lower_msg for phrase in ["my name is", "call me", "i am called"]):
            # Extract clean name up to comma, conjunction, or punctuation
            name_candidate = "Arav"
            for marker in ["my name is ", "call me ", "i am called "]:
                if marker in lower_msg:
                    raw_tail = latest_user_msg[lower_msg.index(marker) + len(marker):]
                    raw_tail = re.split(r"[,;.?]|\b(?:what|and|how|can|could|please|tell)\b", raw_tail, flags=re.IGNORECASE)[0]
                    clean_name = raw_tail.strip().title()
                    if clean_name:
                        name_candidate = clean_name
                    break

            has_weather = any(w in lower_msg for w in ["forecast", "weather", "temperature", "rain"])
            if has_weather:
                response_text = (
                    f"Pleasure to formally make your acquaintance, {name_candidate}. "
                    "However, I am currently operating in local offline standby without live weather API telemetry. "
                    "Once your Groq API key is saved and loaded, I will synthesize real-time meteorological forecasts for you, sir."
                )
            else:
                response_text = f"Pleasure to formally make your acquaintance, {name_candidate}. Systems are at your service, sir."

        elif "what is my name" in lower_msg or "who am i" in lower_msg:
            # Check conversation history for name
            found_name = "Arav"
            for msg in user_messages:
                m_lower = msg.content.lower()
                if "my name is " in m_lower:
                    found_name = msg.content[m_lower.index("my name is ") + 11:].strip().rstrip(".").title()
                    break
            response_text = f"You are {found_name}, sir. Primary operator of this JARVIS terminal."

        # Weather / forecast query in mock mode
        elif any(w in lower_msg for w in ["forecast", "weather", "temperature", "rain"]):
            response_text = (
                "Currently operating in local offline mode without live weather API telemetry, sir. "
                "Once your Groq API key is active in .env, I can synthesize real-time data and forecasts."
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
                    f"Understood, sir: '{latest_user_msg}'. Processing through the JARVIS intelligence layer."
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


class GroqProvider(BaseLLMProvider):
    """Ultra-fast cloud LLM provider using Groq Cloud API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "openai/gpt-oss-120b",
        temperature: float = 0.7,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.api_key = api_key
        # Automatically upgrade legacy or deprecated model IDs to supported models
        if model_name in {"llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama3.3"}:
            self.model_name = "openai/gpt-oss-120b"
        else:
            self.model_name = model_name
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def generate(self, messages: List[ChatMessage], **kwargs: Any) -> ModelResponse:
        if not self.is_available():
            raise ModelUnavailableError("Groq API key is not configured. Set GROQ_API_KEY in .env.")

        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [m.to_dict() for m in messages],
            "temperature": kwargs.get("temperature", self.temperature),
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key.strip()}",
                "User-Agent": "JARVIS-Assistant/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                choice = result.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "")
                usage = result.get("usage", {})
                return ModelResponse(
                    content=content,
                    model_name=self.model_name,
                    token_usage={
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                    },
                    finish_reason=choice.get("finish_reason", "stop"),
                )
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="ignore")
            # If the requested model is not found on Groq, auto-fallback to openai/gpt-oss-120b
            if err.code == 404 and "model_not_found" in err_body and self.model_name != "openai/gpt-oss-120b":
                logger.warning("Groq model '%s' not found on server. Falling back to 'openai/gpt-oss-120b'.", self.model_name)
                self.model_name = "openai/gpt-oss-120b"
                return self.generate(messages, **kwargs)
            logger.error("Groq API HTTP %d: %s", err.code, err_body)
            raise ModelError(f"Groq API error {err.code}: {err.reason} ({err_body})") from err
        except urllib.error.URLError as err:
            if isinstance(err.reason, TimeoutError) or "timed out" in str(err.reason).lower():
                raise ModelTimeoutError(f"Groq request timed out after {self.timeout_seconds}s.") from err
            raise ModelUnavailableError(f"Cannot reach Groq API (internet unreachable): {err.reason}") from err
        except TimeoutError as err:
            raise ModelTimeoutError(f"Groq request timed out after {self.timeout_seconds}s.") from err


class GeminiProvider(BaseLLMProvider):
    """Google Gemini cloud LLM provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-1.5-flash",
        temperature: float = 0.7,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def generate(self, messages: List[ChatMessage], **kwargs: Any) -> ModelResponse:
        if not self.is_available():
            raise ModelUnavailableError("Gemini API key is not configured. Set GEMINI_API_KEY in .env.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key.strip()}"

        contents = []
        system_instruction = None
        for m in messages:
            if m.role == "system":
                system_instruction = {"parts": [{"text": m.content}]}
            else:
                role = "user" if m.role == "user" else "model"
                contents.append({"role": role, "parts": [{"text": m.content}]})

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": kwargs.get("temperature", self.temperature),
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

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
                candidates = result.get("candidates", [])
                if not candidates:
                    return ModelResponse(content="No response generated.", model_name=self.model_name)
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts)
                return ModelResponse(content=text, model_name=self.model_name)
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="ignore")
            logger.error("Gemini API HTTP %d: %s", err.code, err_body)
            raise ModelError(f"Gemini API error {err.code}: {err.reason} ({err_body})") from err
        except urllib.error.URLError as err:
            if isinstance(err.reason, TimeoutError) or "timed out" in str(err.reason).lower():
                raise ModelTimeoutError(f"Gemini request timed out after {self.timeout_seconds}s.") from err
            raise ModelUnavailableError(f"Cannot reach Gemini API (internet unreachable): {err.reason}") from err
        except TimeoutError as err:
            raise ModelTimeoutError(f"Gemini request timed out after {self.timeout_seconds}s.") from err


class HybridLLMProvider(BaseLLMProvider):
    """Dual-mode online/offline provider with automatic internet fallback."""

    def __init__(
        self,
        online_provider: BaseLLMProvider,
        offline_provider: BaseLLMProvider,
    ) -> None:
        self.online_provider = online_provider
        self.offline_provider = offline_provider
        self.active_mode = "online"

    def is_available(self) -> bool:
        return self.online_provider.is_available() or self.offline_provider.is_available()

    def generate(self, messages: List[ChatMessage], **kwargs: Any) -> ModelResponse:
        # Check if online provider is configured (has API key)
        if self.online_provider.is_available():
            try:
                response = self.online_provider.generate(messages, **kwargs)
                self.active_mode = "online"
                return response
            except (ModelUnavailableError, ModelTimeoutError, ModelError) as err:
                logger.warning(
                    "Cloud LLM call failed (%s). Switching to offline mode.",
                    err,
                )
                self.active_mode = "offline"
                offline_response = self.offline_provider.generate(messages, **kwargs)
                if "internet" in str(err).lower() or "unreachable" in str(err).lower() or "timed out" in str(err).lower():
                    notice = "Internet connection not detected. Switched to offline mode, sir.\n\n"
                else:
                    notice = f"Cloud service error: {err}. Switched to offline mode, sir.\n\n"
                return ModelResponse(
                    content=notice + offline_response.content,
                    model_name=f"{offline_response.model_name} (offline)",
                    token_usage=offline_response.token_usage,
                    finish_reason=offline_response.finish_reason,
                )

        # Online provider has no API key configured
        self.active_mode = "offline"
        logger.info("Operating in local offline mode (no cloud API key configured).")
        return self.offline_provider.generate(messages, **kwargs)


def _build_offline_provider(config: ModelConfig) -> BaseLLMProvider:
    """Helper to build the offline local model provider."""
    provider_type = config.offline_provider.lower()
    if provider_type == "ollama":
        ollama = OllamaProvider(
            model_name=config.offline_model,
            base_url=config.base_url,
            temperature=config.temperature,
            timeout_seconds=config.timeout_seconds,
        )
        if ollama.is_available():
            return ollama
        logger.info("Ollama is not running locally. Using MockLLMProvider for offline standby.")
        return MockLLMProvider(model_name=f"{config.offline_model} (offline-standby)")
    return MockLLMProvider(model_name="mock-offline")


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
        if config.fallback_to_mock and not provider.is_available():
            logger.warning(
                "Ollama is unreachable at '%s'. Falling back to MockLLMProvider as configured.",
                config.base_url,
            )
            return MockLLMProvider(model_name=f"{config.model_name} (offline-fallback)")
        return provider

    if provider_type == "groq":
        return GroqProvider(
            api_key=config.api_key,
            model_name=config.groq_model,
            temperature=config.temperature,
            timeout_seconds=config.timeout_seconds,
        )

    if provider_type == "gemini":
        return GeminiProvider(
            api_key=config.api_key,
            model_name=config.gemini_model,
            temperature=config.temperature,
            timeout_seconds=config.timeout_seconds,
        )

    if provider_type == "hybrid":
        online = GroqProvider(
            api_key=config.api_key,
            model_name=config.groq_model,
            temperature=config.temperature,
            timeout_seconds=config.timeout_seconds,
        )
        offline = _build_offline_provider(config)
        return HybridLLMProvider(online_provider=online, offline_provider=offline)

    raise ConfigurationError(f"Unsupported model provider: '{config.provider}'")
