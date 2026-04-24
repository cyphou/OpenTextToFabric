"""Tests for ArtifactHealer and RecoveryReport."""

import json
import os
import re
import tempfile
import unittest
from pathlib import Path

from assessment.artifact_healer import ArtifactHealer
from assessment.recovery_report import RecoveryReport


class TestRecoveryReport(unittest.TestCase):
    """Tests for recovery audit trail."""

    def test_record_entry(self):
        report = RecoveryReport()
        entry = report.record(
            "dax", "birt_leak",
            description="test",
            action="fixed",
            item_name="measure1",
        )
        self.assertEqual(entry["category"], "dax")
        self.assertEqual(entry["repair_type"], "birt_leak")
        self.assertEqual(len(report.entries), 1)

    def test_summary_counts(self):
        report = RecoveryReport()
        report.record("dax", "birt_leak", item_name="m1")
        report.record("dax", "balanced_parens", item_name="m2")
        report.record("tmdl", "duplicate_column", item_name="t1")
        report.record("pbir", "missing_visual_type", follow_up=True)

        summary = report.get_summary()
        self.assertEqual(summary["total_repairs"], 4)
        self.assertEqual(summary["by_category"]["dax"], 2)
        self.assertEqual(summary["by_category"]["tmdl"], 1)
        self.assertEqual(summary["by_category"]["pbir"], 1)
        self.assertEqual(summary["follow_up_needed"], 1)

    def test_save_json(self):
        report = RecoveryReport()
        report.record("dax", "test", item_name="x")
        with tempfile.TemporaryDirectory() as tmp:
            path = report.save(tmp)
            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["summary"]["total_repairs"], 1)
            self.assertEqual(len(data["entries"]), 1)

    def test_empty_report(self):
        report = RecoveryReport()
        summary = report.get_summary()
        self.assertEqual(summary["total_repairs"], 0)
        self.assertEqual(summary["follow_up_needed"], 0)


class TestHealDAX(unittest.TestCase):
    """Tests for DAX healing rules."""

    def setUp(self):
        self.healer = ArtifactHealer()

    def test_birt_leak_total_sum(self):
        result = self.healer.heal_dax("Total.sum([Revenue])", "m1")
        self.assertEqual(result, "SUM([Revenue])")

    def test_birt_leak_count(self):
        result = self.healer.heal_dax("Total.count()", "m1")
        self.assertEqual(result, "COUNTROWS()")

    def test_birt_leak_ave(self):
        result = self.healer.heal_dax("Total.ave([Price])", "m1")
        self.assertEqual(result, "AVERAGE([Price])")

    def test_birt_leak_datetime(self):
        result = self.healer.heal_dax("BirtDateTime.year([Date])", "m1")
        self.assertEqual(result, "YEAR([Date])")

    def test_birt_leak_string(self):
        result = self.healer.heal_dax("BirtStr.toUpper([Name])", "m1")
        self.assertEqual(result, "UPPER([Name])")

    def test_row_reference_double_quotes(self):
        result = self.healer.heal_dax('row["Revenue"] * 2', "m1")
        self.assertEqual(result, "[Revenue] * 2")

    def test_row_reference_single_quotes(self):
        result = self.healer.heal_dax("row['Cost']", "m1")
        self.assertEqual(result, "[Cost]")

    def test_dataset_row_reference(self):
        result = self.healer.heal_dax('dataSetRow["Amount"]', "m1")
        self.assertEqual(result, "[Amount]")

    def test_row_dot_reference(self):
        result = self.healer.heal_dax("row.Quantity + 1", "m1")
        self.assertEqual(result, "[Quantity] + 1")

    def test_balanced_parens_missing_close(self):
        result = self.healer.heal_dax("SUM(FILTER(ALL(), [x] > 0)", "m1")
        self.assertEqual(result, "SUM(FILTER(ALL(), [x] > 0))")

    def test_balanced_parens_ok(self):
        result = self.healer.heal_dax("SUM([Revenue])", "m1")
        self.assertEqual(result, "SUM([Revenue])")

    def test_line_comment_js_to_dax(self):
        result = self.healer.heal_dax("SUM([Revenue]) // total revenue", "m1")
        self.assertEqual(result, "SUM([Revenue]) --  total revenue")

    def test_line_comment_preserves_url(self):
        result = self.healer.heal_dax('"https://example.com"', "m1")
        self.assertEqual(result, '"https://example.com"')

    def test_self_reference(self):
        result = self.healer.heal_dax("[Revenue] / 100", "Revenue")
        self.assertEqual(result, '"Revenue: self-reference removed"')

    def test_self_reference_multiple_refs(self):
        """All refs to self → replaced."""
        result = self.healer.heal_dax("[Sales] + [Sales]", "Sales")
        self.assertEqual(result, '"Sales: self-reference removed"')

    def test_no_self_reference_mixed_refs(self):
        """Mixed refs → not self-referencing."""
        result = self.healer.heal_dax("[Revenue] / [Total]", "Revenue")
        self.assertEqual(result, "[Revenue] / [Total]")

    def test_empty_formula(self):
        result = self.healer.heal_dax("", "m1")
        self.assertEqual(result, "")

    def test_none_formula(self):
        result = self.healer.heal_dax(None, "m1")
        self.assertIsNone(result)

    def test_combined_healing(self):
        """Multiple issues in one formula."""
        result = self.healer.heal_dax('Total.sum(row["Revenue"])', "m1")
        self.assertEqual(result, "SUM([Revenue])")

    def test_healing_records_report(self):
        """Verify healing actions are recorded."""
        self.healer.heal_dax("Total.sum([X])", "measure1")
        self.assertGreater(len(self.healer.report.entries), 0)
        entry = self.healer.report.entries[0]
        self.assertEqual(entry["category"], "dax")
        self.assertEqual(entry["repair_type"], "birt_leak")


