"""Regression suite — snapshot generation and drift detection.

Captures migration output snapshots and detects regressions when
re-running migrations against updated code.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MigrationSnapshot:
    """Captures the state of a migration output for regression testing."""

    def __init__(self, name: str, output_dir: str | Path):
        self.name = name
        self.output_dir = Path(output_dir)
        self.timestamp = datetime.now().isoformat()
        self._artifacts: dict[str, dict[str, Any]] = {}

    def capture(self) -> dict[str, Any]:
        """Capture snapshot of all output artifacts."""
        if not self.output_dir.exists():
            return {"name": self.name, "artifacts": {}, "timestamp": self.timestamp}

        for f in sorted(self.output_dir.rglob("*")):
            if f.is_file():
                rel = str(f.relative_to(self.output_dir)).replace("\\", "/")
                content = f.read_bytes()
                self._artifacts[rel] = {
                    "size": len(content),
                    "hash": hashlib.sha256(content).hexdigest(),
                    "extension": f.suffix,
                }
                # For JSON/TMDL files, capture structure
                if f.suffix in (".json", ".tmdl"):
                    try:
                        text = content.decode("utf-8")
                        if f.suffix == ".json":
                            parsed = json.loads(text)
                            self._artifacts[rel]["keys"] = (
                                sorted(parsed.keys()) if isinstance(parsed, dict)
                                else f"list[{len(parsed)}]"
                            )
                        elif f.suffix == ".tmdl":
                            lines = text.splitlines()
                            self._artifacts[rel]["lines"] = len(lines)
                            self._artifacts[rel]["tables"] = sum(
                                1 for l in lines if l.startswith("table ")
                            )
                            self._artifacts[rel]["measures"] = sum(
                                1 for l in lines if l.strip().startswith("measure ")
                            )
                    except Exception:
                        pass

        return {
            "name": self.name,
            "timestamp": self.timestamp,
            "artifact_count": len(self._artifacts),
            "artifacts": self._artifacts,
        }

    def save(self, snapshot_dir: str | Path) -> Path:
        """Save snapshot to disk."""
        snap = self.capture()
        out = Path(snapshot_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2)
        logger.info("Snapshot saved: %s (%d artifacts)", path, len(self._artifacts))
        return path


class RegressionDetector:
    """Compares two snapshots to detect regressions."""

    def compare(
        self,
        baseline: dict[str, Any],
        current: dict[str, Any],
    ) -> dict[str, Any]:
        """Compare baseline vs current snapshot.

        Returns:
            Dict with added, removed, changed, unchanged counts and details.
        """
        base_arts = baseline.get("artifacts", {})
        curr_arts = current.get("artifacts", {})
        base_keys = set(base_arts.keys())
        curr_keys = set(curr_arts.keys())

        added = sorted(curr_keys - base_keys)
        removed = sorted(base_keys - curr_keys)
        common = sorted(base_keys & curr_keys)

        changed: list[dict[str, Any]] = []
        unchanged: list[str] = []

        for key in common:
            b = base_arts[key]
            c = curr_arts[key]
            if b.get("hash") != c.get("hash"):
                diff: dict[str, Any] = {"file": key}
                if b.get("size") != c.get("size"):
                    diff["size_change"] = c.get("size", 0) - b.get("size", 0)
                if b.get("lines") != c.get("lines") and b.get("lines") is not None:
                    diff["line_change"] = c.get("lines", 0) - b.get("lines", 0)
                if b.get("measures") != c.get("measures") and b.get("measures") is not None:
                    diff["measure_change"] = c.get("measures", 0) - b.get("measures", 0)
                if b.get("tables") != c.get("tables") and b.get("tables") is not None:
                    diff["table_change"] = c.get("tables", 0) - b.get("tables", 0)
                changed.append(diff)
            else:
                unchanged.append(key)

        has_regression = bool(removed) or any(
            d.get("measure_change", 0) < 0 or d.get("table_change", 0) < 0
            for d in changed
        )

        return {
            "baseline": baseline.get("name", ""),
            "current": current.get("name", ""),
            "baseline_timestamp": baseline.get("timestamp", ""),
            "current_timestamp": current.get("timestamp", ""),
            "has_regression": has_regression,
            "added": added,
            "removed": removed,
            "changed": changed,
            "unchanged_count": len(unchanged),
            "summary": {
                "added": len(added),
                "removed": len(removed),
                "changed": len(changed),
                "unchanged": len(unchanged),
            },
        }


class VisualDiff:
    """Side-by-side visual comparison of BIRT source vs PBI output."""

    def compare_visuals(
        self,
        birt_visuals: list[dict[str, Any]],
        pbi_visuals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compare BIRT source visuals with generated PBI visuals.

        Returns:
            Dict with matched, unmatched_birt, unmatched_pbi, and fidelity score.
        """
        matched: list[dict[str, Any]] = []
        unmatched_birt: list[dict[str, Any]] = []
        used_pbi: set[int] = set()

        for bv in birt_visuals:
            bname = bv.get("name", "")
            btype = bv.get("element_type", "")
            best_match = None
            best_idx = -1

            for i, pv in enumerate(pbi_visuals):
                if i in used_pbi:
                    continue
                pname = pv.get("title", pv.get("name", ""))
                if bname and pname and bname.lower() == pname.lower():
                    best_match = pv
                    best_idx = i
                    break

            if best_match is not None:
                used_pbi.add(best_idx)
                matched.append({
                    "birt_name": bname,
                    "birt_type": btype,
                    "pbi_type": best_match.get("visual_type", ""),
                    "pbi_name": best_match.get("title", best_match.get("name", "")),
                    "properties_compared": self._compare_properties(bv, best_match),
                })
            else:
                unmatched_birt.append({"name": bname, "type": btype})

        unmatched_pbi = [
            {"name": pv.get("title", pv.get("name", "")), "type": pv.get("visual_type", "")}
            for i, pv in enumerate(pbi_visuals) if i not in used_pbi
        ]

        total = len(birt_visuals) or 1
        fidelity = len(matched) / total * 100

        return {
            "matched": matched,
            "unmatched_birt": unmatched_birt,
            "unmatched_pbi": unmatched_pbi,
            "fidelity_percent": round(fidelity, 1),
            "summary": {
                "matched": len(matched),
                "unmatched_birt": len(unmatched_birt),
                "unmatched_pbi": len(unmatched_pbi),
            },
        }

    def _compare_properties(
        self,
        birt: dict[str, Any],
        pbi: dict[str, Any],
    ) -> dict[str, Any]:
        """Compare properties between BIRT and PBI visual."""
        result: dict[str, Any] = {}
        bprops = birt.get("properties", {})
        pconfig = pbi.get("config", {})

        if "width" in bprops:
            result["width"] = {
                "birt": bprops.get("width"),
                "pbi": pconfig.get("layouts", [{}])[0].get("position", {}).get("width") if pconfig.get("layouts") else None,
            }
        if "dataSet" in bprops:
            result["data_binding"] = {
                "birt_dataset": bprops.get("dataSet"),
                "pbi_has_query": bool(pbi.get("query_state")),
            }

        return result


