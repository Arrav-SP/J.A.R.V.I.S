"""Core schemas and base abstractions for the JARVIS Tool Subsystem.

Defines parameter descriptors, tool definitions, execution results,
and the abstract BaseTool contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional


@dataclass
class ToolParameter:
    """Describes a single parameter expected by a tool."""

    name: str
    type_name: str  # "string", "integer", "number", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[str]] = None

    def to_schema(self) -> Dict[str, Any]:
        """Convert parameter to JSON Schema format."""
        schema: Dict[str, Any] = {
            "type": self.type_name,
            "description": self.description,
        }
        if self.enum:
            schema["enum"] = self.enum
        return schema


@dataclass
class ToolDefinition:
    """Complete specification of a tool for cataloging and LLM tool calling."""

    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    category: str = "general"

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert tool definition to OpenAI / Groq function-calling schema."""
        properties: Dict[str, Any] = {}
        required: List[str] = []

        for param in self.parameters:
            properties[param.name] = param.to_schema()
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


@dataclass
class ToolResult:
    """Outcome of a tool execution."""

    success: bool
    data: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "timestamp": self.timestamp.isoformat(),
        }


class BaseTool(ABC):
    """Abstract base class for all callable tools in JARVIS."""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Return the tool's definition and parameter metadata."""
        pass

    @property
    def name(self) -> str:
        """Convenience property for tool name."""
        return self.definition.name

    @abstractmethod
    def run(self, **kwargs: Any) -> Any:
        """Execute the tool core logic and return raw data."""
        pass

    def execute(self, **kwargs: Any) -> ToolResult:
        """Safely execute the tool with timing, validation, and error encapsulation."""
        start_t = time.time()
        try:
            data = self.run(**kwargs)
            elapsed_ms = (time.time() - start_t) * 1000.0
            return ToolResult(
                success=True,
                data=data,
                execution_time_ms=elapsed_ms,
            )
        except Exception as err:
            elapsed_ms = (time.time() - start_t) * 1000.0
            return ToolResult(
                success=False,
                data=None,
                error=str(err),
                execution_time_ms=elapsed_ms,
            )
