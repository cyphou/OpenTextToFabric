"""BIRT drill-through and sub-report → Power BI drill-through pages and bookmarks."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DrillThroughConverter:
    """Converts BIRT hyperlinks and sub-report references to PBI drill-through pages.

    BIRT supports:
    - Hyperlink actions on data elements (link to another report with parameters)
    - Sub-report inclusions (embedded report-within-report)
    - Drill-down via grouped data levels

    Power BI equivalents:
    - Drill-through pages (filter by context value)
    - Bookmarks (for navigation patterns)
    - Cross-report drill-through (to another .pbip)
    """

    def convert_hyperlinks(
        self,
        hyperlinks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Convert BIRT hyperlinks to PBI drill-through configuration.

        Args:
            hyperlinks: List of BIRT hyperlink dicts, each with:
                - target_report: str (report name or path)
                - parameters: dict (param name → value expression)
                - source_column: str (column that triggers the drill)
                - action: str ("drillthrough" | "bookmark" | "url")

        Returns:
            Dict with drill_pages and bookmarks lists.
        """
        drill_pages: list[dict[str, Any]] = []
        bookmarks: list[dict[str, Any]] = []
        cross_report: list[dict[str, Any]] = []

        for link in hyperlinks:
            action = link.get("action", "drillthrough")
            target = link.get("target_report", "")
            params = link.get("parameters", {})
            source = link.get("source_column", "")

            if action == "url":
                # External URL — keep as-is, add to web URL action
                bookmarks.append({
                    "name": f"Link_{source}",
                    "type": "webUrl",
                    "url": target,
                    "source_column": source,
                })
            elif action == "bookmark":
                bookmarks.append({
                    "name": target or f"Bookmark_{source}",
                    "type": "bookmark",
                    "source_column": source,
                })
            elif self._is_cross_report(target):
                # Cross-report drill-through
                cross_report.append({
                    "target_report": target,
                    "parameters": self._convert_params(params),
                    "source_column": source,
                })
            else:
                # Same-report drill-through page
                drill_pages.append(self._build_drill_page(target, params, source))

        logger.info(
            "Drill-through conversion: %d pages, %d bookmarks, %d cross-report",
            len(drill_pages), len(bookmarks), len(cross_report),
        )

        return {
            "drill_pages": drill_pages,
            "bookmarks": bookmarks,
            "cross_report": cross_report,
        }

    def convert_subreports(
        self,
        subreports: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert BIRT sub-report inclusions to PBI drill-through pages.

        Sub-reports in BIRT are embedded report fragments with their own data sets.
        In PBI, these become separate pages with drill-through filters.

        Args:
            subreports: List of sub-report dicts with:
                - name: str
                - parameters: dict
                - data_set: str (sub-report's dataset name)

        Returns:
            List of drill-through page configurations.
        """
        pages: list[dict[str, Any]] = []

        for sub in subreports:
            name = sub.get("name", f"SubReport_{len(pages) + 1}")
            params = sub.get("parameters", {})
            data_set = sub.get("data_set", "")

            page: dict[str, Any] = {
                "name": name,
                "displayName": name.replace("_", " "),
                "type": "drillThrough",
                "filters": [],
                "source_dataset": data_set,
            }

            # Convert parameters to drill-through filters
            for param_name, param_expr in params.items():
                page["filters"].append({
                    "column": param_name,
                    "filterType": "drillThrough",
                    "expression": param_expr,
                })

            pages.append(page)

        logger.info("Converted %d sub-reports to drill-through pages", len(pages))
        return pages

    def _build_drill_page(
        self,
        target: str,
        params: dict[str, str],
        source_column: str,
    ) -> dict[str, Any]:
        """Build a single drill-through page config."""
        page_name = target or f"DrillPage_{source_column}"
        filters = []

        for param_name, param_value in params.items():
            filters.append({
                "column": param_name,
                "filterType": "drillThrough",
                "value": param_value,
            })

        # If no explicit params, use source column as the drill filter
        if not filters and source_column:
            filters.append({
                "column": source_column,
                "filterType": "drillThrough",
            })

        return {
            "name": page_name,
            "displayName": page_name.replace("_", " "),
            "type": "drillThrough",
            "filters": filters,
            "source_column": source_column,
        }

    @staticmethod
    def _convert_params(params: dict[str, str]) -> dict[str, str]:
        """Convert BIRT parameter expressions to PBI filter values."""
        converted: dict[str, str] = {}
        for name, expr in params.items():
            # Strip row[] wrappers
            clean = expr
            if 'row["' in clean:
                import re
                m = re.search(r'row\["([^"]+)"\]', clean)
                if m:
                    clean = f"[{m.group(1)}]"
            converted[name] = clean
        return converted

    @staticmethod
    def _is_cross_report(target: str) -> bool:
        """Check if a target reference points to a different report."""
        if not target:
            return False
        return target.endswith(".rptdesign") or "/" in target or "\\" in target


def generate_drill_page_json(
    drill_config: dict[str, Any],
    page_index: int = 0,
) -> dict[str, Any]:
    """Generate a PBI page JSON for a drill-through page.

    Args:
        drill_config: Single drill page config from DrillThroughConverter.
        page_index: Page ordinal (for unique IDs).

    Returns:
        PBIR page JSON structure.
    """
    filters_json = []
    for f in drill_config.get("filters", []):
        filters_json.append({
            "type": "Categorical",
            "target": {
                "Column": {
                    "Expression": {"SourceRef": {"Entity": ""}},
                    "Property": f.get("column", ""),
                },
            },
            "filterType": 1,  # Advanced filter
        })

    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.0.0/schema.json",
        "name": f"DrillPage_{page_index}",
        "displayName": drill_config.get("displayName", f"Drill {page_index}"),
        "displayOption": 0,
        "width": 1280,
        "height": 720,
        "type": 1,  # Drill-through page type
        "filters": filters_json,
    }


def generate_page_navigator(
    pages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate a page navigator visual config for multi-page reports.

    Creates a navigation bar visual that links to all pages. Useful when
    migrating BIRT reports with many sub-reports or drill-through targets.

    Args:
        pages: List of page configs (each must have 'name' and 'displayName').

    Returns:
        PBI visual config for page navigation.
    """
    buttons: list[dict[str, Any]] = []
    for page in pages:
        buttons.append({
            "name": page.get("displayName", page.get("name", "")),
            "target_page": page.get("name", ""),
            "type": "pageNavigation",
        })

    return {
        "visual_type": "pageNavigator",
        "name": "PageNavigator",
        "position": {"x": 0, "y": 0, "z": 1000},
        "size": {"width": 1280, "height": 40},
        "config": {
            "buttons": buttons,
            "orientation": "horizontal",
            "style": "tabs",
        },
    }


class DrillPageBuilder:
    """Builds complete drill-through pages with visuals for PBIP output.

    Integrates with PBIPGenerator to add drill-through pages to the report.
    """

    def __init__(self, converter: DrillThroughConverter | None = None):
        self.converter = converter or DrillThroughConverter()

    def build_pages(
        self,
        hyperlinks: list[dict[str, Any]],
        subreports: list[dict[str, Any]],
        visuals_by_page: dict[str, list[dict[str, Any]]] | None = None,
    ) -> list[dict[str, Any]]:
        """Build drill-through page definitions from hyperlinks and sub-reports.

        Args:
            hyperlinks: BIRT hyperlink actions.
            subreports: BIRT sub-report inclusions.
            visuals_by_page: Optional mapping of page name → visuals for that page.

        Returns:
            List of complete page definitions for PBIP generation.
        """
        pages: list[dict[str, Any]] = []

        # Convert hyperlinks → drill pages
        if hyperlinks:
            result = self.converter.convert_hyperlinks(hyperlinks)
            for i, drill in enumerate(result.get("drill_pages", [])):
                page = generate_drill_page_json(drill, page_index=i + 1)
                page["visuals"] = (visuals_by_page or {}).get(drill.get("name", ""), [])
                pages.append(page)

        # Convert sub-reports → drill pages
        if subreports:
            sub_pages = self.converter.convert_subreports(subreports)
            offset = len(pages)
            for i, sub in enumerate(sub_pages):
                page = generate_drill_page_json(sub, page_index=offset + i + 1)
                page["visuals"] = (visuals_by_page or {}).get(sub.get("name", ""), [])
                pages.append(page)

        logger.info("Built %d drill-through pages", len(pages))
        return pages
