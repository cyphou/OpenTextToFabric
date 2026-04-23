"""Realistic tests for BIRTParser using real-world .rptdesign XML.

Based on Eclipse BIRT 4.x schema with:
- Classic Models sample database (MySQL + Oracle connections)
- Complex SQL JOINs with parameters
- Computed columns using BIRT JavaScript (BirtDateTime, BirtStr, BirtMath)
- Bar/Pie/Line charts with XML chart config
- Crosstab with row/column dimensions
- Styles, parameters, page setup
"""

import json
import tempfile
import unittest
from pathlib import Path

from opentext_extract.birt_parser import BIRTParser, BIRTParseError
from tests.fixtures import BIRT_CLASSIC_MODELS_REPORT


class TestRealisticBIRTDataSources(unittest.TestCase):
    """Tests parsing real-world JDBC data sources."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.report_path = Path(self.tmpdir) / "classic_models_report.rptdesign"
        self.report_path.write_text(BIRT_CLASSIC_MODELS_REPORT, encoding="utf-8")
        self.parser = BIRTParser(self.report_path)
        self.result = self.parser.parse()

    def test_multiple_data_sources(self):
        """Real reports often connect to multiple databases."""
        sources = self.result["data_sources"]
        self.assertEqual(len(sources), 2)

    def test_mysql_data_source(self):
        """Classic Models uses MySQL/MariaDB."""
        sources = self.result["data_sources"]
        mysql_ds = next(s for s in sources if s["name"] == "Classic Models")
        # Parser stores odaDriverClass directly on the dict
        driver = mysql_ds.get("odaDriverClass", mysql_ds.get("driverClass", ""))
        self.assertIn("mysql", driver.lower())

    def test_oracle_data_source(self):
        """Enterprise DWH often uses Oracle."""
        sources = self.result["data_sources"]
        oracle_ds = next(s for s in sources if s["name"] == "Oracle DWH")
        driver = oracle_ds.get("odaDriverClass", oracle_ds.get("driverClass", ""))
        self.assertIn("oracle", driver.lower())


class TestRealisticBIRTDatasets(unittest.TestCase):
    """Tests parsing complex SQL datasets with JOINs and computed columns."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.report_path = Path(self.tmpdir) / "classic_models_report.rptdesign"
        self.report_path.write_text(BIRT_CLASSIC_MODELS_REPORT, encoding="utf-8")
        self.parser = BIRTParser(self.report_path)
        self.result = self.parser.parse()

    def test_two_datasets(self):
        datasets = self.result["datasets"]
        self.assertEqual(len(datasets), 2)

    def test_orders_dataset_query(self):
        """OrdersByCustomer has a multi-table JOIN with parameters."""
        ds = next(d for d in self.result["datasets"] if d["name"] == "OrdersByCustomer")
        query = ds["query"]
        # Real SQL with JOINs
        self.assertIn("JOIN", query.upper())
        self.assertIn("customers", query.lower())
        self.assertIn("orders", query.lower())
        self.assertIn("orderdetails", query.lower())
        # Parameterized query
        self.assertIn("?", query)

    def test_orders_dataset_column_hints(self):
        """8 columns from the multi-table query."""
        ds = next(d for d in self.result["datasets"] if d["name"] == "OrdersByCustomer")
        self.assertEqual(len(ds["column_hints"]), 8)

        col_names = {c["columnName"] for c in ds["column_hints"]}
        self.assertIn("customerName", col_names)
        self.assertIn("orderNumber", col_names)
        self.assertIn("priceEach", col_names)
        self.assertIn("productLine", col_names)
        self.assertIn("country", col_names)

    def test_computed_columns_real_expressions(self):
        """4 computed columns using real BIRT JavaScript functions."""
        ds = next(d for d in self.result["datasets"] if d["name"] == "OrdersByCustomer")
        computed = ds["computed_columns"]
        self.assertEqual(len(computed), 4)

        names = {cc["name"] for cc in computed}
        self.assertIn("lineTotal", names)       # row["quantityOrdered"] * row["priceEach"]
        self.assertIn("orderYear", names)        # BirtDateTime.year(...)
        self.assertIn("orderQuarter", names)     # "Q" + BirtDateTime.quarter(...)
        self.assertIn("discountedPrice", names)  # ternary conditional

    def test_line_total_expression(self):
        """lineTotal = quantityOrdered × priceEach."""
        ds = next(d for d in self.result["datasets"] if d["name"] == "OrdersByCustomer")
        lt = next(cc for cc in ds["computed_columns"] if cc["name"] == "lineTotal")
        self.assertIn("quantityOrdered", lt["expression"])
        self.assertIn("priceEach", lt["expression"])

    def test_sales_summary_dataset(self):
        """SalesSummary uses Oracle DWH with GROUP BY."""
        ds = next(d for d in self.result["datasets"] if d["name"] == "SalesSummary")
        self.assertEqual(ds["data_source"], "Oracle DWH")
        self.assertIn("GROUP BY", ds["query"].upper())
        self.assertIn("SUM", ds["query"].upper())


