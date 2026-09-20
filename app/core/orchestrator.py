"""Central orchestrator for the JARVIS intelligence layer.

Coordinates the core flow:
User text -> Session -> ContextManager -> ModelRouter -> ModelResponse -> Session -> Response
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from app.core.context import ContextManager
from app.core.exceptions import (
    ModelError,
    ModelTimeoutError,
    ModelUnavailableError,
)
from app.core.logger import get_logger
from app.core.model import ChatMessage
from app.core.router import ModelRouter
from app.core.session import Session, SessionManager

if TYPE_CHECKING:
    from app.config.settings import Settings

logger = get_logger("orchestrator")


class Orchestrator:
    """Coordinates conversation sessions, context assembly, and model invocation."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        if settings is None:
            from app.config.settings import get_settings

            settings = get_settings()
        self.settings = settings
        self.session_manager = SessionManager()
        self.context_manager = ContextManager(
            max_context_messages=self.settings.model.max_context_messages,
        )
        self.router = ModelRouter(self.settings.model)
        logger.info(
            "JARVIS Orchestrator initialized (provider=%s, model=%s)",
            self.settings.model.provider,
            self.settings.model.model_name,
        )

    def process_message(self, user_text: str, session_id: str = "terminal-default") -> str:
        """Process a user message and return the assistant response.

        Target flow:
        User text -> Session -> Context -> Model -> Response -> Session update
        """
        clean_text = user_text.strip()
        if not clean_text:
            return "Please provide an instruction or query, sir."

        # 1. Retrieve or create session
        session: Session = self.session_manager.get_or_create_session(session_id)

        # 2. Append user message to session
        session.add_user_message(clean_text)
        logger.debug("Received input in session '%s': %s", session_id, clean_text)

        # 3. Assemble prompt context from history
        context_messages: List[ChatMessage] = self.context_manager.build_context(
            session.get_history(),
        )

        # 4. Resolve model provider from router
        provider = self.router.get_provider("default")

        # 5. Generate response with clean error handling
        try:
            response = provider.generate(
                context_messages,
                temperature=self.settings.model.temperature,
            )
            assistant_text = response.content
        except ModelUnavailableError as err:
            logger.warning("Model service unavailable: %s", err)
            assistant_text = (
                f"I apologize, sir, but the model service is currently unreachable ({err}). "
                "Please ensure your local runtime (such as Ollama) is active, or configure a fallback provider."
            )
        except ModelTimeoutError as err:
            logger.warning("Model request timed out: %s", err)
            assistant_text = (
                "The model provider did not respond in time. Please try again or adjust the timeout settings."
            )
        except ModelError as err:
            logger.error("Model execution error: %s", err)
            assistant_text = f"An error occurred while processing your request: {err}"
        except Exception as err:
            logger.exception("Unexpected error in orchestrator: %s", err)
            assistant_text = f"I encountered an unexpected internal error: {err}"

        # 6. Append assistant response to session history
        session.add_assistant_message(assistant_text)
        logger.debug("Generated response for session '%s': %s", session_id, assistant_text)

        return assistant_text

    def reset_session(self, session_id: str = "terminal-default") -> None:
        """Clear conversation history for the specified session."""
        session = self.session_manager.get_session(session_id)
        if session:
            session.clear()
            logger.info("Session '%s' reset.", session_id)

    def get_session_history(self, session_id: str = "terminal-default") -> List[ChatMessage]:
        """Retrieve the conversation history for a given session."""
        session = self.session_manager.get_session(session_id)
        if session:
            return session.get_history()
        return []
