"""Central orchestrator for the JARVIS intelligence layer.

Coordinates the core flow:
User text -> Session -> ContextManager -> ModelRouter -> ModelResponse -> Session -> Response
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

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

from app.personality.manager import PersonalityManager
from app.personality.models import OperatingMode

if TYPE_CHECKING:
    from app.config.settings import Settings

logger = get_logger("orchestrator")


class Orchestrator:
    """Coordinates conversation sessions, context assembly, personality, and model invocation."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        if settings is None:
            from app.config.settings import get_settings

            settings = get_settings()
        self.settings = settings
        self.personality_manager = PersonalityManager(self.settings.personality)
        self.session_manager = SessionManager()
        self.context_manager = ContextManager(
            max_context_messages=self.settings.model.max_context_messages,
        )
        self.router = ModelRouter(self.settings.model)
        logger.info(
            "JARVIS Orchestrator initialized (provider=%s, model=%s, mode=%s)",
            self.settings.model.provider,
            self.settings.model.model_name,
            self.personality_manager.get_mode().value,
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

        # 3. Assemble prompt context from history using active personality prompt
        system_instructions = self.personality_manager.get_system_instructions()
        context_messages: List[ChatMessage] = self.context_manager.build_context(
            session.get_history(),
            system_prompt=system_instructions,
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

    def set_mode(self, mode: OperatingMode | str) -> str:
        """Switch operating mode at runtime."""
        profile = self.personality_manager.set_mode(mode)
        return f"Operating mode switched to {profile.name.upper()}."

    def get_mode(self) -> str:
        """Return the current operating mode name."""
        return self.personality_manager.get_mode().value

    def set_trait(self, trait_name: str, value: Any) -> str:
        """Update a specific personality trait at runtime."""
        self.personality_manager.set_trait(trait_name, value)
        return f"Personality trait '{trait_name}' updated to {value}."

    def get_personality_status(self) -> Dict[str, Any]:
        """Retrieve a structured summary of active personality settings."""
        return self.personality_manager.get_status()

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
