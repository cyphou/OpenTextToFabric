"""Tests for report_converter modules: expression_converter, visual_mapper, pbip_generator."""

import tempfile
import unittest
from pathlib import Path

from report_converter.expression_converter import ExpressionConverter
from report_converter.visual_mapper import VisualMapper
from report_converter.pbip_generator import PBIPGenerator


class TestExpressionConverter(unittest.TestCase):

    def setUp(self):
        self.converter = ExpressionConverter()

    # Aggregation functions
    def test_total_sum(self):
        result = self.converter.convert('Total.sum(row["amount"])')
        self.assertEqual(result["converted"], "SUM([amount])")
        self.assertEqual(result["status"], "success")

    def test_total_count(self):
        result = self.converter.convert("Total.count()")
        self.assertEqual(result["converted"], "COUNTROWS()")

    def test_total_average(self):
        result = self.converter.convert('Total.ave(row["value"])')
        self.assertEqual(result["converted"], "AVERAGE([value])")

    def test_total_max(self):
        result = self.converter.convert('Total.max(row["price"])')
        self.assertEqual(result["converted"], "MAX([price])")

    def test_total_min(self):
        result = self.converter.convert('Total.min(row["price"])')
        self.assertEqual(result["converted"], "MIN([price])")

    def test_total_distinct_count(self):
        result = self.converter.convert('Total.countDistinct(row["id"])')
        self.assertEqual(result["converted"], "DISTINCTCOUNT([id])")

    def test_total_percent_sum(self):
        result = self.converter.convert('Total.percentSum(row["amount"])')
        self.assertIn("DIVIDE", result["converted"])

    # String functions
    def test_to_upper(self):
        result = self.converter.convert('BirtStr.toUpper(row["name"])')
        self.assertEqual(result["converted"], "UPPER([name])")

    def test_to_lower(self):
        result = self.converter.convert('BirtStr.toLower(row["name"])')
        self.assertEqual(result["converted"], "LOWER([name])")

    def test_trim(self):
        result = self.converter.convert('BirtStr.trim(row["val"])')
        self.assertEqual(result["converted"], "TRIM([val])")

    def test_length(self):
        result = self.converter.convert('BirtStr.length(row["name"])')
        self.assertEqual(result["converted"], "LEN([name])")

    # Date functions
    def test_now(self):
        result = self.converter.convert("BirtDateTime.now()")
        self.assertEqual(result["converted"], "NOW()")

    def test_today(self):
        result = self.converter.convert("BirtDateTime.today()")
        self.assertEqual(result["converted"], "TODAY()")

    def test_year(self):
        result = self.converter.convert('BirtDateTime.year(row["date"])')
        self.assertEqual(result["converted"], "YEAR([date])")

    def test_diff_day(self):
        result = self.converter.convert('BirtDateTime.diffDay(row["start"], row["end"])')
        self.assertIn("DATEDIFF", result["converted"])

    # Math functions
    def test_round(self):
        result = self.converter.convert('BirtMath.round(row["val"], 2)')
        self.assertEqual(result["converted"], "ROUND([val], 2)")

    def test_abs(self):
        result = self.converter.convert('BirtMath.abs(row["val"])')
        self.assertEqual(result["converted"], "ABS([val])")

    # Row/dataSetRow references
    def test_row_reference(self):
        result = self.converter.convert('row["amount"]')
        self.assertEqual(result["converted"], "[amount]")

    def test_dataset_row_reference(self):
        result = self.converter.convert('dataSetRow["total"]')
        self.assertEqual(result["converted"], "[total]")

    def test_params_reference(self):
        result = self.converter.convert('params["StartDate"].value')
        self.assertEqual(result["converted"], "[@StartDate]")

    # Operators
    def test_equality_operator(self):
        result = self.converter.convert('row["status"] == "active"')
        self.assertIn("=", result["converted"])
        self.assertNotIn("==", result["converted"])

    def test_not_equal_operator(self):
        result = self.converter.convert('row["status"] !== "active"')
        self.assertIn("<>", result["converted"])

    # Ternary
    def test_ternary_to_if(self):
        result = self.converter.convert('row["amount"] > 0 ? "positive" : "negative"')
        self.assertIn("IF(", result["converted"])

    # Empty / unsupported
    def test_empty_expression(self):
        result = self.converter.convert("")
        self.assertEqual(result["status"], "empty")

    def test_unconverted_birt_function_warns(self):
        result = self.converter.convert("Total.someNewFunction(x)")
        self.assertEqual(result["status"], "partial")

    def test_javascript_constructs_unsupported(self):
        result = self.converter.convert("var x = 5; function foo() { return x; }")
        self.assertEqual(result["status"], "unsupported")

    # Batch
    def test_convert_batch(self):
        expressions = [
            {"expression": 'Total.sum(row["a"])', "source": "dataset:Sales"},
            {"expression": "BirtDateTime.now()", "source": "element:label"},
        ]
        results = self.converter.convert_batch(expressions)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["status"] == "success" for r in results))

    def test_summary(self):
        self.converter.convert("Total.sum(x)")
        self.converter.convert("BirtDateTime.now()")
        summary = self.converter.summary()
        self.assertEqual(summary["total"], 2)


