"""Tests for TMDL generation and post-migration validation."""

import json
import tempfile
import unittest
from pathlib import Path

from assessment.validator import MigrationValidator
from fabric_output.tmdl_generator import TMDLGenerator


class TestTMDLRelationshipDedup(unittest.TestCase):
    """Verify that infer_relationships emits only one relationship per table pair."""

    def _make_tmdl_with_shared_cols(self, shared_cols: list[str]) -> TMDLGenerator:
        """Helper: create a TMDL with two tables sharing the given columns."""
        tmdl = TMDLGenerator()
        tmdl.add_table_from_dataset({
            "name": "TableA",
            "data_source": "",
            "query": "",
            "column_hints": [{"columnName": c, "dataType": "string"} for c in shared_cols]
                + [{"columnName": "extra_a", "dataType": "string"}],
            "computed_columns": [],
            "result_columns": [],
        })
        tmdl.add_table_from_dataset({
            "name": "TableB",
            "data_source": "",
            "query": "",
            "column_hints": [{"columnName": c, "dataType": "string"} for c in shared_cols],
            "computed_columns": [],
            "result_columns": [],
        })
        return tmdl

    def test_single_relationship_per_pair(self):
        """Multiple shared columns should produce exactly one relationship."""
        tmdl = self._make_tmdl_with_shared_cols(["PSITE_CODE", "ANNEE", "MOIS"])
        rels = tmdl.infer_relationships([])
        self.assertEqual(len(rels), 1, "Should have exactly 1 relationship per table pair")

    def test_prefers_id_column(self):
        """Should prefer a column ending with _id over others."""
        tmdl = self._make_tmdl_with_shared_cols(["name", "region_id", "code"])
        rels = tmdl.infer_relationships([])
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0]["fromColumn"], "region_id")

    def test_prefers_code_over_generic(self):
        """Should prefer a column ending with _code over generic names."""
        tmdl = self._make_tmdl_with_shared_cols(["name", "PSITE_CODE", "year"])
        rels = tmdl.infer_relationships([])
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0]["fromColumn"], "PSITE_CODE")

    def test_no_relationship_no_shared(self):
        """No shared columns → no relationships."""
        tmdl = TMDLGenerator()
        tmdl.add_table_from_dataset({
            "name": "A", "data_source": "", "query": "",
            "column_hints": [{"columnName": "col_a", "dataType": "string"}],
            "computed_columns": [], "result_columns": [],
        })
        tmdl.add_table_from_dataset({
            "name": "B", "data_source": "", "query": "",
            "column_hints": [{"columnName": "col_b", "dataType": "string"}],
            "computed_columns": [], "result_columns": [],
        })
        rels = tmdl.infer_relationships([])
        self.assertEqual(len(rels), 0)

    def test_three_tables_no_ambiguity(self):
        """Three tables sharing a column → one rel per pair, no ambiguity."""
        tmdl = TMDLGenerator()
        for name, extra in [("Fact", ["amount", "qty"]), ("Dim1", []), ("Dim2", ["desc"])]:
            cols = [{"columnName": "region", "dataType": "string"}]
            cols += [{"columnName": c, "dataType": "string"} for c in extra]
            tmdl.add_table_from_dataset({
                "name": name, "data_source": "", "query": "",
                "column_hints": cols,
                "computed_columns": [], "result_columns": [],
            })
        rels = tmdl.infer_relationships([])
        # 3 tables sharing "region" → 3 pairs but each pair gets only 1 rel
        pairs = {(r["fromTable"], r["toTable"]) for r in rels}
        self.assertEqual(len(rels), len(pairs), "No duplicate pairs")


class TestTMDLDuplicateColumnDedup(unittest.TestCase):
    """Verify that duplicate columns in result_columns/computed_columns are deduped."""

    def test_duplicate_result_columns_deduped(self):
        tmdl = TMDLGenerator()
        table = tmdl.add_table_from_dataset({
            "name": "Test",
            "data_source": "",
            "query": "",
            "result_columns": [
                {"name": "PSITE_CODE", "dataType": "string"},
                {"name": "PSITE_CODE", "dataType": "string"},
                {"name": "value", "dataType": "decimal"},
            ],
            "column_hints": [],
            "computed_columns": [],
        })
        names = [c["name"] for c in table["columns"]]
        self.assertEqual(len(names), len(set(names)), "No duplicate column names")

    def test_computed_does_not_duplicate_result(self):
        tmdl = TMDLGenerator()
        table = tmdl.add_table_from_dataset({
            "name": "Test",
            "data_source": "",
            "query": "",
            "result_columns": [
                {"name": "PSITE_CODE", "dataType": "string"},
            ],
            "column_hints": [],
            "computed_columns": [
                {"name": "PSITE_CODE", "dataType": "string", "expression": "row['PSITE_CODE']"},
            ],
        })
        names = [c["name"] for c in table["columns"]]
        self.assertEqual(len(names), len(set(names)))


