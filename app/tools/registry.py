"""Tool registry for registering, cataloging, and invoking JARVIS tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.tools.schemas import BaseTool, ToolDefinition, ToolResult

logger = logging.getLogger("jarvis.tools.registry")


class ToolRegistry:
    """Central registry of executable tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        name = tool.name.lower()
        if name in self._tools:
            logger.warning("Overwriting previously registered tool '%s'.", name)
        self._tools[name] = tool
        logger.info("Tool '%s' registered (category=%s).", name, tool.definition.category)

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name."""
        name_clean = name.lower()
        if name_clean in self._tools:
            del self._tools[name_clean]
            logger.info("Tool '%s' unregistered.", name_clean)
            return True
        return False

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Retrieve a tool instance by name."""
        return self._tools.get(name.lower())

    def list_tools(self) -> List[str]:
        """Return list of all registered tool names."""
        return list(self._tools.keys())

    def get_definitions(self) -> List[ToolDefinition]:
        """Return all tool definitions."""
        return [tool.definition for tool in self._tools.values()]

    def get_openai_schemas(self) -> List[Dict[str, Any]]:
        """Return all tool definitions formatted as OpenAI / Groq function schemas."""
        return [tool.definition.to_openai_schema() for tool in self._tools.values()]

    def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool by name with arguments."""
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool '{name}' is not registered in ToolRegistry.",
            )
        return tool.execute(**kwargs)
