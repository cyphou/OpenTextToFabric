"""Per-item migration fidelity tracking.

Tracks the conversion outcome for every extracted item so the HTML report
can show granular success/failure breakdowns and an aggregate fidelity score.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Conversion status constants
EXACT = "EXACT"
APPROXIMATE = "APPROXIMATE"
UNSUPPORTED = "UNSUPPORTED"
SKIPPED = "SKIPPED"


# Category weight for aggregate fidelity scoring (higher = more important)
DEFAULT_WEIGHTS: dict[str, float] = {
    "nodes": 1.0,
    "documents": 1.5,
    "permissions": 1.2,
    "metadata": 0.8,
    "expressions": 1.5,
    "visuals": 1.3,
    "datasets": 1.0,
    "connections": 0.8,
}

# Points per status (out of 1.0)
STATUS_SCORES: dict[str, float] = {
    EXACT: 1.0,
    APPROXIMATE: 0.6,
    UNSUPPORTED: 0.0,
    SKIPPED: 0.0,
}


@dataclass
class ReportItem:
    """A single migrated item."""
    name: str
    category: str
    status: str
    source_type: str = ""
    details: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class MigrationReport:
    """Accumulates conversion results and computes fidelity scores."""

    def __init__(self, weights: dict[str, float] | None = None):
        self._items: list[ReportItem] = []
        self._weights = weights or DEFAULT_WEIGHTS

    # ── Adding items ──────────────────────────────────────────────

    def add(
        self,
        name: str,
        category: str,
        status: str,
        source_type: str = "",
        details: str = "",
        **metadata: Any,
    ) -> ReportItem:
        """Record a single converted item."""
        item = ReportItem(
            name=name,
            category=category,
            status=status,
            source_type=source_type,
            details=details,
            metadata=metadata,
        )
        self._items.append(item)
        return item

    def add_batch(self, category: str, items: list[dict[str, Any]]) -> None:
        """Record multiple items in one call.

        Each dict should have at least ``name`` and ``status`` keys.
        """
        for it in items:
            self.add(
                name=it.get("name", ""),
                category=category,
                status=it.get("status", SKIPPED),
                source_type=it.get("source_type", ""),
                details=it.get("details", ""),
            )

    # ── Queries ───────────────────────────────────────────────────

    @property
    def items(self) -> list[ReportItem]:
        return list(self._items)

    def by_category(self, category: str) -> list[ReportItem]:
        return [i for i in self._items if i.category == category]

    def status_counts(self, category: str | None = None) -> dict[str, int]:
        """Return {status: count} for all items or a category."""
        items = self.by_category(category) if category else self._items
        counts: dict[str, int] = {}
        for it in items:
            counts[it.status] = counts.get(it.status, 0) + 1
        return counts

    def categories(self) -> list[str]:
        """Return sorted list of categories with items."""
        return sorted({i.category for i in self._items})

    # ── Fidelity scoring ──────────────────────────────────────────

    def category_fidelity(self, category: str) -> float:
        """Return fidelity percentage (0–100) for a category."""
        items = self.by_category(category)
        if not items:
            return 100.0
        total = sum(STATUS_SCORES.get(i.status, 0.0) for i in items)
        return total / len(items) * 100

    def overall_fidelity(self) -> float:
        """Return weighted overall fidelity percentage."""
        total_weight = 0.0
        weighted_sum = 0.0
        for cat in self.categories():
            w = self._weights.get(cat, 1.0)
            fid = self.category_fidelity(cat)
            total_weight += w
            weighted_sum += w * fid
        return weighted_sum / total_weight if total_weight else 100.0

    # ── Serialization ─────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Export report data as a dict."""
        return {
            "overall_fidelity": round(self.overall_fidelity(), 2),
            "total_items": len(self._items),
            "status_counts": self.status_counts(),
            "categories": {
                cat: {
                    "fidelity": round(self.category_fidelity(cat), 2),
                    "counts": self.status_counts(cat),
                    "items": [
                        {
                            "name": i.name,
                            "status": i.status,
                            "source_type": i.source_type,
                            "details": i.details,
                        }
                        for i in self.by_category(cat)
                    ],
                }
                for cat in self.categories()
            },
        }

    def save(self, path: str | Path) -> None:
        """Save the report data as JSON."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
