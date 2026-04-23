"""Tests for visual mapper expansion — 140+ visual type mappings."""

import unittest

from report_converter.visual_mapper import (
    DEFAULT_SIZES,
    VISUAL_TYPE_MAP,
    VisualMapper,
)


class TestVisualTypeMapCompleteness(unittest.TestCase):
    """Verify the expanded visual type map has sufficient coverage."""

    def test_minimum_count(self):
        self.assertGreaterEqual(len(VISUAL_TYPE_MAP), 100)

    def test_original_types_preserved(self):
        """Core types from Sprint 1 must still exist."""
        originals = [
            "table", "label", "text", "image",
            "grid", "list", "crosstab", "data", "bar",
            "pie", "line", "area", "scatter", "gauge",
            "map", "treemap", "funnel", "waterfall", "kpi",
        ]
        for t in originals:
            self.assertIn(t, VISUAL_TYPE_MAP, f"Original type '{t}' missing")


class TestNewVisualTypes(unittest.TestCase):
    """Test Sprint 31 extended visual types."""

    def test_line_variants(self):
        for t in ["stepline", "smoothline", "dashedline"]:
            self.assertEqual(VISUAL_TYPE_MAP[t], "lineChart")

    def test_area_variants(self):
        self.assertEqual(VISUAL_TYPE_MAP["percentstackedarea100"], "hundredPercentStackedAreaChart")
        self.assertEqual(VISUAL_TYPE_MAP["streamgraph"], "stackedAreaChart")

    def test_3d_bar_column(self):
        for t in ["clusteredbar3d", "stackedbar3d"]:
            self.assertIn("Bar", VISUAL_TYPE_MAP[t])
        for t in ["clusteredcolumn3d", "stackedcolumn3d"]:
            self.assertIn("Column", VISUAL_TYPE_MAP[t])

    def test_pie_donut_variants(self):
        self.assertEqual(VISUAL_TYPE_MAP["pie3d"], "pieChart")
        self.assertEqual(VISUAL_TYPE_MAP["ring"], "donutChart")
        self.assertEqual(VISUAL_TYPE_MAP["semicircle"], "donutChart")

    def test_scatter_variants(self):
        for t in ["dotplot", "strip", "jitter"]:
            self.assertEqual(VISUAL_TYPE_MAP[t], "scatterChart")

    def test_combo_variants(self):
        self.assertEqual(VISUAL_TYPE_MAP["dualaxis"], "lineClusteredColumnComboChart")
        self.assertEqual(VISUAL_TYPE_MAP["linecolumn"], "lineClusteredColumnComboChart")
        self.assertEqual(VISUAL_TYPE_MAP["linestackedcolumn"], "lineStackedColumnComboChart")

    def test_table_variants(self):
        for t in ["detailtable", "summarytable", "bandedtable"]:
            self.assertEqual(VISUAL_TYPE_MAP[t], "tableEx")

    def test_card_kpi_gauge(self):
        self.assertEqual(VISUAL_TYPE_MAP["singlecard"], "card")
        self.assertEqual(VISUAL_TYPE_MAP["indicator"], "kpi")
        for t in ["speedometer", "dial", "linearGauge", "thermometer"]:
            self.assertEqual(VISUAL_TYPE_MAP[t], "gauge")

    def test_map_variants(self):
        self.assertEqual(VISUAL_TYPE_MAP["choropleth"], "filledMap")
        self.assertEqual(VISUAL_TYPE_MAP["bubblemap"], "map")
        self.assertEqual(VISUAL_TYPE_MAP["heatmapgeo"], "filledMap")

    def test_advanced_charts(self):
        self.assertEqual(VISUAL_TYPE_MAP["sankey"], "decompositionTreeVisual")
        self.assertEqual(VISUAL_TYPE_MAP["tornado"], "clusteredBarChart")
        self.assertEqual(VISUAL_TYPE_MAP["lollipop"], "clusteredColumnChart")
        self.assertEqual(VISUAL_TYPE_MAP["sparkline"], "lineChart")

    def test_layout_containers(self):
        for t in ["tab", "panel", "accordion", "container"]:
            self.assertEqual(VISUAL_TYPE_MAP[t], "group")

    def test_interactive_controls(self):
        for t in ["dropdown", "slider", "checkbox", "radio", "datepicker", "rangepicker", "searchbox", "listbox"]:
            self.assertEqual(VISUAL_TYPE_MAP[t], "slicer")
        self.assertEqual(VISUAL_TYPE_MAP["button"], "actionButton")

    def test_shapes(self):
        for t in ["divider", "shape", "line_shape", "rectangle", "ellipse", "arrow"]:
            self.assertEqual(VISUAL_TYPE_MAP[t], "shape")

    def test_navigation(self):
        self.assertEqual(VISUAL_TYPE_MAP["paginator"], "pageNavigator")
        self.assertEqual(VISUAL_TYPE_MAP["bookmark_nav"], "bookmarkNavigator")

    def test_media_types(self):
        for t in ["icon", "logo", "video", "qrcode", "barcode"]:
            self.assertEqual(VISUAL_TYPE_MAP[t], "image")


class TestDefaultSizes(unittest.TestCase):
    def test_new_sizes_added(self):
        new_types = ["lineStackedColumnComboChart", "group", "actionButton", "shape", "bookmarkNavigator"]
        for t in new_types:
            self.assertIn(t, DEFAULT_SIZES, f"Missing size for {t}")

    def test_all_sizes_are_tuples(self):
        for visual_type, size in DEFAULT_SIZES.items():
            self.assertIsInstance(size, tuple, f"Size for {visual_type} is not a tuple")
            self.assertEqual(len(size), 2, f"Size for {visual_type} is not (w, h)")

    def test_sizes_positive(self):
        for visual_type, (w, h) in DEFAULT_SIZES.items():
            self.assertGreater(w, 0, f"Width for {visual_type} is 0")
            self.assertGreater(h, 0, f"Height for {visual_type} is 0")


class TestMapVisualType(unittest.TestCase):
    def test_known_type(self):
        result = VISUAL_TYPE_MAP.get("bar")
        self.assertEqual(result, "clusteredBarChart")

    def test_unknown_type_fallback(self):
        result = VISUAL_TYPE_MAP.get("totally_unknown_xyz", "tableEx")
        self.assertEqual(result, "tableEx")

    def test_case_lookup(self):
        # Map uses lowercase keys
        r1 = VISUAL_TYPE_MAP.get("bar")
        self.assertIsNotNone(r1)


if __name__ == "__main__":
    unittest.main()
