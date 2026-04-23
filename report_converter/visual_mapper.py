"""BIRT visual type → Power BI visual mapping."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# BIRT element type / chart type → Power BI visual type mapping
VISUAL_TYPE_MAP: dict[str, str] = {
    # Tables
    "table": "tableEx",
    "list": "tableEx",
    "grid": "tableEx",
    # Charts
    "bar": "clusteredBarChart",
    "stackedbar": "stackedBarChart",
    "line": "lineChart",
    "area": "areaChart",
    "pie": "pieChart",
    "donut": "donutChart",
    "scatter": "scatterChart",
    "bubble": "scatterChart",
    "combo": "lineClusteredColumnComboChart",
    "waterfall": "waterfallChart",
    "funnel": "funnel",
    "gauge": "gauge",
    "meter": "gauge",
    "treemap": "treemap",
    # Cross-tabulation
    "Crosstab": "pivotTable",
    "crosstab": "pivotTable",
    # Text / labels
    "label": "textbox",
    "text": "textbox",
    "data": "card",
    # Images
    "image": "image",
}

# Default visual sizes (width, height) in pixels
DEFAULT_SIZES: dict[str, tuple[int, int]] = {
    "tableEx": (600, 400),
    "pivotTable": (600, 400),
    "clusteredBarChart": (400, 300),
    "stackedBarChart": (400, 300),
    "lineChart": (400, 300),
    "areaChart": (400, 300),
    "pieChart": (300, 300),
    "donutChart": (300, 300),
    "scatterChart": (400, 300),
    "lineClusteredColumnComboChart": (500, 300),
    "waterfallChart": (400, 300),
    "funnel": (300, 400),
    "gauge": (250, 250),
    "treemap": (400, 300),
    "textbox": (200, 50),
    "card": (150, 100),
    "image": (200, 150),
}


class VisualMapper:
    """Maps BIRT visual elements to Power BI visual configurations."""

    def __init__(self):
        self.mapping_log: list[dict[str, Any]] = []

    def map_element(
        self,
        element: dict[str, Any],
        page_width: int = 1280,
        page_height: int = 720,
    ) -> dict[str, Any]:
        """Map a single BIRT body element to a PBI visual config.

        Args:
            element: Parsed BIRT element from body[].
            page_width: Target PBI page width.
            page_height: Target PBI page height.

        Returns:
            PBI visual configuration dict.
        """
        element_type = element.get("element_type", "")
        extension_name = element.get("extension_name", "")
        chart_type = element.get("chart_config", {}).get("chart_type", "")

        # Determine PBI visual type
        pbi_type = self._resolve_visual_type(element_type, extension_name, chart_type)

        # Build visual config
        visual: dict[str, Any] = {
            "visual_type": pbi_type,
            "name": element.get("name", ""),
            "source_type": element_type,
            "source_chart_type": chart_type,
            "position": self._calculate_position(element, page_width, page_height),
            "size": self._get_size(pbi_type),
        }

        # Map data bindings
        if element_type == "table":
            visual["columns"] = self._map_table_columns(element)
            visual["dataset"] = element.get("dataset", "")
            visual["groups"] = element.get("groups", [])
        elif chart_type:
            visual["chart_config"] = self._map_chart_config(element)
        elif element_type in ("label", "text", "data"):
            visual["text_config"] = self._map_text_config(element)

        # Styling
        visual["style"] = self._map_style(element)

        self.mapping_log.append({
            "source": f"{element_type}:{element.get('name', '')}",
            "target": pbi_type,
            "status": "mapped" if pbi_type != "textbox" else "fallback",
        })

        return visual

    def map_all(
        self,
        body_elements: list[dict[str, Any]],
        page_width: int = 1280,
        page_height: int = 720,
    ) -> list[dict[str, Any]]:
        """Map all BIRT body elements to PBI visuals."""
        visuals: list[dict[str, Any]] = []
        for elem in body_elements:
            visual = self.map_element(elem, page_width, page_height)
            visuals.append(visual)

            # Recurse into children (for grids containing visuals)
            for child in elem.get("children", []):
                child_visual = self.map_element(child, page_width, page_height)
                visuals.append(child_visual)

        logger.info("Mapped %d BIRT elements to %d PBI visuals", len(body_elements), len(visuals))
        return visuals

    def _resolve_visual_type(
        self,
        element_type: str,
        extension_name: str,
        chart_type: str,
    ) -> str:
        """Resolve the best PBI visual type."""
        # Chart subtype first
        if chart_type and chart_type in VISUAL_TYPE_MAP:
            return VISUAL_TYPE_MAP[chart_type]
        # Extension name (crosstab, etc.)
        if extension_name and extension_name in VISUAL_TYPE_MAP:
            return VISUAL_TYPE_MAP[extension_name]
        # Element type
        if element_type in VISUAL_TYPE_MAP:
            return VISUAL_TYPE_MAP[element_type]
        # Fallback
        return "textbox"

    def _map_table_columns(self, element: dict[str, Any]) -> list[dict[str, Any]]:
        """Map BIRT table column bindings to PBI column references."""
        columns: list[dict[str, Any]] = []
        for col in element.get("columns", []):
            columns.append({
                "name": col.get("name", ""),
                "expression": col.get("expression", ""),
                "data_type": col.get("dataType", "string"),
                "display_name": col.get("displayName", col.get("name", "")),
            })
        return columns

    def _map_chart_config(self, element: dict[str, Any]) -> dict[str, Any]:
        """Map BIRT chart configuration to PBI chart properties."""
        chart = element.get("chart_config", {})
        return {
            "chart_type": chart.get("chart_type", ""),
            "series": chart.get("series", []),
            "categories": chart.get("categories", []),
        }

    def _map_text_config(self, element: dict[str, Any]) -> dict[str, Any]:
        """Map BIRT label/text to PBI textbox/card config."""
        expressions = element.get("expressions", [])
        text_value = ""
        if expressions:
            text_value = expressions[0].get("value", "")
        return {
            "text": text_value,
            "properties": element.get("properties", {}),
        }

    def _map_style(self, element: dict[str, Any]) -> dict[str, Any]:
        """Map BIRT styles to PBI formatting."""
        props = element.get("properties", {})
        style: dict[str, Any] = {}

        # Font
        if "fontFamily" in props:
            style["fontFamily"] = props["fontFamily"]
        if "fontSize" in props:
            style["fontSize"] = props["fontSize"]
        if "fontWeight" in props:
            style["bold"] = props["fontWeight"] == "bold"
        if "fontStyle" in props:
            style["italic"] = props["fontStyle"] == "italic"

        # Colors
        if "color" in props:
            style["fontColor"] = self._css_to_hex(props["color"])
        if "backgroundColor" in props:
            style["backgroundColor"] = self._css_to_hex(props["backgroundColor"])

        # Borders
        if "borderBottomStyle" in props or "borderTopStyle" in props:
            style["border"] = True

        return style

    @staticmethod
    def _calculate_position(
        element: dict[str, Any],
        page_width: int,
        page_height: int,
    ) -> dict[str, int]:
        """Calculate visual position on PBI page."""
        depth = element.get("depth", 0)
        # Simple stacking layout — could be refined with actual BIRT positioning
        return {
            "x": 20 + (depth * 10),
            "y": 20,  # Will be adjusted by PBIP generator for non-overlapping layout
            "z": 0,
        }

    @staticmethod
    def _get_size(pbi_type: str) -> dict[str, int]:
        """Get default size for a PBI visual type."""
        w, h = DEFAULT_SIZES.get(pbi_type, (300, 200))
        return {"width": w, "height": h}

    @staticmethod
    def _css_to_hex(css_color: str) -> str:
        """Convert CSS color to hex (pass-through for hex values)."""
        if css_color.startswith("#"):
            return css_color
        # Named colors → hex (common ones)
        named: dict[str, str] = {
            "black": "#000000", "white": "#FFFFFF", "red": "#FF0000",
            "green": "#008000", "blue": "#0000FF", "gray": "#808080",
            "yellow": "#FFFF00", "orange": "#FFA500", "purple": "#800080",
        }
        return named.get(css_color.lower(), css_color)
