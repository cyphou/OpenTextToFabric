"""Tests for reporting.generate_report dashboard builder."""

import json
import tempfile
import unittest
from pathlib import Path

from reporting.generate_report import generate_report, _build_report


def _write(out: Path, name: str, data) -> None:
    with open(out / name, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _make_fixture(out: Path) -> None:
    """Write a minimal set of extraction JSONs."""
    _write(out, "nodes.json", [
        {"id": "1", "name": "Enterprise", "type": "Folder"},
        {"id": "2", "name": "Finance", "type": "Folder"},
        {"id": "3", "name": "Report.pdf", "type": "Document"},
    ])
    _write(out, "documents.json", [
        {"name": "Report.pdf", "mime_type": "application/pdf"},
        {"name": "Data.xlsx", "mime_type": "application/vnd.ms-excel"},
    ])
    _write(out, "permissions.json", [
        {"name": "Admin", "rls_role": "Admin"},
        {"name": "Reader", "rls_role": ""},
    ])
    _write(out, "metadata.json", [
        {"key": "author", "type": "string"},
        {"key": "created", "type": "date"},
    ])
    _write(out, "expressions.json", [
        {"column_name": "total_sales", "expression": "Total.sum(sales)", "status": "success", "dax": "SUM(sales)"},
        {"column_name": "avg_price", "expression": "Total.ave(price)", "status": "partial", "dax": "AVERAGE(price)"},
        {"column_name": "custom_fn", "expression": "customFunc()", "status": "unsupported", "dax": ""},
    ])
    _write(out, "visuals.json", [
        {"name": "SalesChart", "type": "chart"},
        {"name": "SummaryTable", "type": "table"},
    ])
    _write(out, "datasets.json", [
        {"name": "SalesDS"},
        {"name": "InventoryDS"},
    ])
    _write(out, "connections.json", [
        {"name": "OracleConn", "driver": "oracle"},
    ])
    _write(out, "audit_trail.json", {
        "entries": [
            {"timestamp": "2025-01-01T00:00:00", "action": "extract", "source_type": "content-server", "source_name": "root", "status": "success", "details": "3 nodes"},
            {"timestamp": "2025-01-01T00:00:01", "action": "convert", "source_type": "birt", "source_name": "expr", "status": "warning", "details": "1 partial"},
        ],
    })


class TestBuildReport(unittest.TestCase):
    def test_builds_from_fixtures(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            _make_fixture(out)
            report = _build_report(out)
            self.assertEqual(len(report.by_category("nodes")), 3)
            self.assertEqual(len(report.by_category("documents")), 2)
            self.assertEqual(len(report.by_category("expressions")), 3)

    def test_expression_status_mapping(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            _make_fixture(out)
            report = _build_report(out)
            counts = report.status_counts("expressions")
            self.assertEqual(counts.get("EXACT", 0), 1)
            self.assertEqual(counts.get("APPROXIMATE", 0), 1)
            self.assertEqual(counts.get("UNSUPPORTED", 0), 1)

    def test_permission_status(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            _make_fixture(out)
            report = _build_report(out)
            counts = report.status_counts("permissions")
            self.assertEqual(counts.get("EXACT", 0), 1)
            self.assertEqual(counts.get("APPROXIMATE", 0), 1)

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as td:
            report = _build_report(Path(td))
            self.assertEqual(len(report.items), 0)
            self.assertAlmostEqual(report.overall_fidelity(), 100.0)


class TestGenerateReport(unittest.TestCase):
    def test_generates_html(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            _make_fixture(out)
            path = generate_report(output_dir=str(out))
            self.assertTrue(Path(path).exists())
            html = Path(path).read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", html)
            self.assertIn("OpenText", html)
            self.assertIn("Executive Summary", html)

    def test_contains_sections(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            _make_fixture(out)
            path = generate_report(output_dir=str(out))
            html = Path(path).read_text(encoding="utf-8")
            self.assertIn("Extraction Overview", html)
            self.assertIn("Content Inventory", html)
            self.assertIn("Governance", html)
            self.assertIn("Expression Conversion", html)
            self.assertIn("Fabric Artifacts", html)
            self.assertIn("BIRT Report Conversion", html)
            self.assertIn("Audit Trail", html)

    def test_contains_stat_cards(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            _make_fixture(out)
            path = generate_report(output_dir=str(out))
            html = Path(path).read_text(encoding="utf-8")
            self.assertIn("stat-card", html)
            self.assertIn("stat-grid", html)

    def test_contains_charts(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            _make_fixture(out)
            path = generate_report(output_dir=str(out))
            html = Path(path).read_text(encoding="utf-8")
            self.assertIn("donut-container", html)
            self.assertIn("bar-chart", html)

    def test_contains_tables(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            _make_fixture(out)
            path = generate_report(output_dir=str(out))
            html = Path(path).read_text(encoding="utf-8")
            self.assertIn("Report.pdf", html)
            self.assertIn("SalesChart", html)
            self.assertIn("OracleConn", html)

    def test_json_sidecar(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            _make_fixture(out)
            generate_report(output_dir=str(out))
            json_path = out / "migration_report.json"
            self.assertTrue(json_path.exists())
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("overall_fidelity", data)
            self.assertGreater(data["total_items"], 0)

    def test_custom_report_path(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            _make_fixture(out)
            custom = str(out / "custom" / "my_report.html")
            path = generate_report(output_dir=str(out), report_path=custom)
            self.assertEqual(path, custom)
            self.assertTrue(Path(path).exists())

    def test_empty_output_dir(self):
        with tempfile.TemporaryDirectory() as td:
            path = generate_report(output_dir=td)
            self.assertTrue(Path(path).exists())
            html = Path(path).read_text(encoding="utf-8")
            self.assertIn("Executive Summary", html)

    def test_dark_mode_css(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            _make_fixture(out)
            path = generate_report(output_dir=str(out))
            html = Path(path).read_text(encoding="utf-8")
            self.assertIn("html.dark", html)
            self.assertIn("toggleTheme", html)

    def test_flow_diagram_present(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            _make_fixture(out)
            path = generate_report(output_dir=str(out))
            html = Path(path).read_text(encoding="utf-8")
            self.assertIn("flow-container", html)
            self.assertIn("OpenText ECM", html)
            self.assertIn("Fabric / Power BI", html)

    def test_xss_safety(self):
        """Ensure user-controlled data is HTML-escaped."""
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            _write(out, "nodes.json", [
                {"id": "1", "name": "<script>alert(1)</script>", "type": "Folder"},
            ])
            path = generate_report(output_dir=str(out))
            html = Path(path).read_text(encoding="utf-8")
            self.assertNotIn("<script>alert(1)</script>", html)
            self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
