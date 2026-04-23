"""Tests for migrate.py CLI entry point."""

import unittest
from unittest.mock import patch

from migrate import build_parser, configure_logging, main


class TestBuildParser(unittest.TestCase):
    """Tests for CLI argument parsing."""

    def test_source_type_required(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args([])

    def test_content_server_source(self):
        parser = build_parser()
        args = parser.parse_args([
            "--source-type", "content-server",
            "--server-url", "https://cs.example.com/otcs/cs.exe",
        ])
        self.assertEqual(args.source_type, "content-server")
        self.assertEqual(args.server_url, "https://cs.example.com/otcs/cs.exe")

    def test_birt_source(self):
        parser = build_parser()
        args = parser.parse_args([
            "--source-type", "birt",
            "--input", "./reports/test.rptdesign",
        ])
        self.assertEqual(args.source_type, "birt")
        self.assertEqual(args.input, "./reports/test.rptdesign")

    def test_default_output_dir(self):
        parser = build_parser()
        args = parser.parse_args(["--source-type", "birt"])
        self.assertEqual(args.output_dir, "./output")

    def test_assess_only_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--source-type", "content-server", "--assess-only"])
        self.assertTrue(args.assess_only)

    def test_deploy_flag(self):
        parser = build_parser()
        args = parser.parse_args([
            "--source-type", "content-server",
            "--deploy",
            "--workspace-id", "abc-123",
            "--tenant-id", "tenant-456",
        ])
        self.assertTrue(args.deploy)
        self.assertEqual(args.workspace_id, "abc-123")

    def test_verbose_levels(self):
        parser = build_parser()
        args0 = parser.parse_args(["--source-type", "birt"])
        self.assertEqual(args0.verbose, 0)

        args1 = parser.parse_args(["--source-type", "birt", "-v"])
        self.assertEqual(args1.verbose, 1)

        args2 = parser.parse_args(["--source-type", "birt", "-vv"])
        self.assertEqual(args2.verbose, 2)

    def test_output_format_choices(self):
        parser = build_parser()
        for fmt in ("fabric", "pbip", "both"):
            args = parser.parse_args(["--source-type", "birt", "--output-format", fmt])
            self.assertEqual(args.output_format, fmt)


class TestConfigureLogging(unittest.TestCase):
    """Tests for logging configuration."""

    def test_default_warning_level(self):
        import logging
        configure_logging(0)
        self.assertEqual(logging.getLogger().level, logging.WARNING)


class TestMain(unittest.TestCase):
    """Tests for main() entry point."""

    @patch("sys.argv", ["migrate", "--source-type", "birt", "--input", "."])
    def test_main_returns_zero(self):
        result = main()
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
