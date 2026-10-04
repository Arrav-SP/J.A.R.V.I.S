"""Episodic memory store for significant events and milestones.

Captures structured interactions, task completions, important decisions, and milestones
with precise timestamps, event types, and outcomes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.memory.schemas import MemoryCategory, MemoryImportance, MemoryRecord
from app.memory.storage import SQLiteMemoryStorage


class EpisodicMemory:
    """Manages timestamped historical episodes, milestones, and task outcomes."""

    def __init__(self, storage: SQLiteMemoryStorage) -> None:
        self.storage = storage

    def record_episode(
        self,
        event_description: str,
        event_type: str = "task_completed",
        project: Optional[str] = None,
        importance: MemoryImportance = MemoryImportance.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryRecord:
        """Record a significant event or milestone into episodic memory."""
        meta = metadata or {}
        meta["event_type"] = event_type

        tags = ["episode", event_type]
        if project:
            tags.append(project)

        record = MemoryRecord(
            category=MemoryCategory.EPISODIC,
            content=event_description.strip(),
            importance=importance,
            source="system_event",
            tags=tags,
            project=project,
            metadata=meta,
        )
        self.storage.save(record)
        return record

    def get_recent_episodes(self, limit: int = 10, project: Optional[str] = None) -> List[MemoryRecord]:
        """Retrieve recent episodic events ordered newest first."""
        return self.storage.list_all(
            category=MemoryCategory.EPISODIC,
            project=project,
            limit=limit,
        )
