"""Project-scoped memory manager.

Scopes architectural decisions, TODOs, bugs, milestones, and terminology to specific projects.
Prevents cross-project contamination of technical context.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.memory.schemas import MemoryCategory, MemoryImportance, MemoryRecord
from app.memory.storage import SQLiteMemoryStorage


class ProjectMemory:
    """Manages project-scoped technical context and facts."""

    def __init__(self, storage: SQLiteMemoryStorage) -> None:
        self.storage = storage

    def record_project_fact(
        self,
        project_name: str,
        fact: str,
        topic: str = "architecture",
        importance: MemoryImportance = MemoryImportance.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryRecord:
        """Record a project-specific fact or technical decision."""
        proj_clean = project_name.strip()
        tags = ["project", proj_clean.lower(), topic.lower()]

        meta = metadata or {}
        meta["topic"] = topic

        record = MemoryRecord(
            category=MemoryCategory.PROJECT,
            content=fact.strip(),
            importance=importance,
            source="user_explicit",
            tags=tags,
            project=proj_clean,
            metadata=meta,
        )
        self.storage.save(record)
        return record

    def get_project_memories(
        self,
        project_name: str,
        topic: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryRecord]:
        """Fetch all memories scoped to a specific project."""
        records = self.storage.list_all(
            category=MemoryCategory.PROJECT,
            project=project_name.strip(),
            limit=limit,
        )
        if topic:
            target_topic = topic.strip().lower()
            return [r for r in records if target_topic in r.tags or r.metadata.get("topic") == target_topic]
        return records

    def list_projects(self) -> List[str]:
        """List distinct project names stored in project memory."""
        records = self.storage.list_all(category=MemoryCategory.PROJECT, limit=500)
        projects = {r.project for r in records if r.project}
        return sorted(list(projects))