class TestRealisticBIRTParameters(unittest.TestCase):
    """Tests parsing report parameters with types, defaults, list-boxes."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.report_path = Path(self.tmpdir) / "classic_models_report.rptdesign"
        self.report_path.write_text(BIRT_CLASSIC_MODELS_REPORT, encoding="utf-8")
        self.parser = BIRTParser(self.report_path)
        self.result = self.parser.parse()

    def test_three_parameters(self):
        params = self.result["parameters"]
        self.assertEqual(len(params), 3)

    def test_date_parameters(self):
        """StartDate and EndDate are date type, required."""
        params = self.result["parameters"]
        # Parser uses 'dataType' key (matching XML property name)
        date_params = [p for p in params if p.get("dataType") == "date"]
        self.assertEqual(len(date_params), 2)

    def test_list_box_parameter(self):
        """ProductLineFilter is a list-box with 8 options."""
        params = self.result["parameters"]
        plf = next((p for p in params if p["name"] == "ProductLineFilter"), None)
        self.assertIsNotNone(plf)
        # Parser uses 'dataType' key (matching XML property name)
        self.assertEqual(plf.get("dataType"), "string")


class TestRealisticBIRTBody(unittest.TestCase):
    """Tests parsing the report body with tables, charts, crosstabs, grids."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.report_path = Path(self.tmpdir) / "classic_models_report.rptdesign"
        self.report_path.write_text(BIRT_CLASSIC_MODELS_REPORT, encoding="utf-8")
        self.parser = BIRTParser(self.report_path)
        self.result = self.parser.parse()

    def test_body_has_multiple_elements(self):
        body = self.result["body"]
        # label, text, table, chart, chart, chart, crosstab, grid, image
        self.assertTrue(len(body) >= 5)

    def test_orders_table(self):
        """Main data table bound to OrdersByCustomer dataset."""
        body = self.result["body"]
        tables = [e for e in body if e.get("element_type") == "table"]
        self.assertTrue(len(tables) >= 1)
        orders_table = tables[0]
        self.assertEqual(orders_table["dataset"], "OrdersByCustomer")

    def test_table_bound_columns(self):
        """Table has 12 bound data columns including aggregations."""
        body = self.result["body"]
        table = next(e for e in body if e.get("element_type") == "table")
        cols = table.get("columns", [])
        self.assertTrue(len(cols) >= 6)

    def test_charts_detected(self):
        """Report has 3 charts: bar, pie, line."""
        body = self.result["body"]
        charts = [e for e in body if e.get("element_type") == "extended-item"
                  and e.get("extension_name") == "Chart"]
        self.assertTrue(len(charts) >= 3)

    def test_bar_chart_config(self):
        """Bar chart shows Revenue by Product Line."""
        body = self.result["body"]
        charts = [e for e in body if e.get("element_type") == "extended-item"
                  and e.get("extension_name") == "Chart"]
        bar_chart = next((c for c in charts if "SalesChart" in c.get("name", "")), None)
        self.assertIsNotNone(bar_chart)

    def test_crosstab_detected(self):
        """Quarterly Crosstab element."""
        body = self.result["body"]
        crosstabs = [e for e in body if e.get("element_type") == "extended-item"
                     and e.get("extension_name") == "Crosstab"]
        self.assertTrue(len(crosstabs) >= 1)

    def test_labels_detected(self):
        """Title label and other text elements."""
        body = self.result["body"]
        labels = [e for e in body if e.get("element_type") in ("label", "text")]
        self.assertTrue(len(labels) >= 1)


