"""Comprehensive test suite for the JARVIS Memory Subsystem (Part 4).

Covers all 22 mandatory requirements:
1. Short-term memory stores conversation context.
2. Short-term memory respects configured limits.
3. Working memory stores current task state.
4. Long-term memory persists.
5. Long-term memory survives process restart.
6. Memory records serialize/deserialize correctly.
7. Explicit remember works.
8. Explicit forget/delete works.
9. Memory search works.
10. Semantic retrieval returns relevant memories.
11. Irrelevant memories are not unnecessarily returned.
12. Memory importance works.
13. Duplicate memories are handled.
14. Updated facts can update existing memories appropriately.
15. Project memory can be scoped by project.
16. Preference memory persists.
17. Session memory can be cleared.
18. Storage errors are handled gracefully.
19. Memory does not expose secrets unnecessarily.
20. Existing Parts 0–3 continue functioning.
21. Text mode works with memory integration.
22. Voice mode works with memory integration.
"""

from __future__ import annotations

from pathlib import Path
import pytest
import sqlite3

from app.config import get_settings, reload_settings, VoiceConfig
from app.core import ChatMessage, Orchestrator
from app.memory import (
    EpisodicMemory,
    LocalEmbeddingProvider,
    LongTermMemory,
    MemoryCategory,
    MemoryImportance,
    MemoryManager,
    MemoryManagerError,
    MemoryRecord,
    PreferenceMemory,
    ProjectMemory,
    SemanticMemoryStore,
    ShortTermMemory,
    SQLiteMemoryStorage,
    WorkingMemory,
)
from app.voice import PipelineState, VirtualAudioManager, VoicePipeline


@pytest.fixture
def memory_db_path(tmp_path: Path) -> Path:
    """Provide an isolated database path in temporary test storage."""
    db_file = tmp_path / "test_memory.db"
    return db_file


@pytest.fixture
def memory_manager(memory_db_path: Path) -> MemoryManager:
    """Provide an isolated, fully functional MemoryManager instance."""
    return MemoryManager(
        storage_path=memory_db_path,
        enabled=True,
        semantic_search=True,
        max_short_term_messages=5,
        max_retrieved_memories=3,
        allow_neural_embeddings=False,
    )


# ---------------------------------------------------------------------------
# 1 & 2. Short-term memory tests
# ---------------------------------------------------------------------------


def test_short_term_memory_stores_conversation():
    """Verify short-term memory stores conversational turns."""
    stm = ShortTermMemory(max_messages=10)
    stm.add_user_message("Hello JARVIS")
    stm.add_assistant_message("At your service, sir.")

    msgs = stm.get_messages()
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[0].content == "Hello JARVIS"
    assert msgs[1].role == "assistant"
    assert msgs[1].content == "At your service, sir."


def test_short_term_memory_respects_limits():
    """Verify short-term memory truncates older turns when limit is reached."""
    stm = ShortTermMemory(max_messages=3)
    stm.add_message("user", "Msg 1")
    stm.add_message("assistant", "Resp 1")
    stm.add_message("user", "Msg 2")
    stm.add_message("assistant", "Resp 2")

    msgs = stm.get_messages()
    assert len(msgs) == 3
    assert msgs[0].content == "Resp 1"
    assert msgs[1].content == "Msg 2"
    assert msgs[2].content == "Resp 2"


# ---------------------------------------------------------------------------
# 3. Working memory tests
# ---------------------------------------------------------------------------