class TestHealMExpression(unittest.TestCase):
    """Tests for M query healing."""

    def setUp(self):
        self.healer = ArtifactHealer()

    def test_balanced_parens(self):
        result = self.healer.heal_m_expression("Sql.Database(server, db", "q1")
        self.assertEqual(result, "Sql.Database(server, db)")

    def test_balanced_braces(self):
        result = self.healer.heal_m_expression("#table(type table [{a}], {", "q1")
        # Parens fixed first (appends ')'), then braces (appends '}')
        self.assertEqual(result, "#table(type table [{a}], {)}")

    def test_let_in_balance(self):
        result = self.healer.heal_m_expression("let\n    Source = 1,", "q1")
        self.assertIn("in", result)
        self.assertIn("Source", result)

    def test_placeholder_replacement(self):
        result = self.healer.heal_m_expression("Table.Sort({prev})", "q1")
        self.assertEqual(result, "Table.Sort(Source)")

    def test_valid_expression_unchanged(self):
        expr = '#table(type table [{"a" = Text.Type}], {})'
        result = self.healer.heal_m_expression(expr, "q1")
        self.assertEqual(result, expr)


class TestHealTMDL(unittest.TestCase):
    """Tests for TMDL file healing."""

    def setUp(self):
        self.healer = ArtifactHealer()

    def _make_project(self, tmp: str, model_tmdl: str = "", tables: dict[str, str] | None = None,
                      relationships: str = "", report_files: dict[str, str] | None = None) -> Path:
        """Create a minimal .pbip project structure for testing."""
        root = Path(tmp) / "TestProject"
        sm_dir = root / "TestModel.SemanticModel" / "definition"
        sm_dir.mkdir(parents=True)

        if model_tmdl:
            (sm_dir / "model.tmdl").write_text(model_tmdl, encoding="utf-8")

        if tables:
            tables_dir = sm_dir / "tables"
            tables_dir.mkdir()
            for name, content in tables.items():
                (tables_dir / f"{name}.tmdl").write_text(content, encoding="utf-8")

        if relationships:
            (sm_dir / "relationships.tmdl").write_text(relationships, encoding="utf-8")

        if report_files:
            report_dir = root / "TestModel.Report"
            for rel_path, content in report_files.items():
                p = report_dir / rel_path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")

        return root

    def test_model_missing_culture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(
                tmp,
                model_tmdl="model Model\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n",
            )
            self.healer.heal_project(root)
            content = (root / "TestModel.SemanticModel" / "definition" / "model.tmdl").read_text()
            self.assertIn("culture:", content)

    def test_model_missing_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(
                tmp,
                model_tmdl="model Model\n\tculture: en-US\n",
            )
            self.healer.heal_project(root)
            content = (root / "TestModel.SemanticModel" / "definition" / "model.tmdl").read_text()
            self.assertIn("defaultPowerBIDataSourceVersion", content)

    def test_duplicate_columns_removed(self):
        tmdl = (
            "table Sales\n"
            "\tlineageTag: Sales\n\n"
            "\tcolumn Revenue\n"
            "\t\tdataType: double\n"
            "\t\tlineageTag: Revenue\n"
            "\t\tsummarizeBy: none\n\n"
            "\tcolumn Revenue\n"
            "\t\tdataType: int64\n"
            "\t\tlineageTag: Revenue2\n"
            "\t\tsummarizeBy: none\n\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(
                tmp,
                model_tmdl="model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n",
                tables={"Sales": tmdl},
            )
            self.healer.heal_project(root)
            content = (root / "TestModel.SemanticModel" / "definition" / "tables" / "Sales.tmdl").read_text()
            self.assertEqual(content.count("column Revenue"), 1)

    def test_data_type_normalisation(self):
        tmdl = (
            "table T1\n"
            "\tlineageTag: T1\n\n"
            "\tcolumn Price\n"
            "\t\tdataType: float\n"
            "\t\tlineageTag: Price\n"
            "\t\tsummarizeBy: none\n\n"
            "\tcolumn Name\n"
            "\t\tdataType: varchar\n"
            "\t\tlineageTag: Name\n"
            "\t\tsummarizeBy: none\n\n"
            "\tpartition T1 = m\n"
            "\t\tmode: import\n"
            "\t\tsource = #table({}, {})\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(
                tmp,
                model_tmdl="model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n",
                tables={"T1": tmdl},
            )
            self.healer.heal_project(root)
            content = (root / "TestModel.SemanticModel" / "definition" / "tables" / "T1.tmdl").read_text()
            self.assertIn("dataType: double", content)
            self.assertIn("dataType: string", content)
            self.assertNotIn("float", content)
            self.assertNotIn("varchar", content)

    def test_dax_healed_in_tmdl_measures(self):
        tmdl = (
            "table Sales\n"
            "\tlineageTag: Sales\n\n"
            "\tcolumn Revenue\n"
            "\t\tdataType: double\n"
            "\t\tlineageTag: Revenue\n"
            "\t\tsummarizeBy: none\n\n"
            '\tmeasure TotalRevenue = Total.sum([Revenue])\n'
            "\t\tlineageTag: TotalRevenue\n\n"
            "\tpartition Sales = m\n"
            "\t\tmode: import\n"
            "\t\tsource = #table({}, {})\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(
                tmp,
                model_tmdl="model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n",
                tables={"Sales": tmdl},
            )
            self.healer.heal_project(root)
            content = (root / "TestModel.SemanticModel" / "definition" / "tables" / "Sales.tmdl").read_text()
            self.assertIn("SUM([Revenue])", content)
            self.assertNotIn("Total.sum", content)

    def test_partition_m_wrapped(self):
        tmdl = (
            "table Orders\n"
            "\tlineageTag: Orders\n\n"
            "\tcolumn OrderId\n"
            "\t\tdataType: int64\n"
            "\t\tlineageTag: OrderId\n"
            "\t\tsummarizeBy: none\n\n"
            '\tpartition Orders = m\n'
            '\t\tmode: import\n'
            '\t\tsource = Sql.Database("server", "db")\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(
                tmp,
                model_tmdl="model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n",
                tables={"Orders": tmdl},
            )
            self.healer.heal_project(root)
            content = (root / "TestModel.SemanticModel" / "definition" / "tables" / "Orders.tmdl").read_text()
            self.assertIn("try", content)
            self.assertIn("otherwise #table({}, {})", content)

    def test_partition_m_table_not_wrapped(self):
        """#table literals should not be double-wrapped."""
        tmdl = (
            "table T1\n"
            "\tlineageTag: T1\n\n"
            "\tpartition T1 = m\n"
            "\t\tmode: import\n"
            "\t\tsource = #table({}, {})\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(
                tmp,
                model_tmdl="model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n",
                tables={"T1": tmdl},
            )
            self.healer.heal_project(root)
            content = (root / "TestModel.SemanticModel" / "definition" / "tables" / "T1.tmdl").read_text()
            self.assertNotIn("try", content)

    def test_orphan_relationship_removed(self):
        rel = (
            "\nrelationship rel_Sales_Missing_OrderId\n"
            "\tfromColumn: Sales.OrderId\n"
            "\ttoColumn: MissingTable.OrderId\n"
            "\tcrossFilteringBehavior: oneDirection\n"
        )
        tmdl = (
            "table Sales\n"
            "\tlineageTag: Sales\n\n"
            "\tcolumn OrderId\n"
            "\t\tdataType: int64\n"
            "\t\tlineageTag: OrderId\n"
            "\t\tsummarizeBy: none\n\n"
            "\tpartition Sales = m\n"
            "\t\tmode: import\n"
            "\t\tsource = #table({}, {})\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(
                tmp,
                model_tmdl="model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n",
                tables={"Sales": tmdl},
                relationships=rel,
            )
            self.healer.heal_project(root)
            content = (root / "TestModel.SemanticModel" / "definition" / "relationships.tmdl").read_text()
            self.assertNotIn("MissingTable", content)

    def test_valid_relationship_kept(self):
        rel = (
            "\nrelationship rel_Sales_Products_ProductId\n"
            "\tfromColumn: Sales.ProductId\n"
            "\ttoColumn: Products.ProductId\n"
            "\tcrossFilteringBehavior: oneDirection\n"
        )
        sales_tmdl = "table Sales\n\tlineageTag: Sales\n\n\tcolumn ProductId\n\t\tdataType: int64\n\t\tlineageTag: ProductId\n\t\tsummarizeBy: none\n\n\tpartition Sales = m\n\t\tmode: import\n\t\tsource = #table({}, {})\n"
        products_tmdl = "table Products\n\tlineageTag: Products\n\n\tcolumn ProductId\n\t\tdataType: int64\n\t\tlineageTag: ProductId\n\t\tsummarizeBy: none\n\n\tpartition Products = m\n\t\tmode: import\n\t\tsource = #table({}, {})\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(
                tmp,
                model_tmdl="model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n",
                tables={"Sales": sales_tmdl, "Products": products_tmdl},
                relationships=rel,
            )
            self.healer.heal_project(root)
            content = (root / "TestModel.SemanticModel" / "definition" / "relationships.tmdl").read_text()
            self.assertIn("rel_Sales_Products_ProductId", content)


