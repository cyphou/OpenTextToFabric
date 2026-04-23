"""Tests for reporting.regression — snapshot, drift detection, visual diff."""

import json
import os
import tempfile
import unittest

from reporting.regression import (
    ComparisonReport,
    MigrationSnapshot,
    RegressionDetector,
    VisualDiff,
)


class TestMigrationSnapshot(unittest.TestCase):
    def test_capture_directory(self):
        with tempfile.TemporaryDirectory() as td:
            f1 = os.path.join(td, "a.tmdl")
            f2 = os.path.join(td, "b.json")
            with open(f1, "w") as f:
                f.write("table T\n\tcolumn C\n")
            with open(f2, "w") as f:
                f.write('{"key": "value"}')

            snap = MigrationSnapshot("test", td)
            result = snap.capture()
            self.assertEqual(result["artifact_count"], 2)
            self.assertIn("a.tmdl", result["artifacts"])
            self.assertIn("b.json", result["artifacts"])

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as td:
            snap = MigrationSnapshot("empty", td)
            result = snap.capture()
            self.assertEqual(len(result["artifacts"]), 0)

    def test_nonexistent_directory(self):
        snap = MigrationSnapshot("missing", "/nonexistent/path")
        result = snap.capture()
        self.assertEqual(len(result["artifacts"]), 0)

    def test_capture_json_structure(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "data.json"), "w") as f:
                json.dump({"a": 1, "b": 2}, f)
            snap = MigrationSnapshot("json_test", td)
            result = snap.capture()
            art = result["artifacts"]["data.json"]
            self.assertIn("hash", art)
            self.assertIn("size", art)
            self.assertIn("keys", art)

    def test_capture_tmdl_structure(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "model.tmdl"), "w") as f:
                f.write("table Sales\n\tmeasure Revenue = SUM(Amount)\n")
            snap = MigrationSnapshot("tmdl_test", td)
            result = snap.capture()
            art = result["artifacts"]["model.tmdl"]
            self.assertEqual(art["tables"], 1)
            self.assertEqual(art["measures"], 1)

    def test_save(self):
        with tempfile.TemporaryDirectory() as td:
            out_dir = os.path.join(td, "output")
            os.makedirs(out_dir)
            with open(os.path.join(out_dir, "f.txt"), "w") as f:
                f.write("test")

            snap = MigrationSnapshot("save_test", out_dir)
            snap_dir = os.path.join(td, "snapshots")
            path = snap.save(snap_dir)
            self.assertTrue(path.exists())
            data = json.loads(path.read_text())
            self.assertEqual(data["name"], "save_test")


class TestRegressionDetector(unittest.TestCase):
    def test_no_drift(self):
        snapshot = {
            "name": "run1",
            "timestamp": "t1",
            "artifacts": {"a.tmdl": {"hash": "h1"}, "b.json": {"hash": "h2"}},
        }
        detector = RegressionDetector()
        result = detector.compare(snapshot, snapshot)
        self.assertEqual(len(result["added"]), 0)
        self.assertEqual(len(result["removed"]), 0)
        self.assertEqual(len(result["changed"]), 0)
        self.assertFalse(result["has_regression"])

    def test_detect_added_file(self):
        baseline = {"name": "b", "artifacts": {"a.tmdl": {"hash": "h1"}}}
        current = {"name": "c", "artifacts": {"a.tmdl": {"hash": "h1"}, "b.json": {"hash": "h2"}}}
        detector = RegressionDetector()
        result = detector.compare(baseline, current)
        self.assertIn("b.json", result["added"])

    def test_detect_removed_file(self):
        baseline = {"name": "b", "artifacts": {"a.tmdl": {"hash": "h1"}, "b.json": {"hash": "h2"}}}
        current = {"name": "c", "artifacts": {"a.tmdl": {"hash": "h1"}}}
        detector = RegressionDetector()
        result = detector.compare(baseline, current)
        self.assertIn("b.json", result["removed"])
        self.assertTrue(result["has_regression"])

    def test_detect_changed_file(self):
        baseline = {"name": "b", "artifacts": {"a.tmdl": {"hash": "h1", "size": 10}}}
        current = {"name": "c", "artifacts": {"a.tmdl": {"hash": "h2", "size": 15}}}
        detector = RegressionDetector()
        result = detector.compare(baseline, current)
        self.assertEqual(len(result["changed"]), 1)
        self.assertEqual(result["changed"][0]["file"], "a.tmdl")

    def test_mixed_changes(self):
        baseline = {"name": "b", "artifacts": {
            "a.tmdl": {"hash": "h1"},
            "b.json": {"hash": "h2"},
            "c.sql": {"hash": "h3"},
        }}
        current = {"name": "c", "artifacts": {
            "a.tmdl": {"hash": "h1"},
            "b.json": {"hash": "h_new", "size": 10},
            "d.py": {"hash": "h4"},
        }}
        detector = RegressionDetector()
        result = detector.compare(baseline, current)
        self.assertIn("d.py", result["added"])
        self.assertIn("c.sql", result["removed"])
        self.assertEqual(len(result["changed"]), 1)

    def test_summary_counts(self):
        baseline = {"name": "b", "artifacts": {"a": {"hash": "1"}}}
        current = {"name": "c", "artifacts": {"a": {"hash": "2", "size": 5}}}
        detector = RegressionDetector()
        result = detector.compare(baseline, current)
        self.assertEqual(result["summary"]["changed"], 1)
        self.assertEqual(result["summary"]["unchanged"], 0)


