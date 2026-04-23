"""Migration strategy recommendation — Import vs DirectLake, big bang vs waves."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class StrategyAdvisor:
    """Recommends migration strategy based on assessment data."""

    def recommend(
        self,
        scan_result: dict[str, Any],
        complexity_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate migration strategy recommendation.

        Args:
            scan_result: Output from ContentScanner.
            complexity_result: Optional output from ComplexityScorer.

        Returns:
            Dict with strategy, rationale, and action items.
        """
        summary = scan_result.get("summary", {})
        portfolio = (complexity_result or {}).get("portfolio", {})

        total_reports = summary.get("total_reports", 0) + max(
            portfolio.get("total", 0), 0
        )
        bands = portfolio.get("by_band", {})
        critical = bands.get("critical", 0)
        high = bands.get("high", 0)
        total_effort = portfolio.get("total_effort_hours", 0)

        # Determine migration approach
        if total_reports <= 5 and critical == 0:
            approach = "big_bang"
            approach_label = "Big Bang"
            approach_rationale = (
                "Small portfolio with no critical-complexity reports. "
                "Migrate all at once for fastest delivery."
            )
        elif critical > 0 or high > 3:
            approach = "phased_waves"
            approach_label = "Phased Waves"
            approach_rationale = (
                f"{critical} critical + {high} high-complexity reports. "
                "Use wave-based approach: simple reports first, complex last."
            )
        else:
            approach = "iterative"
            approach_label = "Iterative"
            approach_rationale = (
                "Moderate portfolio. Migrate in 2-3 iterations with "
                "validation checkpoints."
            )

        # Determine semantic model mode
        ds_count = summary.get("total_connections", 0)
        if ds_count <= 1:
            model_mode = "import"
            model_rationale = "Single data source — Import mode for best performance"
        elif ds_count <= 3:
            model_mode = "directlake"
            model_rationale = (
                f"{ds_count} data sources — DirectLake mode if all sources "
                "land in Lakehouse; otherwise Composite"
            )
        else:
            model_mode = "composite"
            model_rationale = f"{ds_count} data sources — Composite model recommended"

        # Build action items
        actions = self._build_actions(
            approach, model_mode, total_reports, critical, total_effort
        )

        return {
            "approach": approach,
            "approach_label": approach_label,
            "approach_rationale": approach_rationale,
            "model_mode": model_mode,
            "model_rationale": model_rationale,
            "estimated_effort_hours": total_effort,
            "total_reports": total_reports,
            "actions": actions,
        }

    @staticmethod
    def _build_actions(
        approach: str,
        model_mode: str,
        total: int,
        critical: int,
        effort: float,
    ) -> list[dict[str, str]]:
        """Build ordered action items for the recommended strategy."""
        actions: list[dict[str, str]] = []

        actions.append({
            "step": "1",
            "action": "Run assessment",
            "detail": "python migrate.py --assess-only to generate readiness report",
        })

        if approach == "phased_waves":
            actions.append({
                "step": "2",
                "action": "Plan waves",
                "detail": f"Prioritize {total - critical} simpler reports for Wave 1",
            })
            actions.append({
                "step": "3",
                "action": "Pilot migration",
                "detail": "Migrate 2-3 low-complexity reports as proof-of-concept",
            })
        else:
            actions.append({
                "step": "2",
                "action": "Pilot migration",
                "detail": "Migrate 1-2 representative reports for validation",
            })

        actions.append({
            "step": str(len(actions) + 1),
            "action": "Validate output",
            "detail": "Open .pbip in Power BI Desktop, verify visuals and measures",
        })

        if model_mode != "import":
            actions.append({
                "step": str(len(actions) + 1),
                "action": f"Configure {model_mode} model",
                "detail": "Set up data source connections in Fabric workspace",
            })

        actions.append({
            "step": str(len(actions) + 1),
            "action": "Deploy to Fabric",
            "detail": "python migrate.py --deploy --workspace-id <id>",
        })

        actions.append({
            "step": str(len(actions) + 1),
            "action": "UAT & cutover",
            "detail": f"Estimated effort: {effort}h across {total} report(s)",
        })

        return actions
