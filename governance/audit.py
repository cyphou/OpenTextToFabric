"""Migration audit trail — tracks what was migrated, permission deltas, and lineage."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """Single audit trail entry."""
    timestamp: float = field(default_factory=time.time)
    action: str = ""  # "extract", "transform", "deploy", "map_permission", "map_label"
    source_type: str = ""  # "content_server", "documentum", "birt"
    source_id: str = ""
    source_name: str = ""
    target_type: str = ""  # "lakehouse", "pipeline", "report", "rls_role"
    target_path: str = ""
    status: str = "success"  # "success", "warning", "error", "skipped"
    details: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditTrail:
    """Migration audit trail with full event logging."""

    def __init__(self):
        self._entries: list[AuditEntry] = []
        self._start_time: float = time.time()

    def log(
        self,
        action: str,
        source_type: str = "",
        source_id: str = "",
        source_name: str = "",
        target_type: str = "",
        target_path: str = "",
        status: str = "success",
        details: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Log a single audit event."""
        entry = AuditEntry(
            action=action,
            source_type=source_type,
            source_id=source_id,
            source_name=source_name,
            target_type=target_type,
            target_path=target_path,
            status=status,
            details=details,
            metadata=metadata or {},
        )
        self._entries.append(entry)
        logger.debug("Audit: %s %s/%s → %s (%s)", action, source_type, source_id, target_path, status)
        return entry

    def log_extraction(self, source_type: str, item_count: int, details: str = "") -> None:
        """Log an extraction event."""
        self.log(
            action="extract",
            source_type=source_type,
            details=details,
            metadata={"item_count": item_count},
        )

    def log_permission_delta(
        self,
        source_name: str,
        source_perms: list[str],
        target_perms: list[str],
    ) -> None:
        """Log permission mapping delta."""
        self.log(
            action="map_permission",
            source_name=source_name,
            details=f"Source perms: {source_perms} → Target perms: {target_perms}",
            metadata={
                "source_permissions": source_perms,
                "target_permissions": target_perms,
                "permissions_added": [p for p in target_perms if p not in source_perms],
                "permissions_removed": [p for p in source_perms if p not in target_perms],
            },
        )

    def log_error(self, action: str, source_id: str, error: str) -> None:
        """Log an error event."""
        self.log(action=action, source_id=source_id, status="error", details=error)

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def error_count(self) -> int:
        return sum(1 for e in self._entries if e.status == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for e in self._entries if e.status == "warning")

    def summary(self) -> dict[str, Any]:
        """Generate audit summary statistics."""
        actions: dict[str, int] = {}
        statuses: dict[str, int] = {}
        for entry in self._entries:
            actions[entry.action] = actions.get(entry.action, 0) + 1
            statuses[entry.status] = statuses.get(entry.status, 0) + 1

        return {
            "total_entries": self.entry_count,
            "duration_seconds": round(time.time() - self._start_time, 2),
            "actions": actions,
            "statuses": statuses,
            "errors": self.error_count,
            "warnings": self.warning_count,
        }

    def export_json(self, output_dir: str | Path) -> Path:
        """Export full audit trail to JSON."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "migration_audit.json"

        data = {
            "summary": self.summary(),
            "entries": [asdict(e) for e in self._entries],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info("Exported audit trail: %d entries to %s", self.entry_count, path)
        return path

    def export_csv(self, output_dir: str | Path) -> Path:
        """Export audit trail as CSV."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "migration_audit.csv"

        import csv
        fields = ["timestamp", "action", "source_type", "source_id", "source_name",
                  "target_type", "target_path", "status", "details"]

        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for entry in self._entries:
                writer.writerow(asdict(entry))

        return path
