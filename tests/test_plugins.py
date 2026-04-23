"""Tests for report_converter.plugins — extensible plugin registry."""

import unittest
from typing import Any

from report_converter.plugins import (
    DaxPlugin,
    ExpressionPlugin,
    PluginRegistry,
    VisualPlugin,
    get_registry,
    reset_registry,
)


class _MockVisualPlugin:
    """Visual plugin that maps 'custom_chart' to a card."""
    def map_visual(self, element: dict[str, Any]) -> dict[str, Any] | None:
        if element.get("type") == "custom_chart":
            return {"visualType": "card", "title": "custom"}
        return None


class _MockDaxPlugin:
    """DAX plugin that adds a comment prefix."""
    def process(self, dax: str, context: dict[str, Any]) -> str:
        return f"/* optimized */ {dax}"


class _MockExpressionPlugin:
    """Expression plugin that uppercases."""
    def preprocess(self, expression: str, source: str) -> str:
        return expression.upper()


class TestPluginRegistryInit(unittest.TestCase):
    def test_empty_registry(self):
        r = PluginRegistry()
        s = r.summary()
        self.assertEqual(s["visual_plugins"], 0)
        self.assertEqual(s["dax_plugins"], 0)
        self.assertEqual(s["expression_plugins"], 0)
        self.assertEqual(s["birt_function_handlers"], 0)
        self.assertEqual(s["visual_type_overrides"], 0)
        self.assertEqual(s["loaded_modules"], [])


class TestVisualPlugins(unittest.TestCase):
    def test_register_and_apply(self):
        r = PluginRegistry()
        r.register_visual_plugin(_MockVisualPlugin())
        result = r.apply_visual_plugins({"type": "custom_chart"})
        self.assertIsNotNone(result)
        self.assertEqual(result["visualType"], "card")

    def test_no_match_returns_none(self):
        r = PluginRegistry()
        r.register_visual_plugin(_MockVisualPlugin())
        result = r.apply_visual_plugins({"type": "bar"})
        self.assertIsNone(result)

    def test_first_plugin_wins(self):
        r = PluginRegistry()
        class P2:
            def map_visual(self, e):
                return {"visualType": "table"}
        r.register_visual_plugin(_MockVisualPlugin())
        r.register_visual_plugin(P2())
        result = r.apply_visual_plugins({"type": "custom_chart"})
        self.assertEqual(result["visualType"], "card")

    def test_multiple_visual_plugins_count(self):
        r = PluginRegistry()
        r.register_visual_plugin(_MockVisualPlugin())
        r.register_visual_plugin(_MockVisualPlugin())
        self.assertEqual(r.summary()["visual_plugins"], 2)


class TestDaxPlugins(unittest.TestCase):
    def test_register_and_apply(self):
        r = PluginRegistry()
        r.register_dax_plugin(_MockDaxPlugin())
        result = r.apply_dax_plugins("SUM([X])")
        self.assertEqual(result, "/* optimized */ SUM([X])")

    def test_chained_plugins(self):
        r = PluginRegistry()
        r.register_dax_plugin(_MockDaxPlugin())
        r.register_dax_plugin(_MockDaxPlugin())
        result = r.apply_dax_plugins("SUM([X])")
        self.assertEqual(result, "/* optimized */ /* optimized */ SUM([X])")

    def test_no_plugins_passthrough(self):
        r = PluginRegistry()
        result = r.apply_dax_plugins("SUM([X])")
        self.assertEqual(result, "SUM([X])")

    def test_context_passed(self):
        class ContextAware:
            def process(self, dax, context):
                return f"{context.get('prefix', '')}{dax}"
        r = PluginRegistry()
        r.register_dax_plugin(ContextAware())
        result = r.apply_dax_plugins("SUM([X])", {"prefix": "HELLO_"})
        self.assertEqual(result, "HELLO_SUM([X])")


class TestExpressionPlugins(unittest.TestCase):
    def test_register_and_apply(self):
        r = PluginRegistry()
        r.register_expression_plugin(_MockExpressionPlugin())
        result = r.apply_expression_plugins("hello world")
        self.assertEqual(result, "HELLO WORLD")

    def test_no_plugins_passthrough(self):
        r = PluginRegistry()
        result = r.apply_expression_plugins("hello")
        self.assertEqual(result, "hello")


class TestBirtFunctionHandlers(unittest.TestCase):
    def test_register_and_get(self):
        r = PluginRegistry()
        r.register_birt_function("Custom.fn", lambda s: f"DAX({s})")
        handler = r.get_birt_function_handler("Custom.fn")
        self.assertIsNotNone(handler)
        self.assertEqual(handler("X"), "DAX(X)")

    def test_missing_handler_returns_none(self):
        r = PluginRegistry()
        self.assertIsNone(r.get_birt_function_handler("Nonexistent.fn"))


class TestVisualTypeOverrides(unittest.TestCase):
    def test_register_and_get(self):
        r = PluginRegistry()
        r.register_visual_type_override("mychart", "lineChart")
        self.assertEqual(r.get_visual_type_override("mychart"), "lineChart")

    def test_missing_override(self):
        r = PluginRegistry()
        self.assertIsNone(r.get_visual_type_override("unknown"))


class TestLoadPluginModule(unittest.TestCase):
    def test_missing_module(self):
        r = PluginRegistry()
        # Should log error but not raise
        r.load_plugin_module("nonexistent.module.path")
        self.assertEqual(r.summary()["loaded_modules"], [])


class TestGlobalRegistry(unittest.TestCase):
    def setUp(self):
        reset_registry()

    def tearDown(self):
        reset_registry()

    def test_singleton(self):
        r1 = get_registry()
        r2 = get_registry()
        self.assertIs(r1, r2)

    def test_reset(self):
        r1 = get_registry()
        r1.register_visual_plugin(_MockVisualPlugin())
        reset_registry()
        r2 = get_registry()
        self.assertEqual(r2.summary()["visual_plugins"], 0)


class TestSummary(unittest.TestCase):
    def test_counts(self):
        r = PluginRegistry()
        r.register_visual_plugin(_MockVisualPlugin())
        r.register_dax_plugin(_MockDaxPlugin())
        r.register_expression_plugin(_MockExpressionPlugin())
        r.register_birt_function("fn1", lambda s: s)
        r.register_visual_type_override("t1", "card")
        s = r.summary()
        self.assertEqual(s["visual_plugins"], 1)
        self.assertEqual(s["dax_plugins"], 1)
        self.assertEqual(s["expression_plugins"], 1)
        self.assertEqual(s["birt_function_handlers"], 1)
        self.assertEqual(s["visual_type_overrides"], 1)


if __name__ == "__main__":
    unittest.main()
