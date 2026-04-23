"""BIRT conditional formatting → Power BI conditional formatting rules."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ConditionalFormatConverter:
    """Converts BIRT highlight rules and style conditions to PBI conditional formatting.

    BIRT highlight rules are extracted as:
    {
        "type": "highlight",
        "test_expression": "row['Revenue'] > 1000000",
        "style": {"color": "#FF0000", "font_weight": "bold", ...},
        "target": "cell" | "row",
        "operator": "gt" | "lt" | "eq" | "between" | ...,
        "value1": ...,
        "value2": ...,
    }

    Power BI conditional formatting rules:
    {
        "rules": [{"inputColor": {"color": "#FF0000"}, "value": {"compareTo": "staticValue", ...}}],
        "type": "gradient" | "rules" | "fieldValue"
    }
    """

    # BIRT operators → PBI condition operators
    OPERATOR_MAP: dict[str, str] = {
        "eq": "equals",
        "ne": "notEquals",
        "gt": "greaterThan",
        "ge": "greaterThanOrEqual",
        "lt": "lessThan",
        "le": "lessThanOrEqual",
        "between": "between",
        "not-between": "notBetween",
        "like": "contains",
        "not-like": "doesNotContain",
        "is-null": "isBlank",
        "is-not-null": "isNotBlank",
        "is-true": "is",
        "is-false": "is",
        "in": "isOneOf",
        "not-in": "isNotOneOf",
        "top-n": "topN",
        "bottom-n": "bottomN",
        "top-percent": "topNPercent",
        "bottom-percent": "bottomNPercent",
    }

    # BIRT CSS properties → PBI format property targets
    STYLE_TARGET_MAP: dict[str, str] = {
        "color": "fontColor",
        "background-color": "background",
        "font-weight": "fontWeight",
        "font-style": "fontStyle",
        "text-decoration": "textDecoration",
        "font-size": "fontSize",
        "border-color": "borderColor",
    }

    def convert_highlights(
        self,
        highlights: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert a list of BIRT highlight rules to PBI conditional formatting.

        Args:
            highlights: List of BIRT highlight dicts from extraction.

        Returns:
            List of PBI conditional formatting configs per target field.
        """
        results: list[dict[str, Any]] = []

        for hl in highlights:
            pbi_rule = self._convert_single(hl)
            if pbi_rule:
                results.append(pbi_rule)

        logger.info("Converted %d/%d highlight rules", len(results), len(highlights))
        return results

    def _convert_single(self, highlight: dict[str, Any]) -> dict[str, Any] | None:
        """Convert a single BIRT highlight rule."""
        operator = highlight.get("operator", "")
        pbi_op = self.OPERATOR_MAP.get(operator)
        if not pbi_op:
            logger.warning("Unsupported highlight operator: %s", operator)
            return None

        style = highlight.get("style", {})
        target_field = highlight.get("target_column", highlight.get("target", ""))

        # Build rule conditions
        condition: dict[str, Any] = {
            "operator": pbi_op,
            "compareTo": "staticValue",
        }

        value1 = highlight.get("value1")
        if value1 is not None:
            condition["value"] = self._parse_value(value1)

        value2 = highlight.get("value2")
        if value2 is not None and operator in ("between", "not-between"):
            condition["upperBound"] = self._parse_value(value2)

        # Build formatting actions from style
        formatting: dict[str, Any] = {}
        for birt_prop, pbi_prop in self.STYLE_TARGET_MAP.items():
            css_val = style.get(birt_prop) or style.get(birt_prop.replace("-", "_"))
            if css_val:
                formatting[pbi_prop] = self._convert_color(css_val) if "color" in pbi_prop.lower() else css_val

        if not formatting:
            return None

        return {
            "target": target_field,
            "rules": [{
                "condition": condition,
                "formatting": formatting,
            }],
            "type": "rules",
        }

    @staticmethod
    def _parse_value(val: Any) -> Any:
        """Parse a BIRT highlight value to a typed value."""
        if isinstance(val, (int, float)):
            return val
        if isinstance(val, str):
            try:
                return float(val)
            except ValueError:
                return val
        return val

    @staticmethod
    def _convert_color(color: str) -> str:
        """Normalize a CSS color to hex format."""
        color = color.strip()
        if color.startswith("#"):
            return color.upper()
        # Named colors → hex (common ones)
        named = {
            "red": "#FF0000", "green": "#00FF00", "blue": "#0000FF",
            "black": "#000000", "white": "#FFFFFF", "yellow": "#FFFF00",
            "orange": "#FFA500", "gray": "#808080", "grey": "#808080",
            "purple": "#800080", "pink": "#FFC0CB", "brown": "#A52A2A",
        }
        return named.get(color.lower(), color)