class TestMigrationValidator(unittest.TestCase):
    """Test the post-migration validator with TMDL checks."""

    def _create_valid_project(self, tmpdir: str) -> Path:
        """Create a minimal valid PBIP project structure for testing."""
        out = Path(tmpdir)

        # Intermediate JSONs
        for fname in ("datasets.json", "connections.json", "visuals.json", "expressions.json"):
            (out / fname).write_text("[]", encoding="utf-8")

        # TMDL structure
        tmdl = TMDLGenerator(model_name="TestReport")
        tmdl.add_table_from_dataset({
            "name": "Sales",
            "data_source": "",
            "query": "",
            "column_hints": [
                {"columnName": "id", "dataType": "integer"},
                {"columnName": "amount", "dataType": "decimal"},
            ],
            "computed_columns": [],
            "result_columns": [],
        })
        tmdl.add_table_from_dataset({
            "name": "Region",
            "data_source": "",
            "query": "",
            "column_hints": [{"columnName": "id", "dataType": "integer"}],
            "computed_columns": [],
            "result_columns": [],
        })
        tmdl.infer_relationships([])
        tmdl.export(str(out / "TestReport"))

        # PBIP structure
        proj = out / "TestReport"
        report_dir = proj / "TestReport.Report"
        report_dir.mkdir(parents=True, exist_ok=True)
        (proj / "TestReport.pbip").write_text("{}", encoding="utf-8")
        (report_dir / "definition.pbir").write_text("{}", encoding="utf-8")
        (report_dir / ".platform").write_text("{}", encoding="utf-8")

        # Visual
        vis_dir = report_dir / "definition" / "pages" / "page1" / "visuals" / "v1"
        vis_dir.mkdir(parents=True, exist_ok=True)
        (vis_dir / "visual.json").write_text("{}", encoding="utf-8")

        return out

    def test_valid_project_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = self._create_valid_project(tmpdir)
            v = MigrationValidator()
            result = v.validate(str(out))
            self.assertTrue(result["valid"], f"Checks: {result['checks']}")
            self.assertEqual(result["failed"], 0)

    def test_detects_duplicate_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir)
            # Create a TMDL file with duplicate column
            sm_dir = out / "Test.SemanticModel" / "definition" / "tables"
            sm_dir.mkdir(parents=True, exist_ok=True)
            (out / "Test.SemanticModel" / "definition" / "model.tmdl").write_text(
                "model Model\n\tculture: en-US\n", encoding="utf-8"
            )
            (sm_dir / "BadTable.tmdl").write_text(
                "table BadTable\n"
                "\tcolumn PSITE_CODE\n"
                "\t\tdataType: string\n"
                "\tcolumn PSITE_CODE\n"
                "\t\tdataType: string\n",
                encoding="utf-8",
            )
            # Minimal required files
            for fname in ("datasets.json", "connections.json", "visuals.json", "expressions.json"):
                (out / fname).write_text("[]", encoding="utf-8")

            v = MigrationValidator()
            result = v.validate(str(out))
            dup_check = next(c for c in result["checks"] if c["check"] == "duplicate_columns")
            self.assertEqual(dup_check["status"], "fail")
            self.assertIn("PSITE_CODE", dup_check["detail"])

    def test_detects_ambiguous_relationships(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir)
            sm_dir = out / "Test.SemanticModel" / "definition"
            tables_dir = sm_dir / "tables"
            tables_dir.mkdir(parents=True, exist_ok=True)
            (sm_dir / "model.tmdl").write_text(
                "model Model\n\tculture: en-US\n", encoding="utf-8"
            )
            for tname in ("TableA", "TableB"):
                (tables_dir / f"{tname}.tmdl").write_text(
                    f"table {tname}\n\tcolumn col1\n\t\tdataType: string\n",
                    encoding="utf-8",
                )
            # Two relationships between same pair → ambiguous
            (sm_dir / "relationships.tmdl").write_text(
                "\nrelationship rel1\n"
                "\tfromColumn: TableA.col1\n"
                "\ttoColumn: TableB.col1\n"
                "\nrelationship rel2\n"
                "\tfromColumn: TableA.col2\n"
                "\ttoColumn: TableB.col2\n",
                encoding="utf-8",
            )
            for fname in ("datasets.json", "connections.json", "visuals.json", "expressions.json"):
                (out / fname).write_text("[]", encoding="utf-8")

            v = MigrationValidator()
            result = v.validate(str(out))
            amb_check = next(c for c in result["checks"] if c["check"] == "ambiguous_relationships")
            self.assertEqual(amb_check["status"], "fail")
            self.assertIn("ambiguous", amb_check["detail"].lower())

    def test_detects_missing_relationship_tables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir)
            sm_dir = out / "Test.SemanticModel" / "definition"
            tables_dir = sm_dir / "tables"
            tables_dir.mkdir(parents=True, exist_ok=True)
            (sm_dir / "model.tmdl").write_text(
                "model Model\n\tculture: en-US\n", encoding="utf-8"
            )
            (tables_dir / "TableA.tmdl").write_text(
                "table TableA\n\tcolumn col1\n\t\tdataType: string\n",
                encoding="utf-8",
            )
            # Relationship references TableB which doesn't exist
            (sm_dir / "relationships.tmdl").write_text(
                "\nrelationship rel1\n"
                "\tfromColumn: TableA.col1\n"
                "\ttoColumn: MissingTable.col1\n",
                encoding="utf-8",
            )
            for fname in ("datasets.json", "connections.json", "visuals.json", "expressions.json"):
                (out / fname).write_text("[]", encoding="utf-8")

            v = MigrationValidator()
            result = v.validate(str(out))
            ref_check = next(c for c in result["checks"] if c["check"] == "relationship_tables")
            self.assertEqual(ref_check["status"], "fail")
            self.assertIn("MissingTable", ref_check["detail"])

    def test_no_ambiguity_after_inference(self):
        """End-to-end: infer_relationships + validate → no ambiguous paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = self._create_valid_project(tmpdir)
            v = MigrationValidator()
            result = v.validate(str(out))
            amb_check = next(c for c in result["checks"] if c["check"] == "ambiguous_relationships")
            self.assertEqual(amb_check["status"], "pass")


if __name__ == "__main__":
    unittest.main()