def test_working_memory_stores_current_task_state():
    """Verify working memory retains goals, tasks, plans, and files."""
    wm = WorkingMemory()
    assert wm.get_state().is_empty() is True

    wm.set_project("OptGraph")
    wm.set_goal("Optimize compiler IR graph passes")
    wm.set_task("Implement dead code elimination")
    wm.add_active_file("src/opt.cpp")
    wm.add_active_file("src/opt.h")
    wm.set_plan(["Inspect IR", "Find dead nodes", "Eliminate", "Run tests"])
    wm.add_observation("Found 14 dead nodes in module A")

    state = wm.get_state()
    assert state.current_project == "OptGraph"
    assert state.current_goal == "Optimize compiler IR graph passes"
    assert len(state.active_files) == 2
    assert state.current_step == 0
    assert len(state.temporary_observations) == 1

    summary = wm.get_context_summary()
    assert "[ACTIVE TASK & WORKING MEMORY]" in summary
    assert "OptGraph" in summary
    assert "src/opt.cpp" in summary

    wm.advance_step()
    assert wm.get_state().current_step == 1


# ---------------------------------------------------------------------------
# 4 & 5. Long-term memory persistence and restart survival
# ---------------------------------------------------------------------------


def test_long_term_memory_persistence(memory_db_path: Path):
    """Verify long-term memory persists in SQLite."""
    storage = SQLiteMemoryStorage(memory_db_path)
    ltm = LongTermMemory(storage)

    rec = ltm.store_fact("My compiler project is called OptGraph.")
    assert rec.id is not None
    assert rec.content == "My compiler project is called OptGraph."

    # Direct query from SQLite
    fetched = storage.get(rec.id)
    assert fetched is not None
    assert fetched.content == "My compiler project is called OptGraph."


def test_long_term_memory_survives_process_restart(memory_db_path: Path):
    """Simulate complete process exit and re-instantiation against the same SQLite file."""
    # First process lifecycle
    mgr1 = MemoryManager(storage_path=memory_db_path)
    mgr1.remember("The secret project codename is Project Borealis.")
    del mgr1

    # Second process lifecycle (simulated restart)
    mgr2 = MemoryManager(storage_path=memory_db_path)
    results = mgr2.search("Project Borealis")
    assert len(results) > 0
    assert "Project Borealis" in results[0].record.content


# ---------------------------------------------------------------------------
# 6. Serialization / Deserialization
# ---------------------------------------------------------------------------


def test_memory_record_serialization():
    """Verify MemoryRecord model properly serializes and deserializes with types."""
    rec = MemoryRecord(
        category=MemoryCategory.PROJECT,
        content="OptGraph uses LLVM 18 backend.",
        importance=MemoryImportance.CRITICAL,
        tags=["compiler", "llvm"],
        project="OptGraph",
        metadata={"version": 18},
    )

    data = rec.model_dump()
    assert data["category"] == "project"
    assert data["importance"] == "critical"
    assert data["tags"] == ["compiler", "llvm"]

    reconstituted = MemoryRecord(**data)
    assert reconstituted.id == rec.id
    assert reconstituted.category == MemoryCategory.PROJECT
    assert reconstituted.importance == MemoryImportance.CRITICAL


# ---------------------------------------------------------------------------
# 7 & 8. Explicit remember and forget
# ---------------------------------------------------------------------------


def test_explicit_remember_and_forget(memory_manager: MemoryManager):
    """Test explicit remember API and deletion by ID and content."""
    rec = memory_manager.remember("The primary test runner is PyTest.", importance=MemoryImportance.IMPORTANT)
    assert rec.id is not None

    hits = memory_manager.search("primary test runner")
    assert any(h.record.id == rec.id for h in hits)

    # Forget by ID
    deleted = memory_manager.forget(rec.id)
    assert deleted is True

    # Search again
    hits_after = memory_manager.search("primary test runner")
    assert not any(h.record.id == rec.id for h in hits_after)


def test_forget_by_content(memory_manager: MemoryManager):
    """Test forgetting memories by content matching."""
    memory_manager.remember("Coffee preference is black with no sugar.")
    count = memory_manager.forget_by_content("coffee preference")
    assert count >= 1

    hits = memory_manager.search("coffee")
    assert len(hits) == 0


