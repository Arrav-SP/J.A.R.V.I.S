"""Model router for task-based LLM routing.

Directs requests to appropriate models (e.g. fast commands vs complex reasoning)
while keeping providers decoupled.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from app.core.model import BaseLLMProvider, get_model_provider

if TYPE_CHECKING:
    from app.config.settings import ModelConfig


class ModelRouter:
    """Routes requests to the appropriate model provider based on task type."""

    def __init__(self, default_config: ModelConfig) -> None:
        self.default_config = default_config
        self._providers: Dict[str, BaseLLMProvider] = {
            "default": get_model_provider(default_config),
        }

    def get_provider(self, task_type: str = "default") -> BaseLLMProvider:
        """Retrieve the model provider for a given task type."""
        return self._providers.get(task_type, self._providers["default"])

    def register_provider(self, task_type: str, provider: BaseLLMProvider) -> None:
        """Register a custom provider for a specific task route."""
        self._providers[task_type] = provider
