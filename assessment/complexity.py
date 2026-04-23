"""Complexity scoring for migration artifacts.

Scores content areas and reports by complexity to guide wave planning
and effort estimation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Complexity weights per feature
_WEIGHTS = {
    "datasets": 1.0,
    "connections": 2.0,
    "computed_columns": 3.0,
    "expressions": 2.0,
    "parameters": 1.5,
    "visuals": 0.5,
    "charts": 1.5,
    "tables": 1.0,
    "crosstabs": 3.0,
    "subreports": 4.0,
    "drill_through": 3.0,
    "conditional_format": 2.0,
    "acl_depth": 2.0,
    "group_nesting": 1.5,
}

# Thresholds for complexity bands
_THRESHOLDS = {
    "low": 10,
    "medium": 30,
    "high": 60,
    # anything above high is "critical"
}


class ComplexityScorer:
    """Scores migration complexity for reports and content areas."""

    def score_report(self, report_info: dict[str, Any]) -> dict[str, Any]:
        """Score a single report's complexity.

        Args:
            report_info: Dict from ContentScanner.scan_report_file().

        Returns:
            Dict with score, band, breakdown, and recommendations.
        """
        breakdown: dict[str, float] = {}
        total = 0.0

        # Count-based factors
        for factor, weight in _WEIGHTS.items():
            count = report_info.get(factor, 0)
            if isinstance(count, (int, float)) and count > 0:
                points = count * weight
                breakdown[factor] = points
                total += points

        # Extra points for multi-data-source reports
        ds_count = report_info.get("data_sources", 0)
        if ds_count > 1:
            extra = (ds_count - 1) * 5.0
            breakdown["multi_datasource"] = extra
            total += extra

        band = self._band(total)
        effort = self._estimate_effort(total, band)

        return {
            "score": round(total, 1),
            "band": band,
            "breakdown": breakdown,
            "effort_hours": effort,
            "recommendations": self._recommendations(report_info, band),
            "wave": self._suggest_wave(band),
        }

    def score_batch(self, reports: list[dict[str, Any]]) -> dict[str, Any]:
        """Score a batch of reports and produce portfolio summary."""
        scored = []
        for r in reports:
            if "error" in r:
                scored.append({"path": r.get("path", ""), "error": r["error"]})
                continue
            result = self.score_report(r)
            result["path"] = r.get("path", "")
            result["name"] = r.get("name", "")
            scored.append(result)

        # Portfolio summary
        bands: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        total_effort = 0.0
        for s in scored:
            band = s.get("band", "")
            if band in bands:
                bands[band] += 1
            total_effort += s.get("effort_hours", 0)

        waves = self._plan_waves(scored)

        return {
            "reports": scored,
            "portfolio": {
                "total": len(scored),
                "by_band": bands,
                "total_effort_hours": round(total_effort, 1),
                "waves": waves,
            },
        }

    @staticmethod
    def _band(score: float) -> str:
        """Map score to complexity band."""
        if score <= _THRESHOLDS["low"]:
            return "low"
        if score <= _THRESHOLDS["medium"]:
            return "medium"
        if score <= _THRESHOLDS["high"]:
            return "high"
        return "critical"

    @staticmethod
    def _estimate_effort(score: float, band: str) -> float:
        """Estimate migration effort in hours."""
        base = {"low": 0.5, "medium": 2.0, "high": 4.0, "critical": 8.0}
        return round(base.get(band, 2.0) + score * 0.1, 1)

    @staticmethod
    def _recommendations(info: dict[str, Any], band: str) -> list[str]:
        """Generate recommendations based on report analysis."""
        recs: list[str] = []
        if info.get("data_sources", 0) > 2:
            recs.append("Multiple data sources detected — consider composite model")
        if info.get("computed_columns", 0) > 5:
            recs.append("Many computed columns — review DAX conversion accuracy")
        if info.get("expressions", 0) > 20:
            recs.append("High expression count — allocate extra validation time")
        if band in ("high", "critical"):
            recs.append("Complex report — recommend manual review after migration")
        if info.get("parameters", 0) > 0:
            recs.append("Report parameters detected — verify slicer/filter wiring")
        return recs

    @staticmethod
    def _suggest_wave(band: str) -> int:
        """Suggest migration wave number based on complexity."""
        return {"low": 1, "medium": 1, "high": 2, "critical": 3}.get(band, 2)

    @staticmethod
    def _plan_waves(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Group reports into migration waves."""
        waves: dict[int, list[str]] = {}
        for s in scored:
            wave = s.get("wave", 2)
            name = s.get("name", s.get("path", ""))
            waves.setdefault(wave, []).append(name)

        return [
            {"wave": w, "reports": names, "count": len(names)}
            for w, names in sorted(waves.items())
        ]