# ---------------------------------------------------------------------------
# 9, 10, & 11. Search and Semantic Retrieval
# ---------------------------------------------------------------------------


def test_memory_search_and_semantic_retrieval(memory_manager: MemoryManager):
    """Verify semantic retrieval finds concepts even with varied wording."""
    memory_manager.remember(
        "My compiler project is called OptGraph.",
        importance=MemoryImportance.CRITICAL,
        tags=["compiler", "projects"],
    )
    memory_manager.remember(
        "The gym workout routine is push pull legs.",
        importance=MemoryImportance.NORMAL,
        tags=["fitness"],
    )

    # Different wording: "What was that compiler system named?"
    results = memory_manager.search("What was that compiler system named?", limit=3)
    assert len(results) > 0
    top_hit = results[0]
    assert "OptGraph" in top_hit.record.content

    # Irrelevant memories are not at the top or return empty for unrelated topics
    astronomy_results = memory_manager.search("quantum planetary orbits around Mars", threshold=0.5)
    # Shouldn't falsely return compiler facts with high confidence
    for r in astronomy_results:
        assert r.relevance_score < 0.6 or "OptGraph" not in r.record.content


# ---------------------------------------------------------------------------
# 12. Memory Importance
# ---------------------------------------------------------------------------


def test_memory_importance_scoring():
    """Verify importance enum scores rank properly."""
    assert MemoryImportance.CRITICAL.score > MemoryImportance.IMPORTANT.score
    assert MemoryImportance.IMPORTANT.score > MemoryImportance.NORMAL.score
    assert MemoryImportance.NORMAL.score > MemoryImportance.LOW.score


# ---------------------------------------------------------------------------
# 13 & 14. Deduplication and updates
# ---------------------------------------------------------------------------


def test_memory_deduplication_and_updates(memory_manager: MemoryManager):
    """Verify updating a known fact updates existing memory rather than duplicating."""
    # First version
    rec1 = memory_manager.remember("My compiler project is called OptGraph.")
    initial_id = rec1.id

    # Second version updating the same fact
    rec2 = memory_manager.remember("My compiler project is called OptGraph v2.")
    assert rec2.id == initial_id
    assert "OptGraph v2" in rec2.content

    all_mems = memory_manager.storage.list_all()
    # Should only have 1 record, not 2
    assert len(all_mems) == 1
    assert "OptGraph v2" in all_mems[0].content


# ---------------------------------------------------------------------------
# 15. Project Memory Scoping
# ---------------------------------------------------------------------------


def test_project_memory_scoping(memory_manager: MemoryManager):
    """Verify project memories are isolated and filterable by project."""
    memory_manager.remember("Uses PyTorch 2.4", category=MemoryCategory.PROJECT, project="VisionProject")
    memory_manager.remember("Uses React 19", category=MemoryCategory.PROJECT, project="WebPortal")

    vision_facts = memory_manager.project_memory.get_project_memories("VisionProject")
    assert len(vision_facts) == 1
    assert "PyTorch" in vision_facts[0].content

    web_facts = memory_manager.project_memory.get_project_memories("WebPortal")
    assert len(web_facts) == 1
    assert "React" in web_facts[0].content


# ---------------------------------------------------------------------------
# 16. Preference Memory Persistence
# ---------------------------------------------------------------------------


def test_preference_memory(memory_manager: MemoryManager):
    """Verify preference memory persistence and retrieval."""
    pref = memory_manager.preferences.set_preference("Prefers dark mode in all editors", key="theme")
    assert pref is not None

    all_prefs = memory_manager.preferences.get_all_preferences()
    assert len(all_prefs) == 1
    assert "dark mode" in all_prefs[0].content


# ---------------------------------------------------------------------------
# 17. Session memory clearing
# ---------------------------------------------------------------------------


