"""Central orchestrator for the JARVIS intelligence layer.

Coordinates the core flow:
User text -> Session -> ContextManager -> ModelRouter -> ModelResponse -> Session -> Response
"""

from __future__ import annotations

import re
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
from app.tools import ToolRegistry, WeatherTool, WebSearchTool

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

        # Initialize Tool Subsystem
        self.tools = ToolRegistry()
        self.weather_tool = WeatherTool()
        self.search_tool = WebSearchTool()
        self.tools.register(self.weather_tool)
        self.tools.register(self.search_tool)

        logger.info(
            "JARVIS Orchestrator initialized (provider=%s, model=%s, mode=%s, tools=%d)",
            self.settings.model.provider,
            self.settings.model.model_name,
            self.personality_manager.get_mode().value,
            len(self.tools.list_tools()),
        )

    def _extract_weather_location(self, query: str) -> Optional[str]:
        """Detect weather/forecast intent and extract target location."""
        lower = query.lower()
        if not any(w in lower for w in ["weather", "forecast", "temperature", "is it raining", "will it rain", "rain today"]):
            return None

        # Pattern: forecast for <location> / weather in <location>
        m = re.search(
            r"\b(?:forecast\s+(?:for|in|at)|weather\s+(?:in|for|at)|temperature\s+(?:in|for|at|of))\s+([^?.!,]+)",
            query,
            re.IGNORECASE,
        )
        if m:
            raw_loc = m.group(1).strip()
            if raw_loc.lower() not in {"today", "tomorrow", "tonight", "this week"}:
                return raw_loc

        # Check known Indian and major global cities
        for city in ["vellore", "chennai", "delhi", "mumbai", "bengaluru", "bangalore", "hyderabad", "kolkata", "london", "new york"]:
            if city in lower:
                return city.title()

        return "Vellore"

    def _extract_search_query(self, query: str) -> Optional[str]:
        """Detect search intent and extract query."""
        clean = query.strip()
        lower = clean.lower()

        # Direct explicit commands: e.g. "search, who won...", "search for...", "google: ..."
        m = re.search(
            r"\b(?:search|google|browse|look\s+up|find\s+out)\b[\s,:—\-]*(?:for\s+|about\s+)?(.+)",
            clean,
            re.IGNORECASE,
        )
        if m:
            extracted = m.group(1).strip("?.! ,'\"")
            if extracted:
                return extracted

        # Heuristic questions about current events / factual winners / scores / news
        search_prefixes = (
            "who won ",
            "who is the current ",
            "latest news on ",
            "what is the score ",
            "current score ",
            "what is the latest ",
            "what happened in ",
        )
        if any(lower.startswith(p) for p in search_prefixes):
            return clean.strip("?.! ,'\"")

        return None

    def process_message(self, user_text: str, session_id: str = "terminal-default") -> str:
        """Process a user message and return the assistant response.

        Target flow:
        User text -> Session -> Tools -> Context -> Model -> Response -> Session update
        """
        clean_text = user_text.strip()
        if not clean_text:
            return "Please provide an instruction or query, sir."

        # 1. Retrieve or create session
        session: Session = self.session_manager.get_or_create_session(session_id)

        # 2. Append user message to session
        session.add_user_message(clean_text)
        logger.debug("Received input in session '%s': %s", session_id, clean_text)

        # 3. Check for live real-time tools (weather / web search)
        live_tool_context = ""
        weather_loc = self._extract_weather_location(clean_text)
        if weather_loc:
            logger.info("Executing WeatherTool for location: '%s'", weather_loc)
            w_res = self.weather_tool.execute(location=weather_loc)
            if w_res.success and w_res.data:
                live_tool_context = (
                    f"\n\n[REAL-TIME WEATHER TELEMETRY - {w_res.data.get('location', weather_loc)}]:\n"
                    f"{w_res.data.get('summary', '')}\n"
                    "Use this live factual data to answer the user's weather/forecast query directly, concisely, and naturally. "
                    "Do not invoke external tools or output code; respond purely in conversational speech."
                )
        else:
            search_query = self._extract_search_query(clean_text)
            if search_query:
                logger.info("Executing WebSearchTool for query: '%s'", search_query)
                s_res = self.search_tool.execute(query=search_query)
                if s_res.success and s_res.data and s_res.data.get("results"):
                    live_tool_context = (
                        f"\n\n[REAL-TIME LIVE WEB SEARCH FINDINGS]:\n"
                        f"{s_res.data.get('summary', '')}\n"
                        "Synthesize a concise, accurate answer based on these live search findings for spoken delivery. "
                        "Do not attempt to call external tools or output JSON function calls; respond purely in direct conversational speech."
                    )

        # 4. Assemble prompt context from history using active personality prompt + live telemetry
        system_instructions = self.personality_manager.get_system_instructions()
        if live_tool_context:
            system_instructions += live_tool_context

        context_messages: List[ChatMessage] = self.context_manager.build_context(
            session.get_history(),
            system_prompt=system_instructions,
        )

        # 5. Resolve model provider from router
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
