"""Long-term persistent memory manager.

Coordinates persistent storage, retrieval, deduplication, and updates for stable facts,
user preferences, decisions, and knowledge across restarts.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.core.logger import get_logger
from app.memory.schemas import MemoryCategory, MemoryImportance, MemoryRecord
from app.memory.storage import SQLiteMemoryStorage

logger = get_logger("memory.long_term")


class LongTermMemory:
    """Manages persistent memory records stored in SQLite."""

    def __init__(self, storage: SQLiteMemoryStorage) -> None:
        self.storage = storage

    def store_fact(
        self,
        content: str,
        category: MemoryCategory = MemoryCategory.LONG_TERM,
        importance: MemoryImportance = MemoryImportance.NORMAL,
        tags: Optional[List[str]] = None,
        project: Optional[str] = None,
        source: str = "user_explicit",
        metadata: Optional[Dict[str, Any]] = None,
        deduplicate: bool = True,
    ) -> MemoryRecord:
        """Store a new fact, performing deduplication/update if an equivalent memory exists."""
        clean_content = content.strip()
        tags = tags or []
        metadata = metadata or {}

        if deduplicate:
            existing = self.find_duplicate(clean_content, project=project, category=category)
            if existing:
                logger.info("Found existing memory matching content; updating record %s", existing.id)
                existing.update_content(clean_content, importance=importance)
                # Merge tags
                merged_tags = list(set(existing.tags + tags))
                existing.tags = merged_tags
                if metadata:
                    existing.metadata.update(metadata)
                self.storage.save(existing)
                return existing

        record = MemoryRecord(
            category=category,
            content=clean_content,
            importance=importance,
            source=source,
            tags=tags,
            project=project,
            metadata=metadata,
        )
        self.storage.save(record)
        return record

    def find_duplicate(
        self,
        content: str,
        project: Optional[str] = None,
        category: Optional[MemoryCategory] = None,
    ) -> Optional[MemoryRecord]:
        """Find an existing memory that matches normalized content or topic."""
        norm_incoming = self._normalize_for_matching(content)
        records = self.storage.list_all(category=category, project=project, limit=200)

        for rec in records:
            norm_existing = self._normalize_for_matching(rec.content)
            # Exact normalized match
            if norm_incoming == norm_existing:
                return rec
            # Key-value fact pattern matching: e.g. "my compiler project is called X" vs "my compiler project is called Y"
            subject_incoming = self._extract_fact_subject(content)
            subject_existing = self._extract_fact_subject(rec.content)
            if subject_incoming and subject_existing and subject_incoming == subject_existing:
                return rec

        return None

    def get(self, memory_id: str) -> Optional[MemoryRecord]:
        """Fetch memory record by ID."""
        return self.storage.get(memory_id)

    def delete(self, memory_id: str) -> bool:
        """Delete memory record by ID."""
        return self.storage.delete(memory_id)

    def list_memories(
        self,
        category: Optional[MemoryCategory] = None,
        project: Optional[str] = None,
        importance: Optional[MemoryImportance] = None,
        limit: int = 50,
    ) -> List[MemoryRecord]:
        """List stored memories with filtering."""
        return self.storage.list_all(category=category, project=project, importance=importance, limit=limit)

    def search_keyword(self, query: str, limit: int = 10, project: Optional[str] = None) -> List[MemoryRecord]:
        """Search memory content via SQLite keyword match."""
        return self.storage.search_keyword(query=query, limit=limit, project=project)

    @staticmethod
    def _normalize_for_matching(text: str) -> str:
        """Normalize text by lowercasing and stripping punctuation and excessive whitespace."""
        clean = re.sub(r"[^\w\s]", "", text.lower())
        return " ".join(clean.split())

    @staticmethod
    def _extract_fact_subject(text: str) -> Optional[str]:
        """Extract the entity/subject part of common fact declarations for overwrite deduplication."""
        # e.g., "my compiler project is called OptGraph" -> "compiler project"
        # e.g., "my preferred language is Python" -> "preferred language"
        m = re.search(r"\bmy\s+([\w\s]+?)\s+(?:is|called|named)\b", text, re.IGNORECASE)
        if m:
            sub = m.group(1).strip().lower()
            return sub
        return None
