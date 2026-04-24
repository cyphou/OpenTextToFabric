"""Recovery report — audit trail for all self-healing actions."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RecoveryReport:
    """Records every auto-fix applied during artifact healing.

    Each entry captures what was wrong, what fix was applied, and whether
    the fix needs human follow-up. The report is persisted as JSON alongside
    the migration output for audit and compliance purposes.
    """

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def record(
        self,
        category: str,
        repair_type: str,
        *,
        description: str = "",
        action: str = "",
        severity: str = "info",
        follow_up: bool = False,
        item_name: str = "",
        original_value: str = "",
        repaired_value: str = "",
        file_path: str = "",
    ) -> dict[str, Any]:
        """Record a single healing action.

        Args:
            category: Artifact category (dax, tmdl, m_query, pbir, visual).
            repair_type: Short label (e.g. 'balanced_parens', 'birt_leak').
            description: Human-readable description of the issue.
            action: What was done to fix it.
            severity: info | warning | error.
            follow_up: True if a human should review this fix.
            item_name: Name of the affected measure/column/table/visual.
            original_value: The original (broken) value.
            repaired_value: The fixed value.
            file_path: Path to the affected file (relative to output).
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": category,
            "repair_type": repair_type,
            "description": description,
            "action": action,
            "severity": severity,
            "follow_up": follow_up,
            "item_name": item_name,
            "original_value": original_value,
            "repaired_value": repaired_value,
            "file_path": file_path,
        }
        self.entries.append(entry)
        log_fn = logger.warning if severity == "error" else logger.info
        log_fn("Heal [%s/%s] %s: %s", category, repair_type, item_name, action)
        return entry

    def get_summary(self) -> dict[str, Any]:
        """Return summary statistics."""
        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_type: dict[str, int] = {}
        follow_ups = 0

        for e in self.entries:
            by_category[e["category"]] = by_category.get(e["category"], 0) + 1
            by_severity[e["severity"]] = by_severity.get(e["severity"], 0) + 1
            by_type[e["repair_type"]] = by_type.get(e["repair_type"], 0) + 1
            if e["follow_up"]:
                follow_ups += 1

        return {
            "total_repairs": len(self.entries),
            "by_category": by_category,
            "by_severity": by_severity,
            "by_type": by_type,
            "follow_up_needed": follow_ups,
        }

    def save(self, output_dir: str | Path) -> Path:
        """Persist recovery report as JSON."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "recovery_report.json"
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": self.get_summary(),
            "entries": self.entries,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Recovery report saved: %s (%d entries)", path, len(self.entries))
        return path

    def print_summary(self) -> None:
        """Print summary to console."""
        s = self.get_summary()
        if s["total_repairs"] == 0:
            logger.info("No healing actions were needed")
            return
        logger.info("=== Recovery Summary ===")
        logger.info("Total repairs: %d", s["total_repairs"])
        for cat, cnt in s["by_category"].items():
            logger.info("  %s: %d", cat, cnt)
        if s["follow_up_needed"]:
            logger.info("⚠ %d item(s) need human review", s["follow_up_needed"])
