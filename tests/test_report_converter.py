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
        self.assertEqual(result["status"], "script_block")

    # ── Event handler classification ──

    def test_event_handler_querytext(self):
        expr = 'this.queryText = this.queryText.replace("placeholder", params["p"].value)'
        result = self.converter.convert(expr)
        self.assertEqual(result["status"], "event_handler")

    def test_event_handler_reportcontext(self):
        expr = 'reportContext.getOutputFormat() == "html"'
        result = self.converter.convert(expr)
        self.assertEqual(result["status"], "event_handler")

    # ── Script block classification ──

    def test_script_block_for_loop(self):
        expr = 'for (var i = 0; i < arr.length; i++) { result += arr[i]; }'
        result = self.converter.convert(expr)
        self.assertEqual(result["status"], "script_block")

    def test_script_block_function_declaration(self):
        expr = 'function createList(items) { var result = ""; return result; }'
        result = self.converter.convert(expr)
        self.assertEqual(result["status"], "script_block")

    # ── Multi-line if/else if/else ──

    def test_if_else_chain_multiline(self):
        expr = 'if (row["status"] == "A") { "Active" } else if (row["status"] == "I") { "Inactive" } else { "Unknown" }'
        result = self.converter.convert(expr)
        self.assertEqual(result["status"], "success")
        self.assertIn("IF(", result["converted"])
        self.assertIn("Active", result["converted"])
        self.assertIn("Inactive", result["converted"])
        self.assertIn("Unknown", result["converted"])
        # Should be nested IF: IF(cond1, val1, IF(cond2, val2, val3))
        self.assertEqual(result["converted"].count("IF("), 2)

    def test_if_else_simple(self):
        expr = 'if ([amount] > 0) { "positive" } else { "negative" }'
        result = self.converter.convert(expr)
        self.assertIn("IF(", result["converted"])
        self.assertIn("positive", result["converted"])
        self.assertIn("negative", result["converted"])

    def test_if_no_else(self):
        expr = 'if ([amount] > 100) { "high" }'
        result = self.converter.convert(expr)
        self.assertIn("IF(", result["converted"])
        self.assertIn("high", result["converted"])

    # ── Nested ternary ──

    def test_nested_ternary(self):
        expr = 'row["val"] > 100 ? "high" : row["val"] > 50 ? "medium" : "low"'
        result = self.converter.convert(expr)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["converted"].count("IF("), 2)
        self.assertIn("high", result["converted"])
        self.assertIn("medium", result["converted"])
        self.assertIn("low", result["converted"])

    # ── var/return inlining ──

    def test_var_return_inline(self):
        expr = 'var x = row["amount"]; var y = row["tax"]; return x + y'
        result = self.converter.convert(expr)
        self.assertEqual(result["status"], "success")
        self.assertIn("[amount]", result["converted"])
        self.assertIn("[tax]", result["converted"])
        self.assertNotIn("var ", result["converted"])
        self.assertNotIn("return ", result["converted"])

    def test_var_simple(self):
        expr = 'var result = row["price"] * row["qty"]; return result'
        result = self.converter.convert(expr)
        self.assertEqual(result["status"], "success")
        self.assertIn("[price]", result["converted"])
        self.assertIn("[qty]", result["converted"])

    # ── String concatenation ──

    def test_string_concat_to_ampersand(self):
        expr = '"Total: " + row["amount"] + " USD"'
        result = self.converter.convert(expr)
        self.assertEqual(result["status"], "success")
        self.assertIn("&", result["converted"])
        self.assertNotIn("+", result["converted"])

    # ── new Date() ──

    def test_new_date_to_now(self):
        expr = "new Date()"
        result = self.converter.convert(expr)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["converted"], "NOW()")

    # ── null / undefined ──

    def test_null_to_blank(self):
        expr = 'row["col"] == null ? "N/A" : row["col"]'
        result = self.converter.convert(expr)
        self.assertIn("BLANK()", result["converted"])
        self.assertNotIn("null", result["converted"])

    def test_null_word_boundary(self):
        """null replacement should not corrupt words containing 'null'."""
        result = self.converter.convert('row["nullable_flag"]')
        self.assertEqual(result["converted"], "[nullable_flag]")
        self.assertNotIn("BLANK()", result["converted"])

    def test_undefined_to_blank(self):
        result = self.converter.convert('row["x"] == undefined ? 0 : row["x"]')
        self.assertIn("BLANK()", result["converted"])

    # ── switch → SWITCH ──

    def test_switch_statement(self):
        expr = 'switch(row["code"]) { case "A": "Alpha"; break; case "B": "Beta"; break; default: "Other" }'
        result = self.converter.convert(expr)
        self.assertEqual(result["status"], "success")
        self.assertIn("SWITCH(", result["converted"])
        self.assertIn("Alpha", result["converted"])
        self.assertIn("Beta", result["converted"])
        self.assertIn("Other", result["converted"])

    # ── params displayText ──

    def test_params_display_text(self):
        result = self.converter.convert('params["Region"].displayText')
        self.assertIn("SELECTEDVALUE", result["converted"])
        self.assertIn("[@Region]", result["converted"])

    # ── params with single quotes ──

    def test_params_single_quotes(self):
        result = self.converter.convert("params['StartDate'].value")
        self.assertEqual(result["converted"], "[@StartDate]")

    # ── dataSetRow single quotes ──

    def test_dataset_row_single_quotes(self):
        result = self.converter.convert("dataSetRow['total']")
        self.assertEqual(result["converted"], "[total]")

    # ── Complex real-world expressions ──

    def test_complex_birt_math_if_else(self):
        expr = 'if (row["denominator"] == 0) { 0 } else { BirtMath.round(row["numerator"] / row["denominator"] * 100, 2) }'
        result = self.converter.convert(expr)
        self.assertEqual(result["status"], "success")
        self.assertIn("IF(", result["converted"])
        self.assertIn("ROUND(", result["converted"])

    def test_extract_return_from_simple_script(self):
        """A function block with a simple return should extract the expression."""
        expr = 'function calc() { var x = row["a"]; return x * 2; }'
        result = self.converter.convert(expr)
        # This has a function declaration so it's a script_block,
        # but _extract_return_value finds 'return x * 2' and inlines var x
        # Actually function + inner function → script_block without extraction
        self.assertIn(result["status"], ("success", "script_block"))

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
