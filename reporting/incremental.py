"""Incremental sync — change detection for re-migration without full re-run.

Tracks file hashes and metadata to detect which source reports have
changed since the last migration, enabling incremental updates.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ChangeDetector:
    """Detects changes in source files since last migration."""

    def __init__(self, state_path: str | Path | None = None):
        self._state_path = Path(state_path) if state_path else None
        self._previous_state: dict[str, dict[str, Any]] = {}
        self._current_state: dict[str, dict[str, Any]] = {}
        if self._state_path and self._state_path.exists():
            self._load_state()

    def _load_state(self) -> None:
        """Load previous state from disk."""
        with open(self._state_path, encoding="utf-8") as f:
            data = json.load(f)
        self._previous_state = data.get("files", {})
        logger.info("Loaded change state: %d files tracked", len(self._previous_state))

    def save_state(self) -> None:
        """Save current state to disk."""
        if not self._state_path:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "files": self._current_state,
            }, f, indent=2)

    def scan(self, source_dir: str | Path, pattern: str = "*.rptdesign") -> dict[str, Any]:
        """Scan source directory and detect changes.

        Returns:
            Dict with added, modified, unchanged, removed file lists.
        """
        src = Path(source_dir)
        files = sorted(src.glob(pattern))

        for f in files:
            content = f.read_bytes()
            self._current_state[str(f)] = {
                "hash": hashlib.sha256(content).hexdigest(),
                "size": len(content),
                "modified": f.stat().st_mtime,
                "name": f.name,
            }

        prev_keys = set(self._previous_state.keys())
        curr_keys = set(self._current_state.keys())

        added = sorted(curr_keys - prev_keys)
        removed = sorted(prev_keys - curr_keys)
        common = curr_keys & prev_keys

        modified = []
        unchanged = []
        for key in sorted(common):
            if self._previous_state[key]["hash"] != self._current_state[key]["hash"]:
                modified.append(key)
            else:
                unchanged.append(key)

        result = {
            "added": added,
            "modified": modified,
            "unchanged": unchanged,
            "removed": removed,
            "total_source": len(files),
            "needs_migration": added + modified,
        }

        logger.info(
            "Change detection: %d added, %d modified, %d unchanged, %d removed",
            len(added), len(modified), len(unchanged), len(removed),
        )
        return result

    def get_files_to_migrate(self, source_dir: str | Path, pattern: str = "*.rptdesign") -> list[Path]:
        """Get list of files that need (re-)migration."""
        changes = self.scan(source_dir, pattern)
        return [Path(f) for f in changes["needs_migration"]]


class RecoveryReport:
    """Self-healing recovery tracking for failed migrations.

    Tracks which items failed, why, and provides retry recommendations.
    """

    def __init__(self):
        self._failures: list[dict[str, Any]] = []
        self._recoveries: list[dict[str, Any]] = []

    def record_failure(
        self,
        item: str,
        step: str,
        error: str,
        recoverable: bool = True,
        retry_strategy: str = "retry",
    ) -> None:
        """Record a migration failure."""
        self._failures.append({
            "item": item,
            "step": step,
            "error": error,
            "recoverable": recoverable,
            "retry_strategy": retry_strategy,
            "timestamp": datetime.now().isoformat(),
            "recovered": False,
        })

    def record_recovery(self, item: str, step: str, attempt: int = 1) -> None:
        """Record a successful recovery."""
        self._recoveries.append({
            "item": item,
            "step": step,
            "attempt": attempt,
            "timestamp": datetime.now().isoformat(),
        })
        # Mark matching failure as recovered
        for f in self._failures:
            if f["item"] == item and f["step"] == step and not f["recovered"]:
                f["recovered"] = True
                break

    def get_pending_retries(self) -> list[dict[str, Any]]:
        """Get failures that haven't been recovered and are retryable."""
        return [
            f for f in self._failures
            if not f["recovered"] and f["recoverable"]
        ]

    def generate_report(self, output_path: str | Path) -> Path:
        """Generate recovery report HTML."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        total = len(self._failures)
        recovered = sum(1 for f in self._failures if f["recovered"])
        pending = sum(1 for f in self._failures if not f["recovered"] and f["recoverable"])
        unrecoverable = sum(1 for f in self._failures if not f["recoverable"])

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Recovery Report</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; margin: 24px; background: #f9f9f9; }}
h1 {{ color: #0078d4; }}
.cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 16px 0; }}
.card {{ background: #fff; border-radius: 8px; padding: 16px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.card .val {{ font-size: 32px; font-weight: 700; }}
.green {{ color: #107c10; }}
.orange {{ color: #ff8c00; }}
.red {{ color: #d13438; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; margin: 16px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
th {{ background: #f0f2f5; padding: 10px; text-align: left; font-size: 12px; text-transform: uppercase; }}
td {{ padding: 10px; border-top: 1px solid #eee; }}
</style>
</head>
<body>
<h1>Migration Recovery Report</h1>
<div class="cards">
    <div class="card"><div class="val">{total}</div><div>Total Failures</div></div>
    <div class="card"><div class="val green">{recovered}</div><div>Recovered</div></div>
    <div class="card"><div class="val orange">{pending}</div><div>Pending Retry</div></div>
    <div class="card"><div class="val red">{unrecoverable}</div><div>Unrecoverable</div></div>
</div>

<h2>Failure Details</h2>
<table>
<tr><th>Item</th><th>Step</th><th>Error</th><th>Recoverable</th><th>Status</th></tr>
{"".join(f'<tr><td>{f["item"]}</td><td>{f["step"]}</td><td>{f["error"]}</td><td>{"Yes" if f["recoverable"] else "No"}</td><td>{"Recovered" if f["recovered"] else "Pending"}</td></tr>' for f in self._failures)}
</table>
</body>
</html>"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info("Recovery report generated: %s", path)
        return path

    def summary(self) -> dict[str, Any]:
        return {
            "total_failures": len(self._failures),
            "recovered": sum(1 for f in self._failures if f["recovered"]),
            "pending": sum(1 for f in self._failures if not f["recovered"] and f["recoverable"]),
            "unrecoverable": sum(1 for f in self._failures if not f["recoverable"]),
        }


class SLATracker:
    """Per-report SLA compliance tracking.

    Tracks migration duration and success rate against defined SLAs.
    """

    def __init__(self, max_duration_seconds: float = 300, min_fidelity: float = 80.0):
        self.max_duration = max_duration_seconds
        self.min_fidelity = min_fidelity
        self._records: list[dict[str, Any]] = []

    def record(
        self,
        report_name: str,
        duration_seconds: float,
        fidelity_percent: float,
        status: str = "success",
    ) -> dict[str, Any]:
        """Record a migration result against SLA."""
        duration_ok = duration_seconds <= self.max_duration
        fidelity_ok = fidelity_percent >= self.min_fidelity
        sla_met = duration_ok and fidelity_ok and status == "success"

        record = {
            "report": report_name,
            "duration_seconds": duration_seconds,
            "fidelity_percent": fidelity_percent,
            "status": status,
            "duration_sla": duration_ok,
            "fidelity_sla": fidelity_ok,
            "sla_met": sla_met,
            "timestamp": datetime.now().isoformat(),
        }
        self._records.append(record)
        return record

    def compliance_rate(self) -> float:
        """Return overall SLA compliance rate (0-100)."""
        if not self._records:
            return 100.0
        met = sum(1 for r in self._records if r["sla_met"])
        return met / len(self._records) * 100

    def violations(self) -> list[dict[str, Any]]:
        """Return records that violated SLA."""
        return [r for r in self._records if not r["sla_met"]]

    def summary(self) -> dict[str, Any]:
        return {
            "total_records": len(self._records),
            "sla_met": sum(1 for r in self._records if r["sla_met"]),
            "sla_violated": sum(1 for r in self._records if not r["sla_met"]),
            "compliance_rate": self.compliance_rate(),
            "avg_duration": (
                sum(r["duration_seconds"] for r in self._records) / len(self._records)
                if self._records else 0
            ),
            "avg_fidelity": (
                sum(r["fidelity_percent"] for r in self._records) / len(self._records)
                if self._records else 0
            ),
        }
