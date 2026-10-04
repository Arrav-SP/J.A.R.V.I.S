"""JARVIS Memory Subsystem.

Provides modular, local-first, selective memory for JARVIS:
- Short-term conversational buffer
- Working task state
- Long-term persistent knowledge
- Semantic vector retrieval with cosine similarity
- Episodic milestone & event logging
- User preference management (with secret rejection)
- Project-scoped knowledge
"""

from __future__ import annotations

from app.memory.episodic import EpisodicMemory
from app.memory.long_term import LongTermMemory
from app.memory.memory_manager import MemoryManager, MemoryManagerError
from app.memory.preferences import PreferenceMemory
from app.memory.project_memory import ProjectMemory
from app.memory.schemas import (
    MemoryCategory,
    MemoryImportance,
    MemoryRecord,
    MemorySearchResult,
    WorkingMemoryState,
)
from app.memory.semantic import LocalEmbeddingProvider, SemanticMemoryStore
from app.memory.short_term import ShortTermMemory
from app.memory.storage import SQLiteMemoryStorage
from app.memory.working import WorkingMemory

__all__ = [
    "MemoryManager",
    "MemoryManagerError",
    "MemoryRecord",
    "MemoryCategory",
    "MemoryImportance",
    "MemorySearchResult",
    "WorkingMemoryState",
    "ShortTermMemory",
    "WorkingMemory",
    "LongTermMemory",
    "SemanticMemoryStore",
    "LocalEmbeddingProvider",
    "EpisodicMemory",
    "PreferenceMemory",
    "ProjectMemory",
    "SQLiteMemoryStorage",
]
