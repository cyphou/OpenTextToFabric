"""Progress tracking for migration pipeline."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    """Migration step status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepProgress:
    """Progress for a single migration step."""
    name: str
    status: StepStatus = StepStatus.PENDING
    items_total: int = 0
    items_done: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str = ""

    @property
    def elapsed(self) -> float:
        if self.started_at == 0:
            return 0.0
        end = self.finished_at if self.finished_at else time.time()
        return end - self.started_at

    @property
    def percent(self) -> float:
        if self.items_total == 0:
            return 0.0
        return min(100.0, (self.items_done / self.items_total) * 100)

    def start(self, total: int = 0) -> None:
        self.status = StepStatus.RUNNING
        self.items_total = total
        self.started_at = time.time()
        logger.info("Step '%s' started (total: %d)", self.name, total)

    def advance(self, count: int = 1) -> None:
        self.items_done += count

    def complete(self) -> None:
        self.status = StepStatus.COMPLETED
        self.finished_at = time.time()
        logger.info("Step '%s' completed in %.1fs", self.name, self.elapsed)

    def fail(self, error: str) -> None:
        self.status = StepStatus.FAILED
        self.finished_at = time.time()
        self.error = error
        logger.error("Step '%s' failed: %s", self.name, error)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "items_total": self.items_total,
            "items_done": self.items_done,
            "elapsed_seconds": round(self.elapsed, 2),
            "error": self.error,
        }


@dataclass
class MigrationProgress:
    """Overall migration progress tracker."""
    steps: list[StepProgress] = field(default_factory=list)
    checkpoint_path: str = ""

    def add_step(self, name: str) -> StepProgress:
        step = StepProgress(name=name)
        self.steps.append(step)
        return step

    @property
    def current_step(self) -> StepProgress | None:
        for step in self.steps:
            if step.status == StepStatus.RUNNING:
                return step
        return None

    @property
    def is_complete(self) -> bool:
        return all(
            s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)
            for s in self.steps
        )

    @property
    def has_failures(self) -> bool:
        return any(s.status == StepStatus.FAILED for s in self.steps)

    def save_checkpoint(self, path: str | Path | None = None) -> None:
        """Save progress checkpoint for resume."""
        target = Path(path) if path else Path(self.checkpoint_path)
        if not target.name:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {"steps": [s.to_dict() for s in self.steps]}
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def summary(self) -> dict:
        """Get progress summary."""
        return {
            "total_steps": len(self.steps),
            "completed": sum(1 for s in self.steps if s.status == StepStatus.COMPLETED),
            "failed": sum(1 for s in self.steps if s.status == StepStatus.FAILED),
            "pending": sum(1 for s in self.steps if s.status == StepStatus.PENDING),
            "steps": [s.to_dict() for s in self.steps],
        }