class ComparisonReport:
    """Generate side-by-side comparison HTML report."""

    def generate(
        self,
        visual_diff: dict[str, Any],
        regression: dict[str, Any] | None = None,
        output_path: str | Path = "comparison_report.html",
    ) -> Path:
        """Generate HTML comparison report."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        matched = visual_diff.get("matched", [])
        fidelity = visual_diff.get("fidelity_percent", 0)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Migration Comparison Report</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; margin: 24px; background: #f9f9f9; }}
h1 {{ color: #0078d4; }}
.score {{ font-size: 48px; font-weight: 700; color: {'#107c10' if fidelity >= 80 else '#ff8c00' if fidelity >= 50 else '#d13438'}; }}
table {{ width: 100%; border-collapse: collapse; margin: 16px 0; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
th {{ background: #f0f2f5; padding: 10px; text-align: left; font-size: 12px; text-transform: uppercase; }}
td {{ padding: 10px; border-top: 1px solid #eee; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }}
.match {{ background: #dff6dd; color: #107c10; }}
.miss {{ background: #fde7e9; color: #d13438; }}
</style>
</head>
<body>
<h1>BIRT → Power BI Comparison Report</h1>
<p>Visual Fidelity Score:</p>
<div class="score">{fidelity:.1f}%</div>

<h2>Matched Visuals ({len(matched)})</h2>
<table>
<tr><th>BIRT Element</th><th>BIRT Type</th><th>PBI Visual</th><th>PBI Type</th></tr>
{"".join(f'<tr><td>{m["birt_name"]}</td><td>{m["birt_type"]}</td><td>{m["pbi_name"]}</td><td>{m["pbi_type"]}</td></tr>' for m in matched)}
</table>

<h2>Unmatched BIRT Elements ({len(visual_diff.get("unmatched_birt", []))})</h2>
<table>
<tr><th>Name</th><th>Type</th><th>Status</th></tr>
{"".join(f'<tr><td>{u["name"]}</td><td>{u["type"]}</td><td><span class="badge miss">Not migrated</span></td></tr>' for u in visual_diff.get("unmatched_birt", []))}
</table>

{"<h2>Regression Analysis</h2><table><tr><th>Metric</th><th>Value</th></tr>" + f'<tr><td>Files Added</td><td>{regression["summary"]["added"]}</td></tr><tr><td>Files Removed</td><td>{regression["summary"]["removed"]}</td></tr><tr><td>Files Changed</td><td>{regression["summary"]["changed"]}</td></tr><tr><td>Has Regression</td><td>{"Yes" if regression["has_regression"] else "No"}</td></tr></table>' if regression else ""}
</body>
</html>"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info("Comparison report generated: %s", path)
        return path
