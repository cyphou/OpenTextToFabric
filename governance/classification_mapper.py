"""Classification mapper — OpenText categories → Purview sensitivity labels."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default mapping of common OT classification names to Purview labels
DEFAULT_SENSITIVITY_MAP: dict[str, str] = {
    "public": "General",
    "internal": "General",
    "confidential": "Confidential",
    "secret": "Highly Confidential",
    "top secret": "Highly Confidential",
    "restricted": "Confidential",
    "personal": "Confidential",
    "pii": "Confidential",
    "phi": "Highly Confidential",
    "financial": "Confidential",
    "legal": "Confidential",
}


class ClassificationMapper:
    """Maps OpenText classifications/categories to Purview sensitivity labels."""

    def __init__(
        self,
        sensitivity_map: dict[str, str] | None = None,
        default_label: str = "General",
    ):
        self.sensitivity_map = {
            k.lower(): v
            for k, v in (sensitivity_map or DEFAULT_SENSITIVITY_MAP).items()
        }
        self.default_label = default_label

    def map_category(self, category_name: str) -> str:
        """Map an OT category name to a Purview sensitivity label."""
        key = category_name.lower().strip()
        # Exact match
        if key in self.sensitivity_map:
            return self.sensitivity_map[key]
        # Partial match
        for pattern, label in self.sensitivity_map.items():
            if pattern in key or key in pattern:
                return label
        return self.default_label

    def map_metadata(
        self,
        metadata: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Map metadata entries to sensitivity labels.

        Args:
            metadata: List of metadata entries from metadata.json.

        Returns:
            List of {node_id, categories, sensitivity_label} dicts.
        """
        results: list[dict[str, Any]] = []

        for entry in metadata:
            node_id = entry.get("node_id", "")
            categories = entry.get("categories", [])

            # Use highest sensitivity from all categories
            labels = []
            for cat in categories:
                cat_name = cat.get("category_name", "")
                label = self.map_category(cat_name)
                labels.append(label)

                # Also check attribute values for classification hints
                for attr_name, attr_value in cat.get("attributes", {}).items():
                    if isinstance(attr_value, str):
                        attr_label = self.map_category(attr_value)
                        if attr_label != self.default_label:
                            labels.append(attr_label)

            # Pick highest sensitivity level
            final_label = self._highest_sensitivity(labels) if labels else self.default_label

            results.append({
                "node_id": node_id,
                "categories": [c.get("category_name", "") for c in categories],
                "sensitivity_label": final_label,
            })

        logger.info("Mapped %d metadata entries to sensitivity labels", len(results))
        return results

    def export_mapping(self, output_dir: str | Path) -> Path:
        """Export sensitivity label mapping to JSON."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "sensitivity_mapping.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "sensitivity_map": self.sensitivity_map,
                "default_label": self.default_label,
            }, f, indent=2)
        return path

    _SENSITIVITY_ORDER = ["General", "Confidential", "Highly Confidential"]

    def _highest_sensitivity(self, labels: list[str]) -> str:
        """Return the highest sensitivity label from a list."""
        max_idx = -1
        max_label = self.default_label
        for label in labels:
            if label in self._SENSITIVITY_ORDER:
                idx = self._SENSITIVITY_ORDER.index(label)
                if idx > max_idx:
                    max_idx = idx
                    max_label = label
        return max_label