class TestVisualDiff(unittest.TestCase):
    def test_all_matched(self):
        birt = [{"name": "Sales", "element_type": "chart"}]
        pbi = [{"name": "Sales", "visual_type": "clusteredColumnChart"}]
        vd = VisualDiff()
        result = vd.compare_visuals(birt, pbi)
        self.assertEqual(result["fidelity_percent"], 100.0)
        self.assertEqual(len(result["matched"]), 1)

    def test_partial_match(self):
        birt = [
            {"name": "Sales", "element_type": "chart"},
            {"name": "Trends", "element_type": "chart"},
        ]
        pbi = [{"name": "Sales", "visual_type": "lineChart"}]
        vd = VisualDiff()
        result = vd.compare_visuals(birt, pbi)
        self.assertEqual(result["fidelity_percent"], 50.0)
        self.assertEqual(len(result["unmatched_birt"]), 1)

    def test_no_match(self):
        birt = [{"name": "A", "element_type": "chart"}]
        pbi = [{"name": "B", "visual_type": "lineChart"}]
        vd = VisualDiff()
        result = vd.compare_visuals(birt, pbi)
        self.assertEqual(result["fidelity_percent"], 0.0)
        self.assertEqual(len(result["unmatched_pbi"]), 1)

    def test_empty_lists(self):
        vd = VisualDiff()
        result = vd.compare_visuals([], [])
        self.assertEqual(result["fidelity_percent"], 0.0)
        self.assertEqual(len(result["matched"]), 0)

    def test_case_insensitive_matching(self):
        birt = [{"name": "SALES", "element_type": "chart"}]
        pbi = [{"name": "sales", "visual_type": "columnChart"}]
        vd = VisualDiff()
        result = vd.compare_visuals(birt, pbi)
        self.assertEqual(len(result["matched"]), 1)


class TestComparisonReport(unittest.TestCase):
    def test_generate_html(self):
        visual_diff = {
            "matched": [
                {"birt_name": "Chart1", "birt_type": "chart", "pbi_name": "Chart1", "pbi_type": "columnChart"},
            ],
            "unmatched_birt": [{"name": "Table1", "type": "table"}],
            "unmatched_pbi": [],
            "fidelity_percent": 50.0,
        }
        report = ComparisonReport()
        with tempfile.TemporaryDirectory() as td:
            path = report.generate(visual_diff, output_path=os.path.join(td, "report.html"))
            self.assertTrue(path.exists())
            html = path.read_text()
            self.assertIn("<html", html)
            self.assertIn("Chart1", html)

    def test_generate_with_regression(self):
        visual_diff = {
            "matched": [],
            "unmatched_birt": [],
            "unmatched_pbi": [],
            "fidelity_percent": 0.0,
        }
        regression = {
            "has_regression": False,
            "summary": {"added": 1, "removed": 0, "changed": 2, "unchanged": 5},
        }
        report = ComparisonReport()
        with tempfile.TemporaryDirectory() as td:
            path = report.generate(visual_diff, regression=regression, output_path=os.path.join(td, "r.html"))
            html = path.read_text()
            self.assertIn("Regression", html)

    def test_empty_report(self):
        visual_diff = {
            "matched": [],
            "unmatched_birt": [],
            "unmatched_pbi": [],
            "fidelity_percent": 0.0,
        }
        report = ComparisonReport()
        with tempfile.TemporaryDirectory() as td:
            path = report.generate(visual_diff, output_path=os.path.join(td, "r.html"))
            html = path.read_text()
            self.assertIn("<html", html)


if __name__ == "__main__":
    unittest.main()
