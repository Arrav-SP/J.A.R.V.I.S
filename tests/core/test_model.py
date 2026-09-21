"""Unit tests for the model abstraction and LLM providers."""

from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from app.config.settings import ModelConfig
from app.core.exceptions import (
    ConfigurationError,
    ModelError,
    ModelTimeoutError,
    ModelUnavailableError,
)
from app.core.model import (
    ChatMessage,
    GeminiProvider,
    GroqProvider,
    HybridLLMProvider,
    MockLLMProvider,
    OllamaProvider,
    get_model_provider,
)


def test_mock_provider_empty_messages() -> None:
    """Verify mock provider handles empty message list gracefully."""
    provider = MockLLMProvider()
    response = provider.generate([])
    assert "JARVIS" in response.content
    assert response.finish_reason == "stop"


def test_mock_provider_recursion_explanation() -> None:
    """Verify mock provider answers questions about recursion accurately."""
    provider = MockLLMProvider()
    messages = [ChatMessage(role="user", content="Explain recursion.")]
    response = provider.generate(messages)
    assert "Recursion" in response.content
    assert "base case" in response.content.lower()


def test_mock_provider_context_recall() -> None:
    """Verify mock provider can recall the user's previous question from conversation history."""
    provider = MockLLMProvider()
    messages = [
        ChatMessage(role="user", content="What is the capital of France?"),
        ChatMessage(role="assistant", content="The capital of France is Paris."),
        ChatMessage(role="user", content="What did I just ask you?"),
    ]
    response = provider.generate(messages)
    assert "What is the capital of France?" in response.content


def test_ollama_provider_unavailable() -> None:
    """Verify OllamaProvider raises ModelUnavailableError when connection fails."""
    provider = OllamaProvider(base_url="http://127.0.0.1:59999")  # Unlikely port
    messages = [ChatMessage(role="user", content="Hello")]

    assert provider.is_available() is False
    with pytest.raises(ModelUnavailableError) as exc_info:
        provider.generate(messages)
    assert "Unable to connect to Ollama" in str(exc_info.value)


def test_ollama_provider_timeout() -> None:
    """Verify OllamaProvider raises ModelTimeoutError on request timeout."""
    provider = OllamaProvider(base_url="http://127.0.0.1:11434")
    messages = [ChatMessage(role="user", content="Hello")]

    with patch("urllib.request.urlopen", side_effect=TimeoutError("Connection timed out")):
        with pytest.raises(ModelTimeoutError) as exc_info:
            provider.generate(messages)
        assert "timed out" in str(exc_info.value)


def test_ollama_provider_url_error_timeout() -> None:
    """Verify OllamaProvider raises ModelTimeoutError when URLError wraps a timeout."""
    provider = OllamaProvider(base_url="http://127.0.0.1:11434")
    messages = [ChatMessage(role="user", content="Hello")]

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError(TimeoutError("socket timed out"))):
        with pytest.raises(ModelTimeoutError) as exc_info:
            provider.generate(messages)
        assert "timed out" in str(exc_info.value)



def test_ollama_provider_http_error() -> None:
    """Verify OllamaProvider handles HTTP errors."""
    provider = OllamaProvider(base_url="http://127.0.0.1:11434")
    messages = [ChatMessage(role="user", content="Hello")]

    mock_err = urllib.error.HTTPError(
        url="http://127.0.0.1:11434/api/chat",
        code=404,
        msg="Not Found",
        hdrs=MagicMock(),
        fp=MagicMock(read=lambda: b'{"error":"model not found"}'),
    )

    with patch("urllib.request.urlopen", side_effect=mock_err):
        with pytest.raises(ModelError) as exc_info:
            provider.generate(messages)
        assert "Ollama HTTP error 404" in str(exc_info.value)


def test_get_model_provider_mock() -> None:
    """Verify factory returns MockLLMProvider for 'mock' provider configuration."""
    config = ModelConfig(provider="mock", model_name="test-model")
    provider = get_model_provider(config)
    assert isinstance(provider, MockLLMProvider)
    assert provider.model_name == "test-model"


def test_get_model_provider_ollama_fallback() -> None:
    """Verify factory falls back to mock if Ollama is unreachable and fallback is enabled."""
    config = ModelConfig(
        provider="ollama",
        base_url="http://127.0.0.1:59999",
        fallback_to_mock=True,
    )
    provider = get_model_provider(config)
    assert isinstance(provider, MockLLMProvider)
    assert "offline-fallback" in provider.model_name


def test_mock_provider_name_introduction_and_recall() -> None:
    """Verify mock provider learns name on introduction and recalls it."""
    provider = MockLLMProvider()
    intro_resp = provider.generate([ChatMessage(role="user", content="My name is Aarav")])
    assert "Aarav" in intro_resp.content

    recall_resp = provider.generate([
        ChatMessage(role="user", content="My name is Aarav"),
        ChatMessage(role="assistant", content="Pleasure to formally make your acquaintance, Aarav."),
        ChatMessage(role="user", content="What is my name?"),
    ])
    assert "Aarav" in recall_resp.content


def test_mock_provider_regression_explanation() -> None:
    """Verify mock provider explains regression."""
    provider = MockLLMProvider()
    resp = provider.generate([ChatMessage(role="user", content="Explain regression")])
    assert "regression" in resp.content.lower()


def test_groq_provider_missing_key() -> None:
    """Verify GroqProvider raises ModelUnavailableError when API key is missing."""
    provider = GroqProvider(api_key=None)
    assert provider.is_available() is False
    with pytest.raises(ModelUnavailableError):
        provider.generate([ChatMessage(role="user", content="Hello")])


def test_groq_provider_success() -> None:
    """Verify GroqProvider formats payload and parses completion response."""
    provider = GroqProvider(api_key="gsk_testkey123")
    assert provider.is_available() is True

    fake_response = MagicMock()
    fake_response.read.return_value = (
        b'{"choices": [{"message": {"content": "Hello, I am JARVIS powered by Groq."}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 8}}'
    )
    fake_response.__enter__.return_value = fake_response

    with patch("urllib.request.urlopen", return_value=fake_response):
        resp = provider.generate([ChatMessage(role="user", content="Hello")])
        assert "JARVIS powered by Groq" in resp.content
        assert resp.model_name == "openai/gpt-oss-120b"


def test_gemini_provider_success() -> None:
    """Verify GeminiProvider formats payload and parses response."""
    provider = GeminiProvider(api_key="ai_testkey456")
    assert provider.is_available() is True

    fake_response = MagicMock()
    fake_response.read.return_value = (
        b'{"candidates": [{"content": {"parts": [{"text": "Greetings from Gemini."}]}}]}'
    )
    fake_response.__enter__.return_value = fake_response

    with patch("urllib.request.urlopen", return_value=fake_response):
        resp = provider.generate([ChatMessage(role="user", content="Hello")])
        assert "Greetings from Gemini." in resp.content


def test_hybrid_provider_fallback_to_offline() -> None:
    """Verify HybridLLMProvider switches to offline mode when cloud API fails."""
    online = GroqProvider(api_key="gsk_test")
    offline = MockLLMProvider(model_name="mock-offline")
    hybrid = HybridLLMProvider(online_provider=online, offline_provider=offline)

    # Simulate network down on online provider
    with patch.object(online, "generate", side_effect=ModelUnavailableError("Internet down")):
        resp = hybrid.generate([ChatMessage(role="user", content="Explain recursion")])
        assert "Internet connection not detected" in resp.content
        assert "offline" in resp.model_name
        assert "recursion" in resp.content.lower()

