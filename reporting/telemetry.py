"""Telemetry dashboard — interactive 4-tab HTML observability.

Generates a rich single-page HTML dashboard with:
  Tab 1: Migration Overview (status counts, timelines)
  Tab 2: Expression Analysis (conversion rates, patterns)
  Tab 3: Visual Mapping (type distribution, coverage)
  Tab 4: Performance (step durations, bottlenecks)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TelemetryEvent:
    """Single telemetry event."""

    __slots__ = ("timestamp", "category", "action", "label", "value", "metadata")

    def __init__(
        self,
        category: str,
        action: str,
        label: str = "",
        value: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ):
        self.timestamp = datetime.now().isoformat()
        self.category = category
        self.action = action
        self.label = label
        self.value = value
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "category": self.category,
            "action": self.action,
            "label": self.label,
            "value": self.value,
            "metadata": self.metadata,
        }


class TelemetryCollector:
    """Collects telemetry events during migration."""

    def __init__(self):
        self._events: list[TelemetryEvent] = []
        self._step_timers: dict[str, float] = {}

    def track(
        self,
        category: str,
        action: str,
        label: str = "",
        value: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a telemetry event."""
        self._events.append(TelemetryEvent(category, action, label, value, metadata))

    def track_expression(self, original: str, converted: str, status: str, source: str = "") -> None:
        """Track an expression conversion event."""
        self.track("expression", status, source, metadata={
            "original_length": len(original),
            "converted_length": len(converted),
        })

    def track_visual(self, birt_type: str, pbi_type: str, element_name: str = "") -> None:
        """Track a visual mapping event."""
        self.track("visual", "mapped", element_name, metadata={
            "birt_type": birt_type,
            "pbi_type": pbi_type,
        })

    def track_measure(self, name: str, table: str, optimized: bool = False) -> None:
        """Track a measure creation event."""
        self.track("measure", "created", name, metadata={
            "table": table,
            "optimized": optimized,
        })

    def track_relationship(self, from_table: str, to_table: str, column: str, active: bool = True) -> None:
        """Track a relationship inference event."""
        self.track("relationship", "inferred", f"{from_table}->{to_table}", metadata={
            "column": column,
            "active": active,
        })

    def track_step(self, step_name: str, duration_seconds: float, status: str = "completed") -> None:
        """Track a pipeline step completion."""
        self.track("pipeline", status, step_name, duration_seconds)

    def track_error(self, category: str, error: str, context: str = "") -> None:
        """Track an error event."""
        self.track(category, "error", context, metadata={"error": error})

    def get_events(self, category: str | None = None) -> list[dict[str, Any]]:
        """Get events, optionally filtered by category."""
        events = self._events
        if category:
            events = [e for e in events if e.category == category]
        return [e.to_dict() for e in events]

    def summary(self) -> dict[str, Any]:
        """Return summary statistics."""
        by_category: dict[str, dict[str, int]] = {}
        for e in self._events:
            cat = by_category.setdefault(e.category, {})
            cat[e.action] = cat.get(e.action, 0) + 1

        return {
            "total_events": len(self._events),
            "categories": by_category,
        }

    def export_json(self, path: str | Path) -> Path:
        """Export all events to JSON."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in self._events], f, indent=2)
        return p


class TelemetryDashboard:
    """Generates an interactive 4-tab HTML telemetry dashboard."""

    def __init__(self, collector: TelemetryCollector):
        self.collector = collector

    def generate(self, output_path: str | Path) -> Path:
        """Generate the HTML dashboard."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        summary = self.collector.summary()
        events = self.collector.get_events()

        # Expression stats
        expr_events = [e for e in events if e["category"] == "expression"]
        expr_success = sum(1 for e in expr_events if e["action"] == "success")
        expr_partial = sum(1 for e in expr_events if e["action"] == "partial")
        expr_unsupported = sum(1 for e in expr_events if e["action"] == "unsupported")
        expr_total = len(expr_events) or 1

        # Visual stats
        visual_events = [e for e in events if e["category"] == "visual"]
        visual_types: dict[str, int] = {}
        for v in visual_events:
            pbi_type = v.get("metadata", {}).get("pbi_type", "unknown")
            visual_types[pbi_type] = visual_types.get(pbi_type, 0) + 1

        # Pipeline stats
        pipeline_events = [e for e in events if e["category"] == "pipeline"]

        # Error stats
        error_events = [e for e in events if e["action"] == "error"]

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Migration Telemetry Dashboard</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #f4f5f7; color: #333; }}
.header {{ background: linear-gradient(135deg, #0078d4, #005a9e); color: white; padding: 24px 32px; }}
.header h1 {{ font-size: 22px; font-weight: 600; }}
.header .subtitle {{ opacity: 0.85; font-size: 13px; margin-top: 4px; }}
.tabs {{ display: flex; background: #fff; border-bottom: 2px solid #e1e5e8; padding: 0 32px; }}
.tab {{ padding: 12px 20px; cursor: pointer; border-bottom: 3px solid transparent; font-size: 14px; color: #666; }}
.tab.active {{ color: #0078d4; border-bottom-color: #0078d4; font-weight: 600; }}
.tab:hover {{ color: #0078d4; }}
.tab-content {{ display: none; padding: 24px 32px; }}
.tab-content.active {{ display: block; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }}
.card {{ background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.card .label {{ font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }}
.card .value {{ font-size: 28px; font-weight: 700; margin-top: 4px; }}
.card .value.green {{ color: #107c10; }}
.card .value.orange {{ color: #ff8c00; }}
.card .value.red {{ color: #d13438; }}
.card .value.blue {{ color: #0078d4; }}
.bar {{ display: flex; height: 24px; border-radius: 4px; overflow: hidden; margin: 8px 0; }}
.bar .segment {{ transition: width 0.3s; }}
.bar .success {{ background: #107c10; }}
.bar .partial {{ background: #ff8c00; }}
.bar .unsupported {{ background: #d13438; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
th {{ background: #f0f2f5; text-align: left; padding: 10px 16px; font-size: 12px; text-transform: uppercase; color: #666; }}
td {{ padding: 10px 16px; border-top: 1px solid #eee; font-size: 13px; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }}
.badge.success {{ background: #dff6dd; color: #107c10; }}
.badge.warning {{ background: #fff4ce; color: #8a6d00; }}
.badge.error {{ background: #fde7e9; color: #d13438; }}
</style>
</head>
<body>
<div class="header">
    <h1>Migration Telemetry Dashboard</h1>
    <div class="subtitle">Generated {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} &bull; {summary['total_events']} events</div>
</div>

<div class="tabs">
    <div class="tab active" onclick="switchTab(0)">Overview</div>
    <div class="tab" onclick="switchTab(1)">Expressions</div>
    <div class="tab" onclick="switchTab(2)">Visuals</div>
    <div class="tab" onclick="switchTab(3)">Performance</div>
</div>

<div class="tab-content active" id="tab0">
    <div class="cards">
        <div class="card"><div class="label">Total Events</div><div class="value blue">{summary['total_events']}</div></div>
        <div class="card"><div class="label">Expressions</div><div class="value green">{len(expr_events)}</div></div>
        <div class="card"><div class="label">Visuals Mapped</div><div class="value blue">{len(visual_events)}</div></div>
        <div class="card"><div class="label">Errors</div><div class="value {'red' if error_events else 'green'}">{len(error_events)}</div></div>
    </div>
    <h3 style="margin-bottom:12px">Category Breakdown</h3>
    <table>
        <tr><th>Category</th><th>Actions</th><th>Count</th></tr>
        {"".join(f'<tr><td>{cat}</td><td>{", ".join(actions.keys())}</td><td>{sum(actions.values())}</td></tr>' for cat, actions in summary.get("categories", {}).items())}
    </table>
</div>

<div class="tab-content" id="tab1">
    <div class="cards">
        <div class="card"><div class="label">Success</div><div class="value green">{expr_success}</div></div>
        <div class="card"><div class="label">Partial</div><div class="value orange">{expr_partial}</div></div>
        <div class="card"><div class="label">Unsupported</div><div class="value red">{expr_unsupported}</div></div>
        <div class="card"><div class="label">Conversion Rate</div><div class="value blue">{expr_success * 100 // expr_total}%</div></div>
    </div>
    <div class="bar">
        <div class="segment success" style="width:{expr_success * 100 / expr_total:.1f}%" title="Success: {expr_success}"></div>
        <div class="segment partial" style="width:{expr_partial * 100 / expr_total:.1f}%" title="Partial: {expr_partial}"></div>
        <div class="segment unsupported" style="width:{expr_unsupported * 100 / expr_total:.1f}%" title="Unsupported: {expr_unsupported}"></div>
    </div>
</div>

<div class="tab-content" id="tab2">
    <div class="cards">
        <div class="card"><div class="label">Total Visuals</div><div class="value blue">{len(visual_events)}</div></div>
        <div class="card"><div class="label">Unique Types</div><div class="value green">{len(visual_types)}</div></div>
    </div>
    <h3 style="margin:16px 0 12px">Visual Type Distribution</h3>
    <table>
        <tr><th>PBI Visual Type</th><th>Count</th></tr>
        {"".join(f'<tr><td>{vt}</td><td>{ct}</td></tr>' for vt, ct in sorted(visual_types.items(), key=lambda x: -x[1]))}
    </table>
</div>

<div class="tab-content" id="tab3">
    <h3 style="margin-bottom:12px">Pipeline Steps</h3>
    <table>
        <tr><th>Step</th><th>Status</th><th>Duration (s)</th></tr>
        {"".join(f'<tr><td>{e["label"]}</td><td><span class="badge {e["action"]}">{e["action"]}</span></td><td>{e["value"]:.2f}</td></tr>' for e in pipeline_events)}
    </table>
    {"<h3 style='margin:24px 0 12px'>Errors</h3><table><tr><th>Category</th><th>Context</th><th>Error</th></tr>" + "".join(f'<tr><td>{e["category"]}</td><td>{e["label"]}</td><td>{e.get("metadata", {}).get("error", "")}</td></tr>' for e in error_events) + "</table>" if error_events else ""}
</div>

<script>
function switchTab(n) {{
    document.querySelectorAll('.tab').forEach((t,i) => t.classList.toggle('active', i===n));
    document.querySelectorAll('.tab-content').forEach((c,i) => c.classList.toggle('active', i===n));
}}
</script>
</body>
</html>"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info("Telemetry dashboard generated: %s", path)
        return path


class MetricsExporter:
    """Export metrics in multiple formats (JSON, Prometheus, Azure Monitor)."""

    def __init__(self, collector: TelemetryCollector):
        self.collector = collector

    def export_json(self, path: str | Path) -> Path:
        """Export metrics as JSON."""
        return self.collector.export_json(path)

    def export_prometheus(self, path: str | Path) -> Path:
        """Export metrics in Prometheus text format."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        summary = self.collector.summary()
        lines = [
            "# HELP migration_events_total Total migration events",
            "# TYPE migration_events_total counter",
            f"migration_events_total {summary['total_events']}",
        ]
        for cat, actions in summary.get("categories", {}).items():
            for action, count in actions.items():
                lines.append(f'migration_events{{category="{cat}",action="{action}"}} {count}')

        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return p

    def export_azure_monitor(self) -> dict[str, Any]:
        """Format metrics for Azure Monitor custom metrics API."""
        summary = self.collector.summary()
        metrics = []
        for cat, actions in summary.get("categories", {}).items():
            for action, count in actions.items():
                metrics.append({
                    "name": f"migration.{cat}.{action}",
                    "value": count,
                    "dimensions": {"category": cat, "action": action},
                })
        return {"metrics": metrics, "timestamp": datetime.now().isoformat()}
