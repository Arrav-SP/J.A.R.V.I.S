"""Data schemas and type definitions for the JARVIS memory subsystem.

Provides structured, typed representation for memory records, importance levels,
categories, and working memory state without relying on arbitrary unvalidated blobs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MemoryCategory(str, Enum):
    """Categorical classification of memory items."""

    SHORT_TERM = "short_term"
    WORKING = "working"
    LONG_TERM = "long_term"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PREFERENCE = "preference"
    PROJECT = "project"


class MemoryImportance(str, Enum):
    """Importance ranking for memory retention, prioritization, and injection."""

    LOW = "low"
    NORMAL = "normal"
    IMPORTANT = "important"
    CRITICAL = "critical"

    @property
    def score(self) -> float:
        """Numeric scalar representation of importance."""
        scores = {
            MemoryImportance.LOW: 0.25,
            MemoryImportance.NORMAL: 0.5,
            MemoryImportance.IMPORTANT: 0.75,
            MemoryImportance.CRITICAL: 1.0,
        }
        return scores.get(self, 0.5)

    @classmethod
    def from_score(cls, score: float) -> MemoryImportance:
        """Derive importance enum from numeric score."""
        if score >= 0.9:
            return cls.CRITICAL
        if score >= 0.7:
            return cls.IMPORTANT
        if score >= 0.4:
            return cls.NORMAL
        return cls.LOW


def get_utc_now() -> str:
    """Return ISO-formatted UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


class MemoryRecord(BaseModel):
    """Canonical structured memory item representation."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: MemoryCategory = Field(default=MemoryCategory.LONG_TERM)
    content: str
    created_at: str = Field(default_factory=get_utc_now)
    updated_at: str = Field(default_factory=get_utc_now)
    importance: MemoryImportance = Field(default=MemoryImportance.NORMAL)
    source: str = Field(default="user_explicit", description="Origin: user_explicit, conversation, system, tool")
    tags: List[str] = Field(default_factory=list)
    project: Optional[str] = Field(default=None, description="Project context scope if applicable")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def update_content(self, new_content: str, importance: Optional[MemoryImportance] = None) -> None:
        """Update content and refresh updated_at timestamp."""
        self.content = new_content
        if importance is not None:
            self.importance = importance
        self.updated_at = get_utc_now()


class WorkingMemoryState(BaseModel):
    """Structured transient state for active task execution."""

    current_goal: Optional[str] = None
    current_task: Optional[str] = None
    current_project: Optional[str] = None
    active_files: List[str] = Field(default_factory=list)
    current_plan: List[str] = Field(default_factory=list)
    current_step: Optional[int] = None
    current_tool: Optional[str] = None
    temporary_observations: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def is_empty(self) -> bool:
        """Check if working memory currently has active state."""
        return not any([
            self.current_goal,
            self.current_task,
            self.current_project,
            self.active_files,
            self.current_plan,
            self.current_step is not None,
            self.current_tool,
            self.temporary_observations,
            self.metadata,
        ])

    def clear(self) -> None:
        """Reset working state."""
        self.current_goal = None
        self.current_task = None
        self.current_project = None
        self.active_files.clear()
        self.current_plan.clear()
        self.current_step = None
        self.current_tool = None
        self.temporary_observations.clear()
        self.metadata.clear()


class MemorySearchResult(BaseModel):
    """Structured result returned from search or selective retrieval."""

    record: MemoryRecord
    relevance_score: float = Field(ge=0.0, le=1.0)
    match_source: str = Field(default="semantic", description="Match method: exact, keyword, semantic, hybrid")
