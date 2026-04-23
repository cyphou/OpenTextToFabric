"""Purview retention mapper — OpenText retention policies → Purview retention labels."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default retention period mapping (OT policy name keywords → days)
DEFAULT_RETENTION_PERIODS: dict[str, int] = {
    "permanent": -1,  # -1 = never delete
    "archive": 3650,  # 10 years
    "long_term": 2555,  # 7 years
    "financial": 2555,  # 7 years
    "legal": 3650,  # 10 years
    "regulatory": 2555,  # 7 years
    "standard": 1095,  # 3 years
    "short_term": 365,  # 1 year
    "temporary": 90,  # 90 days
    "draft": 30,  # 30 days
}


class PurviewMapper:
    """Maps OpenText retention policies to Purview retention labels."""

    def __init__(
        self,
        retention_map: dict[str, int] | None = None,
        default_days: int = 1095,
    ):
        self.retention_map = {
            k.lower(): v
            for k, v in (retention_map or DEFAULT_RETENTION_PERIODS).items()
        }
        self.default_days = default_days

    def map_retention_policy(self, policy_name: str) -> dict[str, Any]:
        """Map an OT retention policy name to a Purview retention label spec."""
        key = policy_name.lower().strip()

        # Exact match
        days = self.retention_map.get(key)
        if days is None:
            # Partial match
            for pattern, d in self.retention_map.items():
                if pattern in key:
                    days = d
                    break

        if days is None:
            days = self.default_days

        return {
            "source_policy": policy_name,
            "retention_days": days,
            "purview_label": self._days_to_label(days),
            "action_after_retention": "delete" if days > 0 else "retain_forever",
        }

    def map_dctm_lifecycles(
        self,
        retention_data: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Map Documentum lifecycle/retention entries to Purview labels.

        Args:
            retention_data: List from retention.json.

        Returns:
            List of mapped retention entries.
        """
        results: list[dict[str, Any]] = []

        for entry in retention_data:
            object_id = entry.get("object_id", "")
            policy_id = entry.get("policy_id", "")
            state = entry.get("current_state", -1)

            # Map lifecycle state to retention
            mapped = self.map_retention_policy(policy_id)
            mapped["object_id"] = object_id
            mapped["lifecycle_state"] = state
            results.append(mapped)

        logger.info("Mapped %d lifecycle entries to retention labels", len(results))
        return results

    def map_cs_retention(
        self,
        metadata: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Map Content Server metadata with retention categories."""
        results: list[dict[str, Any]] = []

        for entry in metadata:
            node_id = entry.get("node_id", "")
            for cat in entry.get("categories", []):
                cat_name = cat.get("category_name", "").lower()
                if any(kw in cat_name for kw in ("retention", "archive", "lifecycle", "disposal")):
                    mapped = self.map_retention_policy(cat_name)
                    mapped["node_id"] = node_id
                    mapped["category_name"] = cat.get("category_name", "")
                    results.append(mapped)

        return results

    def generate_purview_config(
        self,
        mapped_entries: list[dict[str, Any]],
        output_dir: str | Path,
    ) -> Path:
        """Generate Purview retention label configuration file."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # Deduplicate labels
        labels: dict[str, dict[str, Any]] = {}
        for entry in mapped_entries:
            label = entry.get("purview_label", "")
            if label and label not in labels:
                labels[label] = {
                    "label_name": label,
                    "retention_days": entry.get("retention_days", self.default_days),
                    "action": entry.get("action_after_retention", "delete"),
                }

        config = {
            "retention_labels": list(labels.values()),
            "total_mapped_items": len(mapped_entries),
        }

        path = out / "purview_retention_config.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return path

    @staticmethod
    def _days_to_label(days: int) -> str:
        """Convert retention days to a human-readable label name."""
        if days < 0:
            return "Retain_Forever"
        elif days <= 30:
            return "Short_Term_30d"
        elif days <= 90:
            return "Short_Term_90d"
        elif days <= 365:
            return "Standard_1yr"
        elif days <= 1095:
            return "Standard_3yr"
        elif days <= 2555:
            return "Long_Term_7yr"
        else:
            return "Archive_10yr"
