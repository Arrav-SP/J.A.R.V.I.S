"""Working memory manager for active task and session state.

Holds temporary execution state: current goal, current task, active files, current plan,
step progress, and temporary observations. Designed to be reset when tasks or sessions complete.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from app.memory.schemas import WorkingMemoryState


class WorkingMemory:
    """Manages ephemeral operational context during active task execution."""

    def __init__(self) -> None:
        self._state = WorkingMemoryState()

    def get_state(self) -> WorkingMemoryState:
        """Get the current working memory state object."""
        return self._state

    def set_goal(self, goal: str) -> None:
        """Set active high-level goal."""
        self._state.current_goal = goal

    def set_task(self, task: str) -> None:
        """Set active granular task."""
        self._state.current_task = task

    def set_project(self, project: str) -> None:
        """Set the active working project name."""
        self._state.current_project = project

    def add_active_file(self, filepath: str) -> None:
        """Register a file path being inspected or modified."""
        clean = filepath.strip()
        if clean and clean not in self._state.active_files:
            self._state.active_files.append(clean)

    def remove_active_file(self, filepath: str) -> None:
        """Remove a file path from active set."""
        if filepath in self._state.active_files:
            self._state.active_files.remove(filepath)

    def set_plan(self, steps: List[str]) -> None:
        """Set execution plan steps."""
        self._state.current_plan = list(steps)
        self._state.current_step = 0 if steps else None

    def advance_step(self) -> Optional[int]:
        """Advance plan step pointer."""
        if self._state.current_step is not None:
            self._state.current_step += 1
            if self._state.current_step >= len(self._state.current_plan):
                self._state.current_step = None
        return self._state.current_step

    def add_observation(self, observation: str) -> None:
        """Record an intermediate tool or system observation."""
        clean = observation.strip()
        if clean:
            self._state.temporary_observations.append(clean)

    def set_metadata(self, key: str, value: Any) -> None:
        """Set task-specific metadata."""
        self._state.metadata[key] = value

    def get_context_summary(self) -> Optional[str]:
        """Format active working state into an LLM context block."""
        if self._state.is_empty():
            return None

        lines: List[str] = ["[ACTIVE TASK & WORKING MEMORY]:"]
        if self._state.current_project:
            lines.append(f"- Active Project: {self._state.current_project}")
        if self._state.current_goal:
            lines.append(f"- Current Goal: {self._state.current_goal}")
        if self._state.current_task:
            lines.append(f"- Current Task: {self._state.current_task}")
        if self._state.active_files:
            lines.append(f"- Active Files: {', '.join(self._state.active_files)}")
        if self._state.current_plan:
            curr = self._state.current_step if self._state.current_step is not None else 0
            lines.append(f"- Plan Step: {curr + 1}/{len(self._state.current_plan)}")
        if self._state.temporary_observations:
            last_obs = self._state.temporary_observations[-3:]
            lines.append(f"- Recent Observations: {' | '.join(last_obs)}")

        return "\n".join(lines)

    def clear(self) -> None:
        """Reset all working memory state."""
        self._state.clear()
