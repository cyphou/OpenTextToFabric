"""BIRT conditional formatting → Power BI conditional formatting rules."""

from __future__ import annotations

import logging
import re
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