class StyleConverter:
    """Converts BIRT report-level styles to Power BI theme properties."""

    def convert_styles(
        self,
        styles: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Convert BIRT styles to a PBI report theme fragment.

        Args:
            styles: List of BIRT style definitions.

        Returns:
            PBI theme-compatible dict.
        """
        theme: dict[str, Any] = {
            "name": "MigratedTheme",
            "dataColors": [],
            "foreground": "#333333",
            "background": "#FFFFFF",
            "tableAccent": "#4472C4",
        }

        colors_seen: list[str] = []
        for style in styles:
            color = style.get("color") or style.get("background-color", "")
            if color and color.startswith("#") and color.upper() not in colors_seen:
                colors_seen.append(color.upper())

        if colors_seen:
            theme["dataColors"] = colors_seen[:8]

        # Extract font family if consistent
        fonts = [s.get("font-family", "") for s in styles if s.get("font-family")]
        if fonts:
            most_common = max(set(fonts), key=fonts.count)
            theme["fontFamily"] = most_common

        return theme

    def generate_theme_file(
        self,
        styles: list[dict[str, Any]],
        chart_palettes: list[list[str]] | None = None,
        output_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Generate a full Power BI theme JSON file.

        Args:
            styles: BIRT style definitions.
            chart_palettes: Optional list of color palettes extracted from charts.
            output_path: If provided, writes the theme JSON to this path.

        Returns:
            Complete PBI theme dict.
        """
        theme = self.convert_styles(styles)
        theme["$schema"] = "https://raw.githubusercontent.com/microsoft/powerbi-desktop-samples/main/Report%20Theme%20JSON%20Schema/reportThemeSchema-2.124.json"

        # Merge chart palettes into dataColors
        if chart_palettes:
            all_colors: list[str] = list(theme.get("dataColors", []))
            for palette in chart_palettes:
                for color in palette:
                    norm = color.strip().upper()
                    if norm.startswith("#") and norm not in all_colors:
                        all_colors.append(norm)
            theme["dataColors"] = all_colors[:12]

        # Font configuration
        font = theme.pop("fontFamily", "Segoe UI")
        theme["textClasses"] = {
            "label": {"fontFace": font, "fontSize": 9},
            "title": {"fontFace": font, "fontSize": 12, "fontWeight": "bold"},
            "header": {"fontFace": font, "fontSize": 11, "fontWeight": "bold"},
            "callout": {"fontFace": font, "fontSize": 14, "fontWeight": "bold"},
        }

        # Visual styles
        theme["visualStyles"] = {
            "*": {
                "*": {
                    "general": [{"responsive": True}],
                }
            }
        }

        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                json.dump(theme, f, indent=2)
            logger.info("Generated theme file: %s", out)

        return theme


class GradientFormatConverter:
    """Converts BIRT gradient-like formatting to PBI gradient conditional formatting.

    Handles BIRT patterns where multiple highlight rules create a color gradient
    effect (e.g., low→yellow, medium→orange, high→red).
    """

    DEFAULT_GRADIENT_COLORS = ["#63BE7B", "#FFEB84", "#F8696B"]  # Green → Yellow → Red

    def detect_gradient(
        self,
        highlights: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Detect if a set of highlights forms a gradient pattern.

        A gradient is detected when 3+ rules on the same column use ordered
        numeric thresholds with different colors.

        Returns:
            Gradient config dict or None if not a gradient pattern.
        """
        if len(highlights) < 2:
            return None

        # Group by target column
        by_column: dict[str, list[dict[str, Any]]] = {}
        for hl in highlights:
            col = hl.get("target_column", hl.get("target", ""))
            if col:
                by_column.setdefault(col, []).append(hl)

        for column, rules in by_column.items():
            # Need numeric values to form a gradient
            numeric_rules = []
            for r in rules:
                v = r.get("value1")
                if v is not None:
                    try:
                        numeric_rules.append((float(v), r))
                    except (ValueError, TypeError):
                        continue

            if len(numeric_rules) < 2:
                continue

            # Sort by threshold value
            numeric_rules.sort(key=lambda x: x[0])
            colors = []
            values = []
            for val, rule in numeric_rules:
                style = rule.get("style", {})
                color = style.get("color") or style.get("background-color", "")
                if color:
                    colors.append(color.upper() if color.startswith("#") else color)
                    values.append(val)

            if len(colors) >= 2:
                return {
                    "target": column,
                    "type": "gradient",
                    "minimum": {"value": values[0], "color": colors[0]},
                    "maximum": {"value": values[-1], "color": colors[-1]},
                    "center": {
                        "value": values[len(values) // 2],
                        "color": colors[len(colors) // 2],
                    } if len(colors) >= 3 else None,
                }

        return None

    def build_gradient_rule(
        self,
        column: str,
        min_color: str = "#63BE7B",
        mid_color: str = "#FFEB84",
        max_color: str = "#F8696B",
    ) -> dict[str, Any]:
        """Build a PBI gradient conditional formatting rule."""
        rule: dict[str, Any] = {
            "target": column,
            "type": "gradient",
            "minimum": {"color": min_color},
            "maximum": {"color": max_color},
        }
        if mid_color:
            rule["center"] = {"color": mid_color}
        return rule


class DataBarConverter:
    """Converts BIRT progress-bar / gauge-like visuals to PBI data bar formatting."""

    def convert_to_data_bars(
        self,
        column: str,
        min_value: float | None = None,
        max_value: float | None = None,
        positive_color: str = "#4472C4",
        negative_color: str = "#FF6347",
    ) -> dict[str, Any]:
        """Generate PBI data bar conditional formatting config.

        Args:
            column: Target column name.
            min_value: Minimum axis value (None = automatic).
            max_value: Maximum axis value (None = automatic).
            positive_color: Color for positive bars.
            negative_color: Color for negative bars.

        Returns:
            PBI data bar formatting config.
        """
        config: dict[str, Any] = {
            "target": column,
            "type": "dataBar",
            "positiveColor": positive_color,
            "negativeColor": negative_color,
            "axisColor": "#808080",
            "showValue": True,
        }
        if min_value is not None:
            config["minimum"] = {"value": min_value, "type": "staticValue"}
        if max_value is not None:
            config["maximum"] = {"value": max_value, "type": "staticValue"}

        return config


class IconSetConverter:
    """Converts BIRT icon/image-based conditional formatting to PBI icon sets."""

    # Standard PBI icon sets
    ICON_SETS: dict[str, list[dict[str, str]]] = {
        "traffic_light": [
            {"icon": "circle", "color": "#FF0000"},  # Red
            {"icon": "circle", "color": "#FFA500"},  # Yellow
            {"icon": "circle", "color": "#00FF00"},  # Green
        ],
        "arrows": [
            {"icon": "arrowDown", "color": "#FF0000"},
            {"icon": "arrowRight", "color": "#FFA500"},
            {"icon": "arrowUp", "color": "#00FF00"},
        ],
        "flags": [
            {"icon": "flag", "color": "#FF0000"},
            {"icon": "flag", "color": "#FFA500"},
            {"icon": "flag", "color": "#00FF00"},
        ],
        "stars": [
            {"icon": "star", "color": "#808080"},
            {"icon": "star", "color": "#FFA500"},
            {"icon": "star", "color": "#FFD700"},
        ],
    }

    def convert_icon_rules(
        self,
        column: str,
        thresholds: list[float],
        icon_set: str = "traffic_light",
    ) -> dict[str, Any]:
        """Generate PBI icon set conditional formatting.

        Args:
            column: Target column.
            thresholds: List of threshold values (ascending) dividing icon ranges.
            icon_set: Name of icon set to use.

        Returns:
            PBI icon set formatting config.
        """
        icons = self.ICON_SETS.get(icon_set, self.ICON_SETS["traffic_light"])

        rules: list[dict[str, Any]] = []
        for i, icon in enumerate(icons):
            rule: dict[str, Any] = {"icon": icon}
            if i < len(thresholds):
                rule["threshold"] = thresholds[i]
            rules.append(rule)

        return {
            "target": column,
            "type": "iconSet",
            "iconSetName": icon_set,
            "rules": rules,
        }

    def detect_icon_pattern(
        self,
        highlights: list[dict[str, Any]],
    ) -> str | None:
        """Detect if BIRT highlights use an icon/status pattern.

        Returns the recommended icon set name, or None.
        """
        for hl in highlights:
            style = hl.get("style", {})
            # If BIRT uses image URLs with traffic light / status patterns
            image = style.get("background-image", "") or style.get("image", "")
            text_expr = hl.get("test_expression", "")

            if any(kw in image.lower() or kw in text_expr.lower()
                   for kw in ("traffic", "light", "red", "green", "yellow", "status")):
                return "traffic_light"
            if any(kw in image.lower() or kw in text_expr.lower()
                   for kw in ("arrow", "trend", "up", "down")):
                return "arrows"
            if any(kw in image.lower() or kw in text_expr.lower()
                   for kw in ("flag", "alert", "warning")):
                return "flags"
            if any(kw in image.lower() or kw in text_expr.lower()
                   for kw in ("star", "rating", "score")):
                return "stars"

        return None
