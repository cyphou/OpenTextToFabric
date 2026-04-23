"""Tests for config.py and progress.py."""

import json
import tempfile
import unittest
from pathlib import Path

from config import MigrationConfig, ServerConfig, ScopeConfig, OutputConfig
from progress import StepProgress, StepStatus, MigrationProgress


class TestServerConfig(unittest.TestCase):

    def test_basic_creation(self):
        sc = ServerConfig(url="https://cs.example.com", username="admin", password="pass")
        self.assertEqual(sc.url, "https://cs.example.com")


class TestMigrationConfig(unittest.TestCase):

    def test_from_args_birt(self):
        import argparse
        args = argparse.Namespace(
            source_type="birt",
            server_url=None,
            username=None,
            password_env=None,
            scope=None,
            input="./reports",
            output_dir="./output",
            output_format="pbip",
            assess_only=False,
            batch=False,
            deploy=False,
            workspace_id=None,
            tenant_id=None,
        )
        config = MigrationConfig.from_args(args)
        self.assertEqual(config.output.output_format, "pbip")

    def test_validate_no_errors(self):
        config = MigrationConfig(
            server=ServerConfig(url="https://cs.example.com", username="admin", password="pass"),
            scope=ScopeConfig(),
            output=OutputConfig(output_dir="./output", output_format="both"),
            source_type="content-server",
        )
        errors = config.validate()
        self.assertEqual(errors, [])


class TestStepProgress(unittest.TestCase):

    def test_initial_state(self):
        step = StepProgress(name="test")
        self.assertEqual(step.status, StepStatus.PENDING)

    def test_start(self):
        step = StepProgress(name="test")
        step.start(total=10)
        self.assertEqual(step.status, StepStatus.RUNNING)
        self.assertEqual(step.items_total, 10)

    def test_advance(self):
        step = StepProgress(name="test")
        step.start(total=10)
        step.advance(3)
        self.assertEqual(step.items_done, 3)
        self.assertAlmostEqual(step.percent, 30.0)

    def test_complete(self):
        step = StepProgress(name="test")
        step.start()
        step.complete()
        self.assertEqual(step.status, StepStatus.COMPLETED)
        self.assertGreater(step.elapsed, 0)

    def test_fail(self):
        step = StepProgress(name="test")
        step.start()
        step.fail("something broke")
        self.assertEqual(step.status, StepStatus.FAILED)
        self.assertEqual(step.error, "something broke")

    def test_to_dict(self):
        step = StepProgress(name="test")
        d = step.to_dict()
        self.assertEqual(d["name"], "test")
        self.assertEqual(d["status"], "pending")


class TestMigrationProgress(unittest.TestCase):

    def test_add_step(self):
        mp = MigrationProgress()
        step = mp.add_step("extraction")
        self.assertEqual(len(mp.steps), 1)
        self.assertEqual(step.name, "extraction")

    def test_current_step(self):
        mp = MigrationProgress()
        step = mp.add_step("extraction")
        self.assertIsNone(mp.current_step)
        step.start()
        self.assertEqual(mp.current_step, step)

    def test_is_complete(self):
        mp = MigrationProgress()
        step = mp.add_step("extraction")
        self.assertFalse(mp.is_complete)
        step.start()
        step.complete()
        self.assertTrue(mp.is_complete)

    def test_has_failures(self):
        mp = MigrationProgress()
        step = mp.add_step("extraction")
        step.start()
        step.fail("error")
        self.assertTrue(mp.has_failures)

    def test_save_checkpoint(self):
        mp = MigrationProgress()
        mp.add_step("extraction")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "checkpoint.json"
            mp.save_checkpoint(path)
            self.assertTrue(path.exists())
            data = json.loads(path.read_text())
            self.assertEqual(len(data["steps"]), 1)

    def test_summary(self):
        mp = MigrationProgress()
        s1 = mp.add_step("s1")
        s2 = mp.add_step("s2")
        s1.start()
        s1.complete()
        summary = mp.summary()
        self.assertEqual(summary["total_steps"], 2)
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["pending"], 1)


if __name__ == "__main__":
    unittest.main()
