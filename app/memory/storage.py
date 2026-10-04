"""Local persistent storage engine for the JARVIS memory subsystem.

Provides SQLite-based persistence for structured memory records with schema migration,
metadata indexing, JSON serialization, and tag search.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from app.core.exceptions import JarvisError
from app.memory.schemas import MemoryCategory, MemoryImportance, MemoryRecord
import logging
logger = logging.getLogger("jarvis.memory.storage")


class MemoryStorageError(JarvisError):
    """Raised when memory database operations encounter unrecoverable errors."""


class SQLiteMemoryStorage:
    """Thread-safe SQLite storage engine for structured memory records."""

    def __init__(self, db_path: Path | str = "data/memory/jarvis_memory.db") -> None:
        self.db_path = Path(db_path).resolve()
        self._ensure_db_dir()
        self._init_database()

    def _ensure_db_dir(self) -> None:
        """Create parent directories if missing."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as err:
            raise MemoryStorageError(f"Failed to create directory for memory database: {err}") from err

    def _get_connection(self) -> sqlite3.Connection:
        """Open a database connection with row factory configured."""
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as err:
            logger.error("Failed to connect to SQLite database at %s: %s", self.db_path, err)
            raise MemoryStorageError(f"Could not open memory database: {err}") from err

    def _init_database(self) -> None:
        """Initialize tables and indexes if they do not exist."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            importance TEXT NOT NULL,
            source TEXT NOT NULL,
            tags TEXT NOT NULL,
            project TEXT,
            confidence REAL NOT NULL,
            metadata TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_memories_category ON memories (category);
        CREATE INDEX IF NOT EXISTS idx_memories_project ON memories (project);
        CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories (importance);
        CREATE INDEX IF NOT EXISTS idx_memories_updated ON memories (updated_at DESC);
        """
        try:
            with self._get_connection() as conn:
                conn.executescript(schema_sql)
                conn.commit()
            logger.debug("Initialized SQLite memory database at %s", self.db_path)
        except sqlite3.Error as err:
            logger.critical("Failed to initialize memory database schema: %s", err)
            raise MemoryStorageError(f"Schema initialization failed: {err}") from err

    def save(self, record: MemoryRecord) -> None:
        """Insert or replace a memory record in the database."""
        sql = """
        INSERT OR REPLACE INTO memories (
            id, category, content, created_at, updated_at, importance,
            source, tags, project, confidence, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        tags_json = json.dumps(record.tags, ensure_ascii=False)
        metadata_json = json.dumps(record.metadata, ensure_ascii=False)

        try:
            with self._get_connection() as conn:
                conn.execute(
                    sql,
                    (
                        record.id,
                        record.category.value,
                        record.content,
                        record.created_at,
                        record.updated_at,
                        record.importance.value,
                        record.source,
                        tags_json,
                        record.project,
                        record.confidence,
                        metadata_json,
                    ),
                )
                conn.commit()
            logger.debug("Saved memory %s (%s) to SQLite", record.id, record.category.value)
        except sqlite3.Error as err:
            logger.error("Failed to save memory %s: %s", record.id, err)
            raise MemoryStorageError(f"Failed to persist memory record: {err}") from err

    def get(self, memory_id: str) -> Optional[MemoryRecord]:
        """Fetch a single memory record by ID."""
        sql = "SELECT * FROM memories WHERE id = ?"
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(sql, (memory_id,))
                row = cursor.fetchone()
                if row:
                    return self._row_to_record(row)
                return None
        except sqlite3.Error as err:
            logger.error("Error reading memory %s: %s", memory_id, err)
            raise MemoryStorageError(f"Failed to retrieve memory record {memory_id}: {err}") from err

    def delete(self, memory_id: str) -> bool:
        """Delete a memory record by ID. Returns True if a record was removed."""
        sql = "DELETE FROM memories WHERE id = ?"
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(sql, (memory_id,))
                conn.commit()
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.debug("Deleted memory %s from SQLite", memory_id)
                return deleted
        except sqlite3.Error as err:
            logger.error("Failed to delete memory %s: %s", memory_id, err)
            raise MemoryStorageError(f"Failed to delete memory record {memory_id}: {err}") from err

    def list_all(
        self,
        category: Optional[MemoryCategory | str] = None,
        project: Optional[str] = None,
        importance: Optional[MemoryImportance | str] = None,
        limit: int = 100,
    ) -> List[MemoryRecord]:
        """Query memories with optional category, project, and importance filters."""
        query = "SELECT * FROM memories WHERE 1=1"
        params: List[Any] = []

        if category:
            cat_val = category.value if isinstance(category, MemoryCategory) else str(category)
            query += " AND category = ?"
            params.append(cat_val)

        if project is not None:
            query += " AND project = ?"
            params.append(project)

        if importance:
            imp_val = importance.value if isinstance(importance, MemoryImportance) else str(importance)
            query += " AND importance = ?"
            params.append(imp_val)

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, limit))

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(query, tuple(params))
                rows = cursor.fetchall()
                return [self._row_to_record(r) for r in rows]
        except sqlite3.Error as err:
            logger.error("Failed to query memories: %s", err)
            raise MemoryStorageError(f"Failed to query memory records: {err}") from err

    def search_keyword(self, query: str, limit: int = 10, project: Optional[str] = None) -> List[MemoryRecord]:
        """Perform case-insensitive keyword substring search."""
        if not query.strip():
            return []
        sql = "SELECT * FROM memories WHERE content LIKE ? COLLATE NOCASE"
        params: List[Any] = [f"%{query.strip()}%"]

        if project is not None:
            sql += " AND (project = ? OR project IS NULL)"
            params.append(project)

        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, limit))

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(sql, tuple(params))
                return [self._row_to_record(r) for r in cursor.fetchall()]
        except sqlite3.Error as err:
            logger.error("Keyword search failed for '%s': %s", query, err)
            raise MemoryStorageError(f"Search query failed: {err}") from err

    def clear(self, category: Optional[MemoryCategory | str] = None) -> int:
        """Clear all records or records of a specific category. Returns count deleted."""
        try:
            with self._get_connection() as conn:
                if category:
                    cat_val = category.value if isinstance(category, MemoryCategory) else str(category)
                    cursor = conn.execute("DELETE FROM memories WHERE category = ?", (cat_val,))
                else:
                    cursor = conn.execute("DELETE FROM memories")
                conn.commit()
                count = cursor.rowcount
                logger.info("Cleared %d memory records (category=%s)", count, category)
                return count
        except sqlite3.Error as err:
            logger.error("Failed to clear memories: %s", err)
            raise MemoryStorageError(f"Failed to clear memories: {err}") from err

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        """Convert SQLite row to MemoryRecord domain instance."""
        tags = []
        if row["tags"]:
            try:
                tags = json.loads(row["tags"])
            except Exception:
                tags = []

        metadata = {}
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except Exception:
                metadata = {}

        return MemoryRecord(
            id=row["id"],
            category=MemoryCategory(row["category"]),
            content=row["content"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            importance=MemoryImportance(row["importance"]),
            source=row["source"],
            tags=tags,
            project=row["project"],
            confidence=row["confidence"],
            metadata=metadata,
        )
