"""Central MemoryManager orchestrating all JARVIS memory tiers.

Coordinates:
- ShortTermMemory (recent conversation buffer)
- WorkingMemory (current goal, task, plan, active files)
- LongTermMemory (persistent facts in SQLite)
- SemanticMemoryStore (local vector index & cosine similarity)
- EpisodicMemory (timestamped milestones and outcomes)
- PreferenceMemory (stable user preferences)
- ProjectMemory (project-scoped knowledge)

Provides high-level, explainable APIs:
- remember()
- retrieve()
- search()
- update()
- forget()
- clear_session()
- get_relevant_context()
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from app.core.exceptions import JarvisError
from app.core.logger import get_logger
from app.memory.episodic import EpisodicMemory
from app.memory.long_term import LongTermMemory
from app.memory.preferences import PreferenceMemory
from app.memory.project_memory import ProjectMemory
from app.memory.schemas import (
    MemoryCategory,
    MemoryImportance,
    MemoryRecord,
    MemorySearchResult,
)
from app.memory.semantic import LocalEmbeddingProvider, SemanticMemoryStore
from app.memory.short_term import ShortTermMemory
from app.memory.storage import SQLiteMemoryStorage
from app.memory.working import WorkingMemory

logger = get_logger("memory.manager")


class MemoryManagerError(JarvisError):
    """Raised when memory operations encounter unrecoverable errors."""


class MemoryManager:
    """Unified entry point for the JARVIS memory subsystem."""

    def __init__(
        self,
        storage_path: Path | str = "data/memory/jarvis_memory.db",
        enabled: bool = True,
        semantic_search: bool = True,
        max_short_term_messages: int = 20,
        max_retrieved_memories: int = 5,
        default_importance: MemoryImportance = MemoryImportance.NORMAL,
        allow_neural_embeddings: bool = False,
    ) -> None:
        self.enabled = enabled
        self.storage_path = Path(storage_path)
        self.semantic_search_enabled = semantic_search
        self.max_retrieved_memories = max(1, max_retrieved_memories)
        self.default_importance = default_importance

        # Initialize storage tier
        try:
            self.storage = SQLiteMemoryStorage(self.storage_path)
        except Exception as err:
            logger.critical("Failed to initialize SQLite storage at %s: %s", self.storage_path, err)
            raise MemoryManagerError(f"Database initialization failure: {err}") from err

        # Initialize memory tiers
        self.short_term = ShortTermMemory(max_messages=max_short_term_messages)
        self.working = WorkingMemory()
        self.long_term = LongTermMemory(self.storage)
        self.episodic = EpisodicMemory(self.storage)
        self.preferences = PreferenceMemory(self.storage)
        self.project_memory = ProjectMemory(self.storage)

        # Initialize semantic vector store
        self.embedding_provider = LocalEmbeddingProvider(allow_neural=allow_neural_embeddings)
        self.semantic = SemanticMemoryStore(self.embedding_provider)

        # Preload semantic index from persistent records if enabled
        if self.enabled and self.semantic_search_enabled:
            self._warm_semantic_index()

        logger.info(
            "MemoryManager initialized (storage=%s, enabled=%s, semantic=%s)",
            self.storage_path,
            self.enabled,
            self.semantic_search_enabled,
        )

    def _warm_semantic_index(self) -> None:
        """Load persistent memories into in-memory vector index for low-latency retrieval."""
        try:
            all_records = self.storage.list_all(limit=1000)
            for rec in all_records:
                self.semantic.index_record(rec)
            logger.debug("Indexed %d persistent memories into semantic index", len(all_records))
        except Exception as err:
            logger.warning("Error warming semantic index: %s (continuing with cold index)", err)

    def remember(
        self,
        content: str,
        category: MemoryCategory = MemoryCategory.LONG_TERM,
        importance: Optional[MemoryImportance] = None,
        tags: Optional[List[str]] = None,
        project: Optional[str] = None,
        source: str = "user_explicit",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryRecord:
        """Store or update a memory item across persistent storage and vector index."""
        if not self.enabled:
            logger.debug("Memory subsystem disabled; skipping remember()")
            return MemoryRecord(content=content, category=category)

        imp = importance or self.default_importance

        # Reject secrets
        if self.preferences.is_sensitive(content):
            logger.warning("Rejecting storage of sensitive content in memory")
            raise MemoryManagerError("Cannot store credentials or sensitive tokens in persistent memory.")

        # Dispatch based on category
        if category == MemoryCategory.PREFERENCE:
            record = self.preferences.set_preference(content, importance=imp)
            if not record:
                raise MemoryManagerError("Preference rejected due to sensitive pattern match.")
        elif category == MemoryCategory.PROJECT and project:
            record = self.project_memory.record_project_fact(
                project_name=project,
                fact=content,
                importance=imp,
                metadata=metadata,
            )
        elif category == MemoryCategory.EPISODIC:
            record = self.episodic.record_episode(
                event_description=content,
                project=project,
                importance=imp,
                metadata=metadata,
            )
        else:
            record = self.long_term.store_fact(
                content=content,
                category=category,
                importance=imp,
                tags=tags,
                project=project,
                source=source,
                metadata=metadata,
            )

        # Update semantic index
        if self.semantic_search_enabled and record:
            try:
                self.semantic.index_record(record)
            except Exception as err:
                logger.warning("Failed to index memory record %s semantically: %s", record.id, err)

        logger.info("Remembered [%s] (%s): %s", record.category.value, record.importance.value, record.content[:60])
        return record

    def forget(self, memory_id: str) -> bool:
        """Forget/delete a specific memory by ID."""
        if not self.enabled:
            return False

        deleted = self.storage.delete(memory_id)
        if deleted:
            self.semantic.remove_record(memory_id)
            logger.info("Forgot memory record %s", memory_id)
        return deleted

    def forget_by_content(self, query: str) -> int:
        """Find and delete memories matching a content query."""
        if not self.enabled:
            return 0

        matching = self.search(query, limit=5)
        count = 0
        for res in matching:
            if self.forget(res.record.id):
                count += 1
        return count

    def update(
        self,
        memory_id: str,
        new_content: str,
        importance: Optional[MemoryImportance] = None,
    ) -> Optional[MemoryRecord]:
        """Update the content of an existing memory record."""
        if not self.enabled:
            return None

        record = self.storage.get(memory_id)
        if not record:
            return None

        record.update_content(new_content, importance=importance)
        self.storage.save(record)
        if self.semantic_search_enabled:
            self.semantic.index_record(record)

        return record

    def search(
        self,
        query: str,
        limit: Optional[int] = None,
        project: Optional[str] = None,
        category: Optional[MemoryCategory] = None,
        threshold: float = 0.25,
    ) -> List[MemorySearchResult]:
        """Hybrid search across semantic vector index and exact/keyword storage."""
        if not self.enabled or not query.strip():
            return []

        max_results = limit or self.max_retrieved_memories
        results_map: Dict[str, MemorySearchResult] = {}

        # 1. Semantic retrieval (if enabled)
        if self.semantic_search_enabled:
            try:
                semantic_hits = self.semantic.search(
                    query=query,
                    top_k=max_results * 2,
                    threshold=threshold,
                    project=project,
                )
                for hit in semantic_hits:
                    if category and hit.record.category != category:
                        continue
                    results_map[hit.record.id] = hit
            except Exception as err:
                logger.warning("Semantic search error: %s (falling back to keyword)", err)

        # 2. Keyword fallback / enhancement
        try:
            keyword_hits = self.storage.search_keyword(query=query, limit=max_results, project=project)
            for rec in keyword_hits:
                if category and rec.category != category:
                    continue
                if rec.id not in results_map:
                    # Score keyword matches based on importance
                    score = min(1.0, 0.70 + (rec.importance.score * 0.20))
                    results_map[rec.id] = MemorySearchResult(
                        record=rec,
                        relevance_score=score,
                        match_source="keyword",
                    )
                else:
                    # Boost existing semantic hit if keyword also matched
                    results_map[rec.id].relevance_score = min(1.0, results_map[rec.id].relevance_score + 0.15)
                    results_map[rec.id].match_source = "hybrid"
        except Exception as err:
            logger.warning("Keyword search error: %s", err)

        # Sort by relevance score descending
        sorted_results = sorted(results_map.values(), key=lambda x: x.relevance_score, reverse=True)
        return sorted_results[:max_results]

    def get_relevant_context(
        self,
        query: str,
        project: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Optional[str]:
        """Selective retrieval pipeline for prompt assembly.

        Only injects relevant memories when high-confidence matches exist.
        Includes working memory if active.
        """
        if not self.enabled:
            return None

        sections: List[str] = []

        # 1. Active Working Memory (task, goal, plan)
        working_ctx = self.working.get_context_summary()
        if working_ctx:
            sections.append(working_ctx)

        # 2. Retrieve relevant long-term/project/preference memories
        active_project = project or self.working.get_state().current_project
        search_hits = self.search(query=query, limit=limit, project=active_project)

        if search_hits:
            mem_lines = ["[RELEVANT PERSISTENT MEMORIES]:"]
            for hit in search_hits:
                rec = hit.record
                src_info = f" (relevance: {hit.relevance_score:.2f}, match: {hit.match_source})"
                if rec.project:
                    src_info += f" [Project: {rec.project}]"
                mem_lines.append(f"- {rec.content}{src_info}")
            sections.append("\n".join(mem_lines))

        if not sections:
            return None

        return "\n\n".join(sections)

    def extract_and_remember_explicit(self, text: str) -> Optional[MemoryRecord]:
        """Detect and store explicit 'remember that ...' instructions from user input."""
        clean = text.strip()

        # Patterns like:
        # "remember that my compiler project is called OptGraph"
        # "remember: my compiler project is called OptGraph"
        # "please remember that I like python"
        # "remember that I prefer dark mode"
        # "note that my compiler project is called OptGraph"
        patterns = [
            r"^(?:please\s+)?(?:remember\s+that|remember\s*:?|note\s+that|keep\s+in\s+mind\s+that)\s+(.+)$",
        ]

        extracted = None
        for p in patterns:
            m = re.search(p, clean, re.IGNORECASE)
            if m:
                extracted = m.group(1).strip(" .!,'\"")
                break

        if not extracted:
            return None

        # Determine category & project
        category = MemoryCategory.LONG_TERM
        project = None
        lower_ext = extracted.lower()

        if any(w in lower_ext for w in ["prefer", "preference", "like", "favorite", "favourite"]):
            category = MemoryCategory.PREFERENCE

        # Check for project scoping e.g. "my compiler project is called OptGraph" or "in OptGraph project..."
        proj_match = re.search(r"\bproject\s+(?:(?:is\s+)?(?:called|named)|is)\s+([A-Za-z0-9_-]+)", extracted, re.IGNORECASE)
        if not proj_match:
            proj_match = re.search(r"\b([A-Za-z0-9_-]+)\s+project\b", extracted, re.IGNORECASE)

        if proj_match:
            candidate = proj_match.group(1).strip()
            if candidate.lower() not in {"is", "called", "named", "the", "a", "my"}:
                project = candidate
            category = MemoryCategory.PROJECT
        elif "project" in lower_ext:
            category = MemoryCategory.PROJECT

        try:
            return self.remember(
                content=extracted,
                category=category,
                project=project,
                importance=MemoryImportance.IMPORTANT,
                source="user_explicit",
            )
        except Exception as err:
            logger.error("Failed to automatically store explicit memory: %s", err)
            return None

    def clear_session(self) -> None:
        """Clear ephemeral short-term and working memory without touching persistent database."""
        self.short_term.clear()
        self.working.clear()
        logger.info("Session memory cleared (short-term & working).")

    def clear_all_persistent(self) -> int:
        """Dangerous: Clear all records in the persistent database and semantic index."""
        count = self.storage.clear()
        self.semantic.clear()
        logger.warning("Cleared all %d persistent memories!", count)
        return count
