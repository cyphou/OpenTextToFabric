"""BIRT visual type → Power BI visual mapping."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# BIRT element type / chart type → Power BI visual type mapping
VISUAL_TYPE_MAP: dict[str, str] = {
    # Tables
    "table": "tableEx",
    "list": "tableEx",
    "grid": "tableEx",
    # Charts — bar family
    "bar": "clusteredBarChart",
    "stackedbar": "stackedBarChart",
    "percentstackedbar": "hundredPercentStackedBarChart",
    "column": "clusteredColumnChart",
    "stackedcolumn": "stackedColumnChart",
    "percentstackedcolumn": "hundredPercentStackedColumnChart",
    # Charts — line/area
    "line": "lineChart",
    "area": "areaChart",
    "stackedarea": "stackedAreaChart",
    # Charts — pie/donut
    "pie": "pieChart",
    "donut": "donutChart",
    # Charts — scatter/bubble
    "scatter": "scatterChart",
    "bubble": "scatterChart",
    # Charts — combo
    "combo": "lineClusteredColumnComboChart",
    # Charts — specialized
    "waterfall": "waterfallChart",
    "funnel": "funnel",
    "gauge": "gauge",
    "meter": "gauge",
    "treemap": "treemap",
    "radar": "radarChart",
    "ribbon": "ribbonChart",
    # KPI / card variants
    "kpi": "multiRowCard",
    "multicard": "multiRowCard",
    "scorecard": "kpi",
    # Map
    "map": "map",
    "filledmap": "filledMap",
    "shapemap": "shapeMap",
    # Advanced analytics
    "decompositiontree": "decompositionTreeVisual",
    "keyinfluencers": "keyInfluencers",
    "qna": "qnaVisual",
    # Cross-tabulation
    "Crosstab": "pivotTable",
    "crosstab": "pivotTable",
    "matrix": "pivotTable",
    # Text / labels
    "label": "textbox",
    "text": "textbox",
    "data": "card",
    # Images
    "image": "image",
    # Slicer
    "parameter": "slicer",
    "filter": "slicer",
    # ── Sprint 28 additions (13 new types) ──
    # Hierarchical / drill visuals
    "hierarchy": "decompositionTreeVisual",
    "drill": "decompositionTreeVisual",
    # 100% charts
    "percentstackedarea": "hundredPercentStackedAreaChart",
    # Specialized charts
    "heatmap": "tableHeatmap",
    "gantt": "clusteredBarChart",  # Gantt approximation
    "box": "clusteredBarChart",    # Box plot approximation
    "histogram": "clusteredColumnChart",
    "pareto": "lineClusteredColumnComboChart",
    # R / Python custom visuals
    "rvisual": "scriptVisual",
    "pythonvisual": "scriptVisual",
    "script": "scriptVisual",
    # Smart narrative / AI
    "narrative": "smartNarrative",
    "summary": "smartNarrative",
    # Progress / status
    "progress": "gauge",
    "bullet": "gauge",
    # Card variants
    "cardvisual": "card",
    "multirowcard": "multiRowCard",
    # ── Extended visual types (Sprint 31) — 40 additional mappings ──
    # Line variants
    "stepline": "lineChart",
    "smoothline": "lineChart",
    "dashedline": "lineChart",
    # Area variants
    "percentstackedarea100": "hundredPercentStackedAreaChart",
    "streamgraph": "stackedAreaChart",
    # Bar/column variants
    "clusteredbar3d": "clusteredBarChart",
    "stackedbar3d": "stackedBarChart",
    "clusteredcolumn3d": "clusteredColumnChart",
    "stackedcolumn3d": "stackedColumnChart",
    "cylinder": "clusteredColumnChart",
    "cone": "clusteredColumnChart",
    "pyramid": "clusteredColumnChart",
    # Pie/donut variants
    "pie3d": "pieChart",
    "ring": "donutChart",
    "semicircle": "donutChart",
    "sunburst": "treemap",
    # Scatter variants
    "dotplot": "scatterChart",
    "strip": "scatterChart",
    "jitter": "scatterChart",
    # Combo variants
    "dualaxis": "lineClusteredColumnComboChart",
    "linecolumn": "lineClusteredColumnComboChart",
    "linestackedcolumn": "lineStackedColumnComboChart",
    "linearea": "lineClusteredColumnComboChart",
    # Table/matrix variants
    "pivot": "pivotTable",
    "detailtable": "tableEx",
    "summarytable": "tableEx",
    "bandedtable": "tableEx",
    # Card/KPI variants
    "singlecard": "card",
    "numbercardvisual": "card",
    "indicator": "kpi",
    "speedometer": "gauge",
    "dial": "gauge",
    "linearGauge": "gauge",
    "thermometer": "gauge",
    # Map variants
    "choropleth": "filledMap",
    "bubblemap": "map",
    "heatmapgeo": "filledMap",
    "arcgis": "map",
    "leaflet": "map",
    # Advanced charts
    "sankey": "decompositionTreeVisual",
    "chord": "decompositionTreeVisual",
    "network": "decompositionTreeVisual",
    "wordcloud": "tableEx",
    "calendar": "tableEx",
    "timeline": "clusteredBarChart",
    "tornado": "clusteredBarChart",
    "butterfly": "clusteredBarChart",
    "lollipop": "clusteredColumnChart",
    "dumbell": "clusteredBarChart",
    "sparkline": "lineChart",
    "sparkbar": "clusteredColumnChart",
    "smallmultiples": "lineChart",
    "trellis": "lineChart",
    # Layout / container
    "tab": "group",
    "panel": "group",
    "accordion": "group",
    "container": "group",
    # Interactive
    "button": "actionButton",
    "dropdown": "slicer",
    "slider": "slicer",
    "checkbox": "slicer",
    "radio": "slicer",
    "datepicker": "slicer",
    "rangepicker": "slicer",
    "searchbox": "slicer",
    "listbox": "slicer",
    # Miscellaneous
    "divider": "shape",
    "shape": "shape",
    "line_shape": "shape",
    "rectangle": "shape",
    "ellipse": "shape",
    "arrow": "shape",
    "icon": "image",
    "logo": "image",
    "webview": "textbox",
    "iframe": "textbox",
    "html": "textbox",
    "video": "image",
    "qrcode": "image",
    "barcode": "image",
    "paginator": "pageNavigator",
    "navigation": "pageNavigator",
    "toc": "pageNavigator",
    "bookmark_nav": "bookmarkNavigator",
}

# Default visual sizes (width, height) in pixels
DEFAULT_SIZES: dict[str, tuple[int, int]] = {
    "tableEx": (600, 400),
    "pivotTable": (600, 400),
    "clusteredBarChart": (400, 300),
    "stackedBarChart": (400, 300),
    "hundredPercentStackedBarChart": (400, 300),
    "clusteredColumnChart": (400, 300),
    "stackedColumnChart": (400, 300),
    "hundredPercentStackedColumnChart": (400, 300),
    "lineChart": (400, 300),
    "areaChart": (400, 300),
    "stackedAreaChart": (400, 300),
    "pieChart": (300, 300),
    "donutChart": (300, 300),
    "scatterChart": (400, 300),
    "lineClusteredColumnComboChart": (500, 300),
    "waterfallChart": (400, 300),
    "funnel": (300, 400),
    "gauge": (250, 250),
    "treemap": (400, 300),
    "radarChart": (350, 350),
    "ribbonChart": (400, 300),
    "multiRowCard": (400, 200),
    "kpi": (250, 150),
    "map": (500, 400),
    "filledMap": (500, 400),
    "shapeMap": (500, 400),
    "decompositionTreeVisual": (600, 400),
    "keyInfluencers": (600, 400),
    "qnaVisual": (500, 300),
    "slicer": (200, 100),
    "textbox": (200, 50),
    "card": (150, 100),
    "image": (200, 150),
    # Sprint 28 additions
    "hundredPercentStackedAreaChart": (400, 300),
    "tableHeatmap": (500, 400),
    "scriptVisual": (500, 400),
    "smartNarrative": (400, 200),
    "pageNavigator": (1280, 40),
    # Sprint 31 additions
    "lineStackedColumnComboChart": (500, 300),
    "group": (600, 400),
    "actionButton": (120, 40),
    "shape": (200, 100),
    "bookmarkNavigator": (400, 40),
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
            # Tables with groups → matrix subtotals
            if visual["groups"]:
                visual["subtotals"] = self._map_group_subtotals(element)
        elif chart_type:
            visual["chart_config"] = self._map_chart_config(element)
            visual["dataset"] = element.get("dataset", "")
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

    # Structural / layout element types that should never produce standalone
    # PBI visuals.  These are BIRT layout containers (table column widths,
    # table rows, grid cells, grids, etc.) — not data visuals.
    _STRUCTURAL_TYPES = frozenset({
        "column", "row", "cell", "header", "detail", "footer",
        "group", "list-group", "grid",
    })

    def map_all(
        self,
        body_elements: list[dict[str, Any]],
        page_width: int = 1280,
        page_height: int = 720,
    ) -> list[dict[str, Any]]:
        """Map all BIRT body elements to PBI visuals.

        Performs a deep traversal of the element tree so that data-bearing
        elements nested inside grids (grid → row → cell → table) are found
        regardless of nesting depth.  Structural layout elements (column,
        row, cell, header, detail, footer, group) are skipped.
        """
        visuals: list[dict[str, Any]] = []
        self._collect_visuals(body_elements, visuals, page_width, page_height)

        logger.info("Mapped %d BIRT elements to %d PBI visuals", len(body_elements), len(visuals))
        return visuals

    def _collect_visuals(
        self,
        elements: list[dict[str, Any]],
        visuals: list[dict[str, Any]],
        page_width: int,
        page_height: int,
    ) -> None:
        """Recursively collect data-bearing visuals, skipping structural layout."""
        for elem in elements:
            elem_type = elem.get("element_type", "")

            if elem_type in self._STRUCTURAL_TYPES:
                # Still recurse into structural elements — they may contain
                # data visuals (e.g. cell → table, row → cell → extended-item)
                self._collect_visuals(
                    elem.get("children", []), visuals, page_width, page_height,
                )
                continue

            # Map this element as a PBI visual
            visual = self.map_element(elem, page_width, page_height)
            visuals.append(visual)

            # Recurse into children (grid → row → cell → table chain)
            self._collect_visuals(
                elem.get("children", []), visuals, page_width, page_height,
            )

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
        """Map BIRT table column bindings to PBI column references.

        Resolves BIRT aliases: when a column name differs from the dataset
        column it references (e.g. ``groupe_sur_puits`` → ``dataSetRow["Puits"]``),
        the underlying dataset column name is used instead.
        """
        columns: list[dict[str, Any]] = []
        seen: set[str] = set()
        for col in element.get("columns", []):
            name = col.get("name", "")
            expr = col.get("expression", "")
            # Resolve aliases: dataSetRow["RealCol"] → use RealCol
            m = re.match(r'dataSetRow\["([^"]+)"\]', expr)
            if m:
                real_col = m.group(1)
                # If the BIRT column name differs from the dataset column,
                # it's an alias — use the real column name.
                if real_col != name:
                    name = real_col
            if name in seen:
                continue  # skip duplicate references
            seen.add(name)
            columns.append({
                "name": name,
                "expression": expr,
                "data_type": col.get("dataType", "string"),
                "display_name": col.get("displayName", col.get("name", "")),
            })
        return columns

    @staticmethod
    def _map_group_subtotals(element: dict[str, Any]) -> list[dict[str, Any]]:
        """Map BIRT table group headers/footers to PBI matrix subtotals.

        BIRT tables with groups produce headers and footers that correspond
        to PBI matrix row subtotals.
        """
        subtotals: list[dict[str, Any]] = []
        for group in element.get("groups", []):
            subtotals.append({
                "group_name": group.get("name", ""),
                "key_expression": group.get("key_expression", group.get("key_expr", "")),
                "show_header": True,
                "show_footer": True,
                "position": "top",
            })
        return subtotals

    def _map_chart_config(self, element: dict[str, Any]) -> dict[str, Any]:
        """Map BIRT chart configuration to PBI chart properties."""
        chart = element.get("chart_config", {})
        config: dict[str, Any] = {
            "chart_type": chart.get("chart_type", ""),
            "series": chart.get("series", []),
            "categories": chart.get("categories", []),
        }

        # Axis configuration
        axes = chart.get("axes", [])
        if axes:
            config["axes"] = self._map_axes(axes)

        # Legend
        legend = chart.get("legend", {})
        if legend:
            config["legend"] = self._map_legend(legend)

        # Tooltip
        tooltip = chart.get("tooltip", {})
        if tooltip:
            config["tooltip"] = self._map_tooltip(tooltip)

        # Title
        title = chart.get("title", "")
        if title:
            config["title"] = title

        return config

    @staticmethod
    def _map_axes(axes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map BIRT chart axes to PBI axis config."""
        mapped: list[dict[str, Any]] = []
        for axis in axes:
            ax: dict[str, Any] = {
                "type": axis.get("type", ""),
            }
            if axis.get("title"):
                ax["title"] = axis["title"]
                ax["showTitle"] = True
            if axis.get("min") is not None:
                ax["rangeMin"] = axis["min"]
            if axis.get("max") is not None:
                ax["rangeMax"] = axis["max"]
            if axis.get("labelRotation"):
                ax["labelRotation"] = axis["labelRotation"]
            ax["showGridlines"] = axis.get("showGridlines", True)
            mapped.append(ax)
        return mapped

    @staticmethod
    def _map_legend(legend: dict[str, Any]) -> dict[str, Any]:
        """Map BIRT legend to PBI legend config."""
        # BIRT positions: left, right, top, bottom, inside
        position_map = {
            "left": "left",
            "right": "right",
            "top": "top",
            "bottom": "bottom",
            "inside": "topRight",
        }
        birt_pos = legend.get("position", "right").lower()
        return {
            "show": legend.get("visible", True),
            "position": position_map.get(birt_pos, "right"),
            "fontSize": legend.get("fontSize", 9),
        }

    @staticmethod
    def _map_tooltip(tooltip: dict[str, Any]) -> dict[str, Any]:
        """Map BIRT tooltip to PBI tooltip config."""
        config: dict[str, Any] = {
            "show": True,
        }
        if tooltip.get("expression"):
            config["custom_expression"] = tooltip["expression"]
        if tooltip.get("format"):
            config["format"] = tooltip["format"]
        return config

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