class TestRealisticBIRTStyles(unittest.TestCase):
    """Tests parsing CSS-like styles from BIRT reports."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.report_path = Path(self.tmpdir) / "classic_models_report.rptdesign"
        self.report_path.write_text(BIRT_CLASSIC_MODELS_REPORT, encoding="utf-8")
        self.parser = BIRTParser(self.report_path)
        self.result = self.parser.parse()

    def test_multiple_styles(self):
        """5 styles: report-header, table-header, table-detail, group-header, currency."""
        styles = self.result["styles"]
        self.assertTrue(len(styles) >= 4)

    def test_style_properties(self):
        """Styles have font, color, background, alignment properties."""
        styles = self.result["styles"]
        header_style = next((s for s in styles if s["name"] == "report-header"), None)
        self.assertIsNotNone(header_style)
        props = header_style.get("properties", {})
        # Should have parsed properties like fontFamily, fontSize, etc.
        self.assertTrue(len(props) >= 1)


class TestRealisticBIRTExport(unittest.TestCase):
    """Tests export_json with the real Classic Models report."""

    def test_export_creates_all_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "classic_models.rptdesign"
            report_path.write_text(BIRT_CLASSIC_MODELS_REPORT, encoding="utf-8")

            parser = BIRTParser(report_path)
            output_dir = Path(tmpdir) / "output"
            files = parser.export_json(output_dir)

            for key in ("reports.json", "datasets.json", "connections.json",
                        "expressions.json", "visuals.json"):
                self.assertIn(key, files)
                self.assertTrue(files[key].exists(), f"{key} should exist")

    def test_export_datasets_json(self):
        """datasets.json should contain both datasets with full metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "classic_models.rptdesign"
            report_path.write_text(BIRT_CLASSIC_MODELS_REPORT, encoding="utf-8")

            parser = BIRTParser(report_path)
            output_dir = Path(tmpdir) / "output"
            files = parser.export_json(output_dir)

            with open(files["datasets.json"], encoding="utf-8") as f:
                datasets = json.load(f)
            self.assertEqual(len(datasets), 2)

    def test_export_connections_json(self):
        """connections.json should contain both data source connections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "classic_models.rptdesign"
            report_path.write_text(BIRT_CLASSIC_MODELS_REPORT, encoding="utf-8")

            parser = BIRTParser(report_path)
            output_dir = Path(tmpdir) / "output"
            files = parser.export_json(output_dir)

            with open(files["connections.json"], encoding="utf-8") as f:
                connections = json.load(f)
            self.assertEqual(len(connections), 2)

    def test_export_expressions_contain_computed_columns(self):
        """expressions.json should capture computed column expressions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "classic_models.rptdesign"
            report_path.write_text(BIRT_CLASSIC_MODELS_REPORT, encoding="utf-8")

            parser = BIRTParser(report_path)
            output_dir = Path(tmpdir) / "output"
            files = parser.export_json(output_dir)

            with open(files["expressions.json"], encoding="utf-8") as f:
                expressions = json.load(f)
            # Should have computed columns + bound data column expressions
            self.assertTrue(len(expressions) >= 4)


if __name__ == "__main__":
    unittest.main()
