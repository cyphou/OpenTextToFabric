"""Realistic end-to-end tests for the visual mapper and PBIP generator.

Tests the full pipeline: BIRT report elements → PBI visual mapping → .pbip generation.
Uses the Classic Models report fixture for realistic input.
"""

import json
import tempfile
import unittest
from pathlib import Path

from report_converter.visual_mapper import VisualMapper
from report_converter.pbip_generator import PBIPGenerator


class TestRealisticVisualMapping(unittest.TestCase):
    """Maps real BIRT report elements to Power BI visuals."""

    def setUp(self):
        self.mapper = VisualMapper()

    def test_map_orders_table(self):
        """Data table with bound columns and group → tableEx with columns."""
        element = {
            "element_type": "table",
            "name": "OrdersTable",
            "dataset": "OrdersByCustomer",
            "columns": [
                {"name": "customerName", "expression": 'dataSetRow["customerName"]'},
                {"name": "orderNumber", "expression": 'dataSetRow["orderNumber"]'},
                {"name": "orderDate", "expression": 'dataSetRow["orderDate"]'},
                {"name": "status", "expression": 'dataSetRow["status"]'},
                {"name": "productLine", "expression": 'dataSetRow["productLine"]'},
                {"name": "lineTotal", "expression": 'dataSetRow["lineTotal"]'},
            ],
            "groups": [{"name": "CustomerGroup", "key_expr": 'row["customerName"]'}],
            "properties": {"width": "100%"},
            "children": [],
            "expressions": [
                'Total.sum(row["lineTotal"])',
                'Total.countDistinct(row["orderNumber"])',
            ],
        }
        visual = self.mapper.map_element(element)
        self.assertEqual(visual["visual_type"], "tableEx")
        self.assertEqual(visual["dataset"], "OrdersByCustomer")

    def test_map_bar_chart(self):
        """Revenue by Product Line bar chart."""
        element = {
            "element_type": "extended-item",
            "extension_name": "Chart",
            "name": "SalesChart",
            "chart_config": {
                "chart_type": "bar",
                "chart_subtype": "side-by-side",
                "title": "Revenue by Product Line",
                "axes": [
                    {"type": "category", "title": "Product Line"},
                    {"type": "linear", "title": "Revenue ($)"},
                ],
            },
            "properties": {"width": "700px", "height": "400px"},
            "children": [],
            "expressions": [],
        }
        visual = self.mapper.map_element(element)
        self.assertEqual(visual["visual_type"], "clusteredBarChart")

    def test_map_pie_chart(self):
        """Revenue Distribution pie chart."""
        element = {
            "element_type": "extended-item",
            "extension_name": "Chart",
            "name": "SalesPieChart",
            "chart_config": {
                "chart_type": "pie",
                "title": "Revenue Distribution by Region",
            },
            "properties": {"width": "500px", "height": "400px"},
            "children": [],
            "expressions": [],
        }
        visual = self.mapper.map_element(element)
        self.assertEqual(visual["visual_type"], "pieChart")

    def test_map_line_chart(self):
        """Monthly Revenue Trend line chart."""
        element = {
            "element_type": "extended-item",
            "extension_name": "Chart",
            "name": "SalesLineChart",
            "chart_config": {
                "chart_type": "line",
                "title": "Monthly Revenue Trend",
            },
            "properties": {"width": "700px", "height": "350px"},
            "children": [],
            "expressions": [],
        }
        visual = self.mapper.map_element(element)
        self.assertEqual(visual["visual_type"], "lineChart")

    def test_map_crosstab(self):
        """Quarterly Crosstab → pivotTable."""
        element = {
            "element_type": "extended-item",
            "extension_name": "Crosstab",
            "name": "QuarterlyCrosstab",
            "chart_config": {},
            "properties": {"width": "100%"},
            "children": [],
            "expressions": [],
        }
        visual = self.mapper.map_element(element)
        self.assertEqual(visual["visual_type"], "pivotTable")

    def test_map_title_label(self):
        """Report title label → textbox."""
        element = {
            "element_type": "label",
            "name": "ReportTitle",
            "properties": {
                "fontFamily": "Arial",
                "fontSize": "18pt",
                "fontWeight": "bold",
                "color": "#003366",
                "textAlign": "center",
            },
            "children": [],
            "expressions": [],
        }
        visual = self.mapper.map_element(element)
        self.assertEqual(visual["visual_type"], "textbox")
        self.assertEqual(visual["style"]["fontFamily"], "Arial")
        self.assertTrue(visual["style"]["bold"])

    def test_map_all_classic_models_elements(self):
        """Map all elements from Classic Models report at once."""
        elements = [
            {"element_type": "label", "name": "Title", "properties": {}, "children": [], "expressions": []},
            {"element_type": "table", "name": "OrdersTable", "dataset": "OrdersByCustomer",
             "columns": [{"name": "c1"}], "groups": [], "properties": {}, "children": [], "expressions": []},
            {"element_type": "extended-item", "extension_name": "Chart", "name": "BarChart",
             "chart_config": {"chart_type": "bar"}, "properties": {}, "children": [], "expressions": []},
            {"element_type": "extended-item", "extension_name": "Chart", "name": "PieChart",
             "chart_config": {"chart_type": "pie"}, "properties": {}, "children": [], "expressions": []},
            {"element_type": "extended-item", "extension_name": "Chart", "name": "LineChart",
             "chart_config": {"chart_type": "line"}, "properties": {}, "children": [], "expressions": []},
            {"element_type": "extended-item", "extension_name": "Crosstab", "name": "Crosstab",
             "chart_config": {}, "properties": {}, "children": [], "expressions": []},
        ]
        visuals = self.mapper.map_all(elements)
        self.assertEqual(len(visuals), 6)

        visual_types = {v["visual_type"] for v in visuals}
        expected = {"textbox", "tableEx", "clusteredBarChart", "pieChart", "lineChart", "pivotTable"}
        self.assertEqual(visual_types, expected)


