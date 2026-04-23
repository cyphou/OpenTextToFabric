"""Tests for report_converter.conditional_format."""

import unittest

from report_converter.conditional_format import ConditionalFormatConverter, StyleConverter


class TestConditionalFormatConverter(unittest.TestCase):

    def setUp(self):
        self.converter = ConditionalFormatConverter()

    def test_simple_gt_rule(self):
        highlights = [{
            "operator": "gt",
            "value1": 1000000,
            "style": {"color": "#FF0000"},
            "target_column": "Revenue",
        }]
        result = self.converter.convert_highlights(highlights)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "rules")
        self.assertEqual(result[0]["target"], "Revenue")
        rule = result[0]["rules"][0]
        self.assertEqual(rule["condition"]["operator"], "greaterThan")
        self.assertEqual(rule["condition"]["value"], 1000000)
        self.assertEqual(rule["formatting"]["fontColor"], "#FF0000")

    def test_between_rule(self):
        highlights = [{
            "operator": "between",
            "value1": 100,
            "value2": 500,
            "style": {"background-color": "green"},
            "target_column": "Score",
        }]
        result = self.converter.convert_highlights(highlights)
        self.assertEqual(len(result), 1)
        rule = result[0]["rules"][0]
        self.assertEqual(rule["condition"]["operator"], "between")
        self.assertEqual(rule["condition"]["value"], 100)
        self.assertEqual(rule["condition"]["upperBound"], 500)

    def test_unsupported_operator(self):
        highlights = [{"operator": "foo_unknown", "style": {"color": "red"}}]
        result = self.converter.convert_highlights(highlights)
        self.assertEqual(len(result), 0)

    def test_no_style_returns_none(self):
        highlights = [{"operator": "gt", "value1": 10, "style": {}}]
        result = self.converter.convert_highlights(highlights)
        self.assertEqual(len(result), 0)

    def test_named_color_conversion(self):
        result = ConditionalFormatConverter._convert_color("red")
        self.assertEqual(result, "#FF0000")

    def test_hex_color_passthrough(self):
        result = ConditionalFormatConverter._convert_color("#ABC123")
        self.assertEqual(result, "#ABC123")

    def test_multiple_style_properties(self):
        highlights = [{
            "operator": "eq",
            "value1": "Critical",
            "style": {"color": "#FF0000", "background-color": "#FFCCCC", "font-weight": "bold"},
            "target_column": "Status",
        }]
        result = self.converter.convert_highlights(highlights)
        self.assertEqual(len(result), 1)
        fmt = result[0]["rules"][0]["formatting"]
        self.assertEqual(fmt["fontColor"], "#FF0000")
        self.assertEqual(fmt["background"], "#FFCCCC")
        self.assertEqual(fmt["fontWeight"], "bold")

    def test_string_value_parsing(self):
        val = ConditionalFormatConverter._parse_value("123.45")
        self.assertEqual(val, 123.45)

    def test_string_text_parsing(self):
        val = ConditionalFormatConverter._parse_value("active")
        self.assertEqual(val, "active")

    def test_all_operators_mapped(self):
        ops = ["eq", "ne", "gt", "ge", "lt", "le", "between", "not-between",
               "like", "not-like", "is-null", "is-not-null", "in", "not-in",
               "top-n", "bottom-n", "top-percent", "bottom-percent"]
        for op in ops:
            self.assertIn(op, ConditionalFormatConverter.OPERATOR_MAP)


class TestStyleConverter(unittest.TestCase):

    def test_convert_styles_basic(self):
        styles = [
            {"color": "#FF0000", "font-family": "Arial"},
            {"color": "#00FF00", "font-family": "Arial"},
            {"background-color": "#0000FF"},
        ]
        converter = StyleConverter()
        theme = converter.convert_styles(styles)
        self.assertEqual(theme["name"], "MigratedTheme")
        self.assertIn("#FF0000", theme["dataColors"])
        self.assertIn("#00FF00", theme["dataColors"])
        self.assertEqual(theme["fontFamily"], "Arial")

    def test_empty_styles(self):
        converter = StyleConverter()
        theme = converter.convert_styles([])
        self.assertEqual(theme["name"], "MigratedTheme")
        self.assertEqual(theme["dataColors"], [])


if __name__ == "__main__":
    unittest.main()
