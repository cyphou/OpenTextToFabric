"""Tests for reporting.telemetry — event tracking, dashboard, metrics export."""

import json
import os
import tempfile
import unittest

from reporting.telemetry import (
    MetricsExporter,
    TelemetryCollector,
    TelemetryDashboard,
    TelemetryEvent,
)


class TestTelemetryEvent(unittest.TestCase):
    def test_creation(self):
        e = TelemetryEvent("expression", "convert", "sum", 1.0)
        self.assertEqual(e.category, "expression")
        self.assertEqual(e.action, "convert")
        self.assertEqual(e.label, "sum")
        self.assertEqual(e.value, 1.0)

    def test_default_value(self):
        e = TelemetryEvent("test", "run", "x")
        self.assertEqual(e.value, 0.0)

    def test_timestamp(self):
        e = TelemetryEvent("test", "run", "x")
        self.assertIsNotNone(e.timestamp)

    def test_to_dict(self):
        e = TelemetryEvent("cat", "act", "lbl", 5.0)
        d = e.to_dict()
        self.assertEqual(d["category"], "cat")
        self.assertEqual(d["action"], "act")


class TestTelemetryCollector(unittest.TestCase):
    def setUp(self):
        self.tc = TelemetryCollector()

    def test_track_expression(self):
        self.tc.track_expression("row[\"X\"]", "[X]", "converted")
        events = self.tc.get_events("expression")
        self.assertEqual(len(events), 1)

    def test_track_visual(self):
        self.tc.track_visual("chart", "clusteredColumnChart")
        events = self.tc.get_events("visual")
        self.assertEqual(len(events), 1)

    def test_track_measure(self):
        self.tc.track_measure("Revenue", "Sales")
        events = self.tc.get_events("measure")
        self.assertEqual(len(events), 1)

    def test_track_relationship(self):
        self.tc.track_relationship("T1", "T2", "col")
        events = self.tc.get_events("relationship")
        self.assertEqual(len(events), 1)

    def test_track_step(self):
        self.tc.track_step("extraction", 0.5, "completed")
        events = self.tc.get_events("pipeline")
        self.assertEqual(len(events), 1)

    def test_track_error(self):
        self.tc.track_error("conversion", "Failed to parse expression")
        events = self.tc.get_events("conversion")
        self.assertEqual(len(events), 1)

    def test_multiple_events(self):
        self.tc.track_expression("a", "b", "ok")
        self.tc.track_visual("c", "d")
        self.tc.track_error("e", "f")
        all_events = self.tc.get_events()
        self.assertEqual(len(all_events), 3)

    def test_summary(self):
        self.tc.track_expression("a", "b", "converted")
        self.tc.track_expression("c", "d", "failed")
        self.tc.track_visual("e", "f")
        s = self.tc.summary()
        self.assertEqual(s["total_events"], 3)
        self.assertIn("categories", s)

    def test_empty_summary(self):
        s = self.tc.summary()
        self.assertEqual(s["total_events"], 0)

    def test_export_json(self):
        self.tc.track_expression("a", "b", "ok")
        with tempfile.TemporaryDirectory() as td:
            path = self.tc.export_json(os.path.join(td, "events.json"))
            self.assertTrue(path.exists())
            data = json.loads(path.read_text())
            self.assertEqual(len(data), 1)


class TestTelemetryDashboard(unittest.TestCase):
    def test_generate_html(self):
        tc = TelemetryCollector()
        tc.track_expression("a", "b", "converted")
        tc.track_visual("c", "d")
        tc.track_error("convert", "failure")
        dashboard = TelemetryDashboard(tc)
        with tempfile.TemporaryDirectory() as td:
            path = dashboard.generate(os.path.join(td, "dashboard.html"))
            self.assertTrue(path.exists())
            html = path.read_text()
            self.assertIn("<html", html)
            self.assertIn("Telemetry", html)

    def test_empty_dashboard(self):
        tc = TelemetryCollector()
        dashboard = TelemetryDashboard(tc)
        with tempfile.TemporaryDirectory() as td:
            path = dashboard.generate(os.path.join(td, "dashboard.html"))
            self.assertTrue(path.exists())
            html = path.read_text()
            self.assertIn("<html", html)


class TestMetricsExporter(unittest.TestCase):
    def test_export_json(self):
        tc = TelemetryCollector()
        tc.track_expression("a", "b", "ok")
        exporter = MetricsExporter(tc)
        with tempfile.TemporaryDirectory() as td:
            path = exporter.export_json(os.path.join(td, "metrics.json"))
            self.assertTrue(path.exists())

    def test_export_prometheus(self):
        tc = TelemetryCollector()
        tc.track_expression("a", "b", "ok")
        tc.track_visual("c", "d")
        exporter = MetricsExporter(tc)
        with tempfile.TemporaryDirectory() as td:
            path = exporter.export_prometheus(os.path.join(td, "metrics.prom"))
            self.assertTrue(path.exists())
            content = path.read_text()
            self.assertIn("migration_events_total", content)

    def test_export_azure_monitor(self):
        tc = TelemetryCollector()
        tc.track_step("extract", 0.5)
        exporter = MetricsExporter(tc)
        result = exporter.export_azure_monitor()
        self.assertIn("metrics", result)
        self.assertGreater(len(result["metrics"]), 0)

    def test_empty_export(self):
        tc = TelemetryCollector()
        exporter = MetricsExporter(tc)
        result = exporter.export_azure_monitor()
        self.assertEqual(len(result["metrics"]), 0)


if __name__ == "__main__":
    unittest.main()