class TestRealisticPBIPGeneration(unittest.TestCase):
    """Generates .pbip from realistic Classic Models visuals."""

    def test_generate_classic_models_report(self):
        """Full .pbip generation from Classic Models visuals."""
        visuals = [
            {"visual_type": "textbox", "name": "Title", "position": {"x": 0, "y": 0},
             "size": {"width": 1280, "height": 60}, "style": {"bold": True, "fontSize": 18}},
            {"visual_type": "tableEx", "name": "OrdersTable", "position": {"x": 0, "y": 80},
             "size": {"width": 1280, "height": 400},
             "columns": [{"name": "customerName"}, {"name": "orderNumber"}, {"name": "lineTotal"}],
             "style": {}},
            {"visual_type": "clusteredBarChart", "name": "SalesChart", "position": {"x": 0, "y": 500},
             "size": {"width": 700, "height": 400}, "style": {}},
            {"visual_type": "pieChart", "name": "PieChart", "position": {"x": 720, "y": 500},
             "size": {"width": 500, "height": 400}, "style": {}},
            {"visual_type": "lineChart", "name": "LineChart", "position": {"x": 0, "y": 920},
             "size": {"width": 700, "height": 350}, "style": {}},
            {"visual_type": "pivotTable", "name": "Crosstab", "position": {"x": 720, "y": 920},
             "size": {"width": 500, "height": 350}, "style": {}},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            gen = PBIPGenerator(report_name="Classic_Models_Orders")
            files = gen.generate(visuals=visuals, output_dir=tmpdir)

            # Verify .pbip file
            self.assertIn(".pbip", files)
            pbip_path = files[".pbip"]
            self.assertTrue(pbip_path.exists())

            # Verify definition.pbir
            self.assertIn("definition.pbir", files)

            # All visuals fit on one page (6 visuals < 10 threshold)
            self.assertIn("page_0", files)

    def test_generate_large_report_multi_page(self):
        """Report with many visuals spans multiple pages."""
        visuals = [
            {"visual_type": "card", "name": f"Metric_{i}",
             "position": {"x": (i % 4) * 320, "y": (i // 4) * 200},
             "size": {"width": 300, "height": 180}, "style": {}}
            for i in range(22)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            gen = PBIPGenerator(report_name="KPI_Dashboard")
            files = gen.generate(visuals=visuals, output_dir=tmpdir)

            # Should have 3 pages (22 visuals / 10 per page)
            self.assertIn("page_0", files)
            self.assertIn("page_1", files)
            self.assertIn("page_2", files)


if __name__ == "__main__":
    unittest.main()