class TestHealPBIR(unittest.TestCase):
    """Tests for PBIR visual/report healing."""

    def setUp(self):
        self.healer = ArtifactHealer()

    def _make_project(self, tmp: str, report_files: dict[str, str]) -> Path:
        root = Path(tmp) / "TestProject"
        report_dir = root / "TestModel.Report"
        for rel_path, content in report_files.items():
            p = report_dir / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return root

    def test_definition_pbir_missing_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(tmp, {
                "definition.pbir": json.dumps({"version": "4.0"}),
            })
            self.healer.heal_project(root)
            data = json.loads((root / "TestModel.Report" / "definition.pbir").read_text())
            self.assertIn("$schema", data)

    def test_definition_pbir_missing_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(tmp, {
                "definition.pbir": json.dumps({"$schema": "https://example.com"}),
            })
            self.healer.heal_project(root)
            data = json.loads((root / "TestModel.Report" / "definition.pbir").read_text())
            self.assertEqual(data["version"], "4.0")

    def test_report_json_missing_theme(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(tmp, {
                "definition/report.json": json.dumps({"$schema": "https://example.com"}),
            })
            self.healer.heal_project(root)
            data = json.loads((root / "TestModel.Report" / "definition" / "report.json").read_text())
            self.assertIn("themeCollection", data)

    def test_visual_missing_type(self):
        visual = {"visual": {"position": {"x": 0, "y": 0, "width": 100, "height": 100}}}
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(tmp, {
                "definition/pages/page1/visuals/v1/visual.json": json.dumps(visual),
            })
            self.healer.heal_project(root)
            data = json.loads(
                (root / "TestModel.Report" / "definition" / "pages" / "page1" / "visuals" / "v1" / "visual.json").read_text()
            )
            self.assertEqual(data["visual"]["visualType"], "tableEx")

    def test_visual_zero_size_fixed(self):
        visual = {"visual": {"visualType": "barChart", "position": {"x": 0, "y": 0, "width": 0, "height": 0}}}
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(tmp, {
                "definition/pages/page1/visuals/v1/visual.json": json.dumps(visual),
            })
            self.healer.heal_project(root)
            data = json.loads(
                (root / "TestModel.Report" / "definition" / "pages" / "page1" / "visuals" / "v1" / "visual.json").read_text()
            )
            self.assertGreater(data["visual"]["position"]["width"], 0)
            self.assertGreater(data["visual"]["position"]["height"], 0)

    def test_valid_visual_unchanged(self):
        visual = {"visual": {"visualType": "barChart", "position": {"x": 0, "y": 0, "width": 500, "height": 400}}}
        raw = json.dumps(visual)
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(tmp, {
                "definition/pages/page1/visuals/v1/visual.json": raw,
            })
            self.healer.heal_project(root)
            new_raw = (root / "TestModel.Report" / "definition" / "pages" / "page1" / "visuals" / "v1" / "visual.json").read_text()
            # Content should be unchanged (no write)
            self.assertEqual(json.loads(new_raw), visual)

    def test_invalid_json_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_project(tmp, {
                "definition.pbir": "{ broken json",
            })
            self.healer.heal_project(root)
            errors = [e for e in self.healer.report.entries if e["severity"] == "error"]
            self.assertGreater(len(errors), 0)


class TestHealAndValidate(unittest.TestCase):
    """Integration test for heal + validate pipeline."""

    def test_heal_then_validate(self):
        healer = ArtifactHealer()
        tmdl = (
            "table Sales\n"
            "\tlineageTag: Sales\n\n"
            "\tcolumn Revenue\n"
            "\t\tdataType: float\n"
            "\t\tlineageTag: Revenue\n"
            "\t\tsummarizeBy: none\n\n"
            "\tcolumn Revenue\n"
            "\t\tdataType: double\n"
            "\t\tlineageTag: Revenue2\n"
            "\t\tsummarizeBy: none\n\n"
            '\tmeasure Total = Total.sum([Revenue])\n'
            "\t\tlineageTag: Total\n\n"
            "\tpartition Sales = m\n"
            "\t\tmode: import\n"
            "\t\tsource = #table({}, {})\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "TestProject"
            sm_dir = root / "Sales.SemanticModel" / "definition" / "tables"
            sm_dir.mkdir(parents=True)
            (sm_dir.parent / "model.tmdl").write_text(
                "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
            )
            (sm_dir / "Sales.tmdl").write_text(tmdl, encoding="utf-8")

            result = healer.heal_and_validate(str(root))
            self.assertIn("healing", result)
            self.assertIn("validation", result)
            # Healing should have fixed duplicate column + data type + BIRT leak
            self.assertGreater(result["healing"]["total_repairs"], 0)
            # After healing, duplicate_columns check should pass
            dup_check = next(
                (c for c in result["validation"]["checks"] if c["check"] == "duplicate_columns"),
                None,
            )
            if dup_check:
                self.assertEqual(dup_check["status"], "pass")


class TestHealerNoProject(unittest.TestCase):
    """Edge cases — no SemanticModel or Report dirs."""

    def test_empty_directory(self):
        healer = ArtifactHealer()
        with tempfile.TemporaryDirectory() as tmp:
            report = healer.heal_project(tmp)
            self.assertEqual(len(report.entries), 0)

    def test_missing_definition_dir(self):
        healer = ArtifactHealer()
        with tempfile.TemporaryDirectory() as tmp:
            # Create SemanticModel without definition subfolder
            sm = Path(tmp) / "Test.SemanticModel"
            sm.mkdir()
            report = healer.heal_project(tmp)
            self.assertEqual(len(report.entries), 0)


if __name__ == "__main__":
    unittest.main()
