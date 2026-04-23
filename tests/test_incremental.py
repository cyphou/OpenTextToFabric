"""Tests for reporting.incremental — change detection, recovery, SLA tracking."""

import os
import tempfile
import time
import unittest
from pathlib import Path

from reporting.incremental import (
    ChangeDetector,
    RecoveryReport,
    SLATracker,
)


class TestChangeDetector(unittest.TestCase):
    def test_first_scan_all_new(self):
        with tempfile.TemporaryDirectory() as td:
            f1 = os.path.join(td, "report1.rptdesign")
            f2 = os.path.join(td, "report2.rptdesign")
            for f in [f1, f2]:
                with open(f, "w") as fh:
                    fh.write(f"<report>{f}</report>")

            cd = ChangeDetector()
            files = cd.get_files_to_migrate(td, "*.rptdesign")
            self.assertEqual(len(files), 2)

    def test_no_changes_second_scan(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = os.path.join(td, ".state.json")
            f1 = os.path.join(td, "report1.rptdesign")
            with open(f1, "w") as fh:
                fh.write("<report>A</report>")

            cd = ChangeDetector(state_path=state_file)
            files1 = cd.get_files_to_migrate(td, "*.rptdesign")
            self.assertEqual(len(files1), 1)
            cd.save_state()

            cd2 = ChangeDetector(state_path=state_file)
            files2 = cd2.get_files_to_migrate(td, "*.rptdesign")
            self.assertEqual(len(files2), 0)

    def test_detects_modified_file(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = os.path.join(td, ".state.json")
            f1 = os.path.join(td, "report.rptdesign")
            with open(f1, "w") as fh:
                fh.write("<report>V1</report>")

            cd = ChangeDetector(state_path=state_file)
            cd.get_files_to_migrate(td, "*.rptdesign")
            cd.save_state()

            # Modify file
            with open(f1, "w") as fh:
                fh.write("<report>V2_MODIFIED</report>")

            cd2 = ChangeDetector(state_path=state_file)
            files = cd2.get_files_to_migrate(td, "*.rptdesign")
            self.assertEqual(len(files), 1)

    def test_detects_new_file(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = os.path.join(td, ".state.json")
            f1 = os.path.join(td, "report1.rptdesign")
            with open(f1, "w") as fh:
                fh.write("<report>A</report>")

            cd = ChangeDetector(state_path=state_file)
            cd.get_files_to_migrate(td, "*.rptdesign")
            cd.save_state()

            # Add new file
            f2 = os.path.join(td, "report2.rptdesign")
            with open(f2, "w") as fh:
                fh.write("<report>B</report>")

            cd2 = ChangeDetector(state_path=state_file)
            files = cd2.get_files_to_migrate(td, "*.rptdesign")
            self.assertEqual(len(files), 1)
            self.assertIn(Path(f2), files)

    def test_scan_returns_change_info(self):
        with tempfile.TemporaryDirectory() as td:
            f1 = os.path.join(td, "r.rptdesign")
            with open(f1, "w") as fh:
                fh.write("<report>X</report>")

            cd = ChangeDetector()
            scan = cd.scan(td, "*.rptdesign")
            self.assertEqual(scan["total_source"], 1)
            self.assertEqual(len(scan["added"]), 1)
            self.assertIn(f1, scan["added"])

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as td:
            cd = ChangeDetector()
            files = cd.get_files_to_migrate(td, "*.rptdesign")
            self.assertEqual(len(files), 0)


class TestRecoveryReport(unittest.TestCase):
    def test_record_failure(self):
        rr = RecoveryReport()
        rr.record_failure("report1.rptdesign", "parse", "Bad XML")
        self.assertEqual(len(rr._failures), 1)
        self.assertEqual(rr._failures[0]["item"], "report1.rptdesign")

    def test_record_recovery(self):
        rr = RecoveryReport()
        rr.record_failure("report1.rptdesign", "parse", "Bad XML")
        rr.record_recovery("report1.rptdesign", "parse")
        self.assertEqual(len(rr._recoveries), 1)
        # Should mark failure as recovered
        self.assertTrue(rr._failures[0]["recovered"])

    def test_generate_report(self):
        rr = RecoveryReport()
        rr.record_failure("r1.rptdesign", "extract", "Error details")
        rr.record_recovery("r2.rptdesign", "convert")
        with tempfile.TemporaryDirectory() as td:
            path = rr.generate_report(os.path.join(td, "recovery.html"))
            self.assertTrue(path.exists())
            content = path.read_text()
            self.assertIn("<html", content)
            self.assertIn("r1.rptdesign", content)

    def test_empty_report(self):
        rr = RecoveryReport()
        with tempfile.TemporaryDirectory() as td:
            path = rr.generate_report(os.path.join(td, "recovery.html"))
            self.assertTrue(path.exists())
            content = path.read_text()
            self.assertIn("<html", content)

    def test_summary(self):
        rr = RecoveryReport()
        rr.record_failure("a", "step1", "err1")
        rr.record_failure("b", "step2", "err2")
        rr.record_recovery("a", "step1")
        s = rr.summary()
        self.assertEqual(s["total_failures"], 2)
        self.assertEqual(s["recovered"], 1)

    def test_pending_retries(self):
        rr = RecoveryReport()
        rr.record_failure("a", "s1", "e1", recoverable=True)
        rr.record_failure("b", "s2", "e2", recoverable=False)
        pending = rr.get_pending_retries()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["item"], "a")


class TestSLATracker(unittest.TestCase):
    def test_record_and_compliance(self):
        sla = SLATracker(max_duration_seconds=10.0)
        sla.record("report1", 5.0, 90.0)
        sla.record("report2", 8.0, 95.0)
        self.assertAlmostEqual(sla.compliance_rate(), 100.0)

    def test_violations_duration(self):
        sla = SLATracker(max_duration_seconds=5.0)
        sla.record("report1", 3.0, 90.0)
        sla.record("report2", 10.0, 90.0)  # Exceeds max_duration
        sla.record("report3", 4.0, 90.0)
        violations = sla.violations()
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["report"], "report2")

    def test_violations_fidelity(self):
        sla = SLATracker(max_duration_seconds=10.0, min_fidelity=80.0)
        sla.record("report1", 2.0, 50.0)  # Below fidelity threshold
        violations = sla.violations()
        self.assertEqual(len(violations), 1)

    def test_violations_failed_status(self):
        sla = SLATracker(max_duration_seconds=10.0)
        sla.record("report1", 2.0, 90.0, status="failed")
        violations = sla.violations()
        self.assertEqual(len(violations), 1)

    def test_empty_tracker(self):
        sla = SLATracker(max_duration_seconds=10.0)
        self.assertEqual(sla.compliance_rate(), 100.0)
        self.assertEqual(sla.violations(), [])

    def test_summary(self):
        sla = SLATracker(max_duration_seconds=5.0)
        sla.record("r1", 3.0, 90.0)
        sla.record("r2", 6.0, 90.0)  # exceeds duration
        sla.record("r3", 2.0, 50.0)  # below fidelity
        s = sla.summary()
        self.assertEqual(s["total_records"], 3)
        self.assertIn("compliance_rate", s)
        self.assertIn("sla_violated", s)


if __name__ == "__main__":
    unittest.main()
