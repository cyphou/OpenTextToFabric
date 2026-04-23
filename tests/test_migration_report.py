"""Tests for reporting.migration_report fidelity tracker."""

import json
import tempfile
import unittest
from pathlib import Path

from reporting.migration_report import (
    MigrationReport,
    EXACT,
    APPROXIMATE,
    UNSUPPORTED,
    SKIPPED,
    ReportItem,
)


class TestReportItemCreation(unittest.TestCase):
    def test_add_single(self):
        r = MigrationReport()
        item = r.add("doc1.pdf", "documents", EXACT, source_type="application/pdf")
        self.assertIsInstance(item, ReportItem)
        self.assertEqual(item.name, "doc1.pdf")
        self.assertEqual(item.category, "documents")
        self.assertEqual(item.status, EXACT)
        self.assertEqual(len(r.items), 1)

    def test_add_batch(self):
        r = MigrationReport()
        r.add_batch("nodes", [
            {"name": "a", "status": EXACT},
            {"name": "b", "status": APPROXIMATE},
            {"name": "c", "status": UNSUPPORTED},
        ])
        self.assertEqual(len(r.items), 3)

    def test_add_batch_defaults(self):
        r = MigrationReport()
        r.add_batch("nodes", [{}])
        self.assertEqual(r.items[0].status, SKIPPED)
        self.assertEqual(r.items[0].name, "")


class TestQueries(unittest.TestCase):
    def setUp(self):
        self.r = MigrationReport()
        self.r.add("n1", "nodes", EXACT)
        self.r.add("n2", "nodes", APPROXIMATE)
        self.r.add("d1", "documents", EXACT)
        self.r.add("e1", "expressions", UNSUPPORTED)

    def test_by_category(self):
        self.assertEqual(len(self.r.by_category("nodes")), 2)
        self.assertEqual(len(self.r.by_category("documents")), 1)
        self.assertEqual(len(self.r.by_category("missing")), 0)

    def test_status_counts_all(self):
        counts = self.r.status_counts()
        self.assertEqual(counts[EXACT], 2)
        self.assertEqual(counts[APPROXIMATE], 1)
        self.assertEqual(counts[UNSUPPORTED], 1)

    def test_status_counts_category(self):
        counts = self.r.status_counts("nodes")
        self.assertEqual(counts[EXACT], 1)
        self.assertEqual(counts[APPROXIMATE], 1)

    def test_categories(self):
        cats = self.r.categories()
        self.assertEqual(cats, ["documents", "expressions", "nodes"])


class TestFidelityScoring(unittest.TestCase):
    def test_all_exact(self):
        r = MigrationReport()
        r.add("a", "nodes", EXACT)
        r.add("b", "nodes", EXACT)
        self.assertAlmostEqual(r.category_fidelity("nodes"), 100.0)

    def test_all_unsupported(self):
        r = MigrationReport()
        r.add("a", "nodes", UNSUPPORTED)
        self.assertAlmostEqual(r.category_fidelity("nodes"), 0.0)

    def test_mixed(self):
        r = MigrationReport()
        r.add("a", "nodes", EXACT)       # 1.0
        r.add("b", "nodes", APPROXIMATE)  # 0.6
        # (1.0 + 0.6) / 2 * 100 = 80.0
        self.assertAlmostEqual(r.category_fidelity("nodes"), 80.0)

    def test_empty_category(self):
        r = MigrationReport()
        self.assertAlmostEqual(r.category_fidelity("nodes"), 100.0)

    def test_overall_fidelity_single_category(self):
        r = MigrationReport()
        r.add("a", "nodes", EXACT)
        r.add("b", "nodes", APPROXIMATE)
        self.assertAlmostEqual(r.overall_fidelity(), 80.0)

    def test_overall_fidelity_weighted(self):
        r = MigrationReport(weights={"nodes": 1.0, "expressions": 2.0})
        r.add("a", "nodes", EXACT)       # nodes=100%
        r.add("b", "expressions", UNSUPPORTED)  # expressions=0%
        # weighted: (1*100 + 2*0) / 3 = 33.33...
        self.assertAlmostEqual(r.overall_fidelity(), 100 / 3, places=1)

    def test_overall_empty(self):
        r = MigrationReport()
        self.assertAlmostEqual(r.overall_fidelity(), 100.0)


class TestSerialization(unittest.TestCase):
    def test_to_dict(self):
        r = MigrationReport()
        r.add("a", "nodes", EXACT)
        r.add("b", "nodes", APPROXIMATE)
        d = r.to_dict()
        self.assertIn("overall_fidelity", d)
        self.assertEqual(d["total_items"], 2)
        self.assertIn("nodes", d["categories"])
        cat = d["categories"]["nodes"]
        self.assertEqual(len(cat["items"]), 2)
        self.assertIn("fidelity", cat)

    def test_save_and_load(self):
        r = MigrationReport()
        r.add("x", "metadata", EXACT)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.json"
            r.save(path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["total_items"], 1)
            self.assertIn("metadata", data["categories"])

    def test_save_creates_parent(self):
        r = MigrationReport()
        r.add("y", "nodes", EXACT)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sub" / "deep" / "report.json"
            r.save(path)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
