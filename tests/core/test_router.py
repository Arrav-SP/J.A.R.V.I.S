"""Unit tests for ModelRouter."""

from app.config.settings import ModelConfig
from app.core.model import MockLLMProvider
from app.core.router import ModelRouter


def test_model_router_default() -> None:
    """Verify ModelRouter resolves default provider."""
    config = ModelConfig(provider="mock", model_name="default-test")
    router = ModelRouter(config)

    provider = router.get_provider("default")
    assert isinstance(provider, MockLLMProvider)
    assert provider.model_name == "default-test"


def test_model_router_custom_route() -> None:
    """Verify ModelRouter resolves custom registered routes."""
    config = ModelConfig(provider="mock", model_name="default-test")
    router = ModelRouter(config)

    fast_provider = MockLLMProvider(model_name="fast-test")
    router.register_provider("fast", fast_provider)

    assert router.get_provider("fast") is fast_provider
    # Unknown task routes fall back to default
    assert router.get_provider("unknown_route") is router.get_provider("default")
