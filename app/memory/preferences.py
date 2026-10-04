"""Preference memory manager for persistent user preferences.

Maintains user settings, tool choices, preferred languages, and interaction styles.
Refuses to store sensitive information (e.g., API keys, passwords, credentials).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.core.logger import get_logger
from app.memory.schemas import MemoryCategory, MemoryImportance, MemoryRecord
from app.memory.storage import SQLiteMemoryStorage

logger = get_logger("memory.preferences")

# Regex heuristics to identify sensitive credential patterns
SECRET_PATTERNS = [
    r"(?i)\b(?:api[_-]?key|secret|password|token|bearer|private[_-]?key)\b\s*[:=]\s*\S+",
    r"\bghp_[A-Za-z0-9_]{36,}\b",
    r"\bgsk_[A-Za-z0-9_]{30,}\b",
    r"\bAIza[0-9A-Za-z-_]{35}\b",
]


class PreferenceMemory:
    """Manages persistent user preferences."""

    def __init__(self, storage: SQLiteMemoryStorage) -> None:
        self.storage = storage

    def is_sensitive(self, text: str) -> bool:
        """Check whether text contains credentials, API keys, or secrets."""
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    def set_preference(
        self,
        preference: str,
        key: Optional[str] = None,
        importance: MemoryImportance = MemoryImportance.IMPORTANT,
    ) -> Optional[MemoryRecord]:
        """Record or update a user preference."""
        clean = preference.strip()
        if self.is_sensitive(clean):
            logger.warning("Rejected preference record containing sensitive token/credential pattern.")
            return None

        tags = ["preference"]
        if key:
            tags.append(f"key:{key.strip().lower()}")

        # Check existing preferences for key
        if key:
            all_prefs = self.storage.list_all(category=MemoryCategory.PREFERENCE, limit=100)
            target_tag = f"key:{key.strip().lower()}"
            for p in all_prefs:
                if target_tag in p.tags:
                    p.update_content(clean, importance=importance)
                    self.storage.save(p)
                    return p

        record = MemoryRecord(
            category=MemoryCategory.PREFERENCE,
            content=clean,
            importance=importance,
            source="user_explicit",
            tags=tags,
            metadata={"pref_key": key} if key else {},
        )
        self.storage.save(record)
        return record

    def get_all_preferences(self) -> List[MemoryRecord]:
        """Fetch all stored user preferences."""
        return self.storage.list_all(category=MemoryCategory.PREFERENCE, limit=100)
