"""Tests for opentext_extract.birt_parser."""

import tempfile
import unittest
from pathlib import Path

from opentext_extract.birt_parser import BIRTParser, BIRTParseError


SAMPLE_RPTDESIGN = """<?xml version="1.0" encoding="UTF-8"?>
<report version="3.2.23">
    <data-sources>
        <oda-data-source name="SampleDB" id="1">
            <property name="extensionID">org.eclipse.birt.report.data.oda.jdbc</property>
            <property name="odaDriverClass">oracle.jdbc.OracleDriver</property>
            <property name="odaURL">jdbc:oracle:thin:@host:1521:xe</property>
            <property name="odaUser">scott</property>
        </oda-data-source>
    </data-sources>
    <data-sets>
        <oda-data-set name="SalesData" id="2">
            <property name="dataSource">SampleDB</property>
            <property name="queryText">SELECT id, name, amount FROM sales</property>
            <list-property name="computedColumns">
                <structure>
                    <property name="name">TotalAmount</property>
                    <property name="dataType">float</property>
                    <expression name="expression" type="javascript">row["amount"] * 1.1</expression>
                </structure>
            </list-property>
            <list-property name="columnHints">
                <structure>
                    <property name="columnName">id</property>
                    <property name="dataType">integer</property>
                </structure>
                <structure>
                    <property name="columnName">name</property>
                    <property name="dataType">string</property>
                </structure>
                <structure>
                    <property name="columnName">amount</property>
                    <property name="dataType">float</property>
                </structure>
            </list-property>
        </oda-data-set>
    </data-sets>
    <parameters>
        <scalar-parameter name="StartDate" id="3">
            <property name="dataType">date</property>
            <property name="isRequired">true</property>
            <property name="promptText">Enter start date</property>
        </scalar-parameter>
    </parameters>
    <styles>
        <style name="HeaderStyle">
            <property name="fontFamily">Arial</property>
            <property name="fontSize">12pt</property>
            <property name="fontWeight">bold</property>
        </style>
    </styles>
    <page-setup>
        <simple-master-page name="Simple MasterPage" id="4">
            <property name="type">a4</property>
        </simple-master-page>
    </page-setup>
    <body>
        <table name="SalesTable" id="5">
            <property name="dataSet">SalesData</property>
            <list-property name="boundDataColumns">
                <structure>
                    <property name="name">col_id</property>
                    <expression name="expression" type="javascript">dataSetRow["id"]</expression>
                </structure>
                <structure>
                    <property name="name">col_name</property>
                    <expression name="expression" type="javascript">dataSetRow["name"]</expression>
                </structure>
            </list-property>
        </table>
        <label name="Footer" id="6">
            <property name="fontFamily">Verdana</property>
        </label>
    </body>
</report>
"""


class TestBIRTParser(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.report_path = Path(self.tmpdir) / "test_report.rptdesign"
        self.report_path.write_text(SAMPLE_RPTDESIGN, encoding="utf-8")
        self.parser = BIRTParser(self.report_path)

    def test_parse_returns_dict(self):
        result = self.parser.parse()
        self.assertIsInstance(result, dict)
        self.assertEqual(result["report_name"], "test_report")

    def test_parse_data_sources(self):
        result = self.parser.parse()
        sources = result["data_sources"]
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["name"], "SampleDB")
        self.assertEqual(sources[0].get("extension_id", ""), "org.eclipse.birt.report.data.oda.jdbc")

    def test_parse_datasets(self):
        result = self.parser.parse()
        datasets = result["datasets"]
        self.assertEqual(len(datasets), 1)
        self.assertEqual(datasets[0]["name"], "SalesData")
        self.assertEqual(datasets[0]["data_source"], "SampleDB")
        self.assertIn("SELECT", datasets[0]["query"])

    def test_parse_computed_columns(self):
        result = self.parser.parse()
        ds = result["datasets"][0]
        self.assertTrue(len(ds["computed_columns"]) >= 1)
        cc = ds["computed_columns"][0]
        self.assertEqual(cc["name"], "TotalAmount")

    def test_parse_column_hints(self):
        result = self.parser.parse()
        ds = result["datasets"][0]
        self.assertEqual(len(ds["column_hints"]), 3)

    def test_parse_parameters(self):
        result = self.parser.parse()
        params = result["parameters"]
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0]["name"], "StartDate")

    def test_parse_body(self):
        result = self.parser.parse()
        body = result["body"]
        self.assertTrue(len(body) >= 2)
        table = body[0]
        self.assertEqual(table["element_type"], "table")
        self.assertEqual(table["dataset"], "SalesData")

    def test_parse_table_columns(self):
        result = self.parser.parse()
        table = result["body"][0]
        cols = table.get("columns", [])
        self.assertEqual(len(cols), 2)

    def test_parse_styles(self):
        result = self.parser.parse()
        styles = result["styles"]
        self.assertEqual(len(styles), 1)
        self.assertEqual(styles[0]["name"], "HeaderStyle")

    def test_parse_page_setup(self):
        result = self.parser.parse()
        setup = result["page_setup"]
        self.assertTrue(len(setup["master_pages"]) >= 1)


class TestBIRTParserErrors(unittest.TestCase):

    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            BIRTParser("/nonexistent/report.rptdesign")

    def test_invalid_xml(self):
        with tempfile.NamedTemporaryFile(suffix=".rptdesign", mode="w", delete=False, encoding="utf-8") as f:
            f.write("<invalid><xml>")
            f.flush()
            parser = BIRTParser(f.name)
            with self.assertRaises(BIRTParseError):
                parser.parse()


class TestBIRTExportJSON(unittest.TestCase):

    def test_export_creates_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "test.rptdesign"
            report_path.write_text(SAMPLE_RPTDESIGN, encoding="utf-8")

            parser = BIRTParser(report_path)
            output_dir = Path(tmpdir) / "output"
            files = parser.export_json(output_dir)

            self.assertIn("reports.json", files)
            self.assertIn("datasets.json", files)
            self.assertIn("connections.json", files)
            self.assertIn("expressions.json", files)
            self.assertIn("visuals.json", files)

            for path in files.values():
                self.assertTrue(path.exists())

    def test_export_expressions_collected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "test.rptdesign"
            report_path.write_text(SAMPLE_RPTDESIGN, encoding="utf-8")

            parser = BIRTParser(report_path)
            output_dir = Path(tmpdir) / "output"
            files = parser.export_json(output_dir)

            import json
            with open(files["expressions.json"], encoding="utf-8") as f:
                expressions = json.load(f)
            # Should have computed column expression + table column expressions
            self.assertTrue(len(expressions) >= 1)


if __name__ == "__main__":
    unittest.main()