class TestVisualMapper(unittest.TestCase):

    def setUp(self):
        self.mapper = VisualMapper()

    def test_map_table_element(self):
        element = {
            "element_type": "table",
            "name": "SalesTable",
            "dataset": "SalesData",
            "columns": [{"name": "col1", "expression": "row[\"id\"]"}],
            "groups": [],
            "properties": {},
            "children": [],
            "expressions": [],
        }
        visual = self.mapper.map_element(element)
        self.assertEqual(visual["visual_type"], "tableEx")
        self.assertEqual(visual["dataset"], "SalesData")

    def test_map_bar_chart(self):
        element = {
            "element_type": "extended-item",
            "extension_name": "Chart",
            "name": "BarChart",
            "chart_config": {"chart_type": "bar"},
            "properties": {},
            "children": [],
            "expressions": [],
        }
        visual = self.mapper.map_element(element)
        self.assertEqual(visual["visual_type"], "clusteredBarChart")

    def test_map_pie_chart(self):
        element = {
            "element_type": "extended-item",
            "extension_name": "Chart",
            "name": "PieChart",
            "chart_config": {"chart_type": "pie"},
            "properties": {},
            "children": [],
            "expressions": [],
        }
        visual = self.mapper.map_element(element)
        self.assertEqual(visual["visual_type"], "pieChart")

    def test_map_crosstab(self):
        element = {
            "element_type": "extended-item",
            "extension_name": "Crosstab",
            "name": "CT1",
            "chart_config": {},
            "properties": {},
            "children": [],
            "expressions": [],
        }
        visual = self.mapper.map_element(element)
        self.assertEqual(visual["visual_type"], "pivotTable")

    def test_map_label(self):
        element = {
            "element_type": "label",
            "name": "Title",
            "properties": {"fontFamily": "Arial"},
            "children": [],
            "expressions": [],
        }
        visual = self.mapper.map_element(element)
        self.assertEqual(visual["visual_type"], "textbox")

    def test_map_unknown_fallback(self):
        element = {
            "element_type": "unknown_element",
            "name": "x",
            "properties": {},
            "children": [],
            "expressions": [],
        }
        visual = self.mapper.map_element(element)
        self.assertEqual(visual["visual_type"], "textbox")

    def test_map_all(self):
        elements = [
            {"element_type": "table", "name": "T1", "dataset": "D1", "columns": [],
             "groups": [], "properties": {}, "children": [], "expressions": []},
            {"element_type": "label", "name": "L1", "properties": {},
             "children": [], "expressions": []},
        ]
        visuals = self.mapper.map_all(elements)
        self.assertEqual(len(visuals), 2)

    def test_style_mapping(self):
        element = {
            "element_type": "label",
            "name": "styled",
            "properties": {
                "fontFamily": "Arial",
                "fontSize": "12pt",
                "fontWeight": "bold",
                "color": "#FF0000",
            },
            "children": [],
            "expressions": [],
        }
        visual = self.mapper.map_element(element)
        style = visual["style"]
        self.assertEqual(style["fontFamily"], "Arial")
        self.assertTrue(style["bold"])
        self.assertEqual(style["fontColor"], "#FF0000")


class TestPBIPGenerator(unittest.TestCase):

    def test_generate_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = PBIPGenerator(report_name="TestReport")
            files = gen.generate(visuals=[], output_dir=tmpdir)
            self.assertIn(".pbip", files)
            self.assertIn("definition.pbir", files)

    def test_generate_with_visuals(self):
        visuals = [
            {"visual_type": "tableEx", "name": "T1", "position": {"x": 0, "y": 0},
             "size": {"width": 400, "height": 300}, "columns": [{"name": "col1"}], "style": {}},
            {"visual_type": "pieChart", "name": "P1", "position": {"x": 0, "y": 0},
             "size": {"width": 300, "height": 300}, "style": {}},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = PBIPGenerator(report_name="TestReport")
            files = gen.generate(visuals=visuals, output_dir=tmpdir)
            self.assertIn("page_0", files)
            # Check PBIP file exists
            pbip_path = files[".pbip"]
            self.assertTrue(pbip_path.exists())

    def test_multiple_pages(self):
        visuals = [
            {"visual_type": "card", "name": f"V{i}", "position": {"x": 0, "y": 0},
             "size": {"width": 200, "height": 100}, "style": {}}
            for i in range(15)
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = PBIPGenerator()
            files = gen.generate(visuals=visuals, output_dir=tmpdir)
            # Should have 2 pages (10 per page)
            self.assertIn("page_0", files)
            self.assertIn("page_1", files)


if __name__ == "__main__":
    unittest.main()