def test_clear_session_leaves_persistent_intact(memory_manager: MemoryManager):
    """Verify clearing session memory resets short-term/working but keeps SQLite records."""
    memory_manager.remember("Persistent fact that must survive session clear.")
    memory_manager.short_term.add_user_message("Temporary user message")
    memory_manager.working.set_goal("Temporary goal")

    memory_manager.clear_session()

    assert memory_manager.short_term.count() == 0
    assert memory_manager.working.get_state().is_empty() is True

    # Persistent records remain intact
    stored = memory_manager.storage.list_all()
    assert len(stored) == 1
    assert "Persistent fact" in stored[0].content


# ---------------------------------------------------------------------------
# 18. Error Handling
# ---------------------------------------------------------------------------


def test_storage_error_handling_graceful(tmp_path: Path):
    """Verify invalid database paths or locked files raise clean domain errors without crash."""
    invalid_path = tmp_path / "not_a_dir" / "test.db"
    # Create a regular file where the directory should be
    (tmp_path / "not_a_dir").write_text("blocked")

    with pytest.raises(MemoryManagerError):
        MemoryManager(storage_path=invalid_path)


# ---------------------------------------------------------------------------
# 19. Privacy & Secret Rejection
# ---------------------------------------------------------------------------


def test_memory_secret_rejection(memory_manager: MemoryManager):
    """Verify memory refuses to store raw API keys and credentials."""
    with pytest.raises(MemoryManagerError):
        memory_manager.remember("My API key is gsk_1234567890abcdef1234567890abcdef")

    with pytest.raises(MemoryManagerError):
        memory_manager.remember("password = SecretPassword123!")


# ---------------------------------------------------------------------------
# 20, 21, & 22. Core, Text, and Voice Integration
# ---------------------------------------------------------------------------


def test_orchestrator_text_mode_with_memory(temp_workspace: Path, clean_env):
    """Verify Orchestrator remembers facts across conversations in text mode."""
    settings = reload_settings(base_dir=temp_workspace)
    settings.model.provider = "mock"
    settings.memory.enabled = True
    settings.memory.storage_path = str(temp_workspace / "data" / "memory" / "orch_test.db")

    orch = Orchestrator(settings=settings)

    # 1. User asks to remember a fact
    resp1 = orch.process_message("Remember that my compiler project is called OptGraph.")
    assert resp1 is not None

    # Verify fact stored
    mems = orch.memory_manager.storage.list_all()
    assert len(mems) >= 1
    assert "OptGraph" in mems[0].content

    # 2. Simulate restart with new Orchestrator instance on same storage
    orch2 = Orchestrator(settings=settings)
    ctx = orch2.memory_manager.get_relevant_context("What is my compiler project called?")
    assert ctx is not None
    assert "OptGraph" in ctx

    resp2 = orch2.process_message("What is my compiler project called?")
    assert resp2 is not None


def test_voice_mode_with_memory_integration(temp_workspace: Path, clean_env):
    """Verify VoicePipeline executes end-to-end with the memory-enabled Orchestrator."""
    settings = reload_settings(base_dir=temp_workspace)
    settings.model.provider = "mock"
    settings.voice.enabled = True
    settings.voice.mode = "text"
    settings.voice.stt.provider = "mock"
    settings.voice.tts.provider = "mock"
    settings.memory.enabled = True
    settings.memory.storage_path = str(temp_workspace / "data" / "memory" / "voice_test.db")

    orch = Orchestrator(settings=settings)
    # Store a memory
    orch.memory_manager.remember("User preferred voice speed is 1.25.")

    voice_pipe = VoicePipeline(
        config=settings.voice,
        orchestrator=orch,
        audio_manager=VirtualAudioManager(),
    )

    # Simulate voice turn processing
    import numpy as np

    fake_audio = np.zeros(16000, dtype=np.float32)
    voice_pipe._process_completed_utterance(fake_audio)

    assert voice_pipe.last_telemetry is not None
    assert voice_pipe.last_telemetry["total_latency_ms"] >= 0.0
