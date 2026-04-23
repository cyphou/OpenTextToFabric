"""Phase 5 fidelity tests — conditional formatting, drill-through, multi-source,
visual mapper v2, expression converter v2, iHub integration, theme generation.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from report_converter.conditional_format import (
    ConditionalFormatConverter,
    DataBarConverter,
    GradientFormatConverter,
    IconSetConverter,
    StyleConverter,
)
from report_converter.drill_through import (
    DrillPageBuilder,
    DrillThroughConverter,
    generate_drill_page_json,
    generate_page_navigator,
)
from report_converter.expression_converter import ExpressionConverter
from report_converter.multi_datasource import DataSourceAnalyzer
from report_converter.visual_mapper import VISUAL_TYPE_MAP, VisualMapper
from opentext_extract.ihub_client import IHubClient, ScheduleConverter


# ═══════════════════════════════════════════════════════════════
# Sprint 25 — Conditional Formatting & Styles
# ═══════════════════════════════════════════════════════════════

class TestGradientFormatConverter(unittest.TestCase):

    def setUp(self):
        self.converter = GradientFormatConverter()

    def test_detect_gradient_from_ordered_rules(self):
        highlights = [
            {"operator": "lt", "value1": 100, "style": {"color": "#00FF00"}, "target_column": "Score"},
            {"operator": "gt", "value1": 500, "style": {"color": "#FF0000"}, "target_column": "Score"},
            {"operator": "between", "value1": 100, "value2": 500, "style": {"color": "#FFA500"}, "target_column": "Score"},
        ]
        result = self.converter.detect_gradient(highlights)
        self.assertIsNotNone(result)
        self.assertEqual(result["target"], "Score")
        self.assertEqual(result["type"], "gradient")
        self.assertEqual(result["minimum"]["value"], 100)
        self.assertEqual(result["maximum"]["value"], 500)

    def test_no_gradient_for_single_rule(self):
        result = self.converter.detect_gradient([
            {"operator": "gt", "value1": 100, "style": {"color": "#FF0000"}, "target_column": "X"},
        ])
        self.assertIsNone(result)

    def test_no_gradient_for_non_numeric(self):
        result = self.converter.detect_gradient([
            {"operator": "eq", "value1": "Active", "style": {"color": "#FF0000"}, "target_column": "Status"},
            {"operator": "eq", "value1": "Inactive", "style": {"color": "#00FF00"}, "target_column": "Status"},
        ])
        self.assertIsNone(result)

    def test_build_gradient_rule(self):
        rule = self.converter.build_gradient_rule("Revenue")
        self.assertEqual(rule["type"], "gradient")
        self.assertEqual(rule["target"], "Revenue")
        self.assertIn("minimum", rule)
        self.assertIn("maximum", rule)
        self.assertIn("center", rule)


class TestDataBarConverter(unittest.TestCase):

    def test_basic_data_bar(self):
        converter = DataBarConverter()
        config = converter.convert_to_data_bars("Revenue")
        self.assertEqual(config["type"], "dataBar")
        self.assertEqual(config["target"], "Revenue")
        self.assertTrue(config["showValue"])

    def test_data_bar_with_range(self):
        converter = DataBarConverter()
        config = converter.convert_to_data_bars("Score", min_value=0, max_value=100)
        self.assertEqual(config["minimum"]["value"], 0)
        self.assertEqual(config["maximum"]["value"], 100)

    def test_custom_colors(self):
        converter = DataBarConverter()
        config = converter.convert_to_data_bars(
            "Amount", positive_color="#00FF00", negative_color="#FF0000"
        )
        self.assertEqual(config["positiveColor"], "#00FF00")
        self.assertEqual(config["negativeColor"], "#FF0000")


class TestIconSetConverter(unittest.TestCase):

    def setUp(self):
        self.converter = IconSetConverter()

    def test_traffic_light_icons(self):
        result = self.converter.convert_icon_rules("Status", [30, 70])
        self.assertEqual(result["type"], "iconSet")
        self.assertEqual(result["iconSetName"], "traffic_light")
        self.assertEqual(len(result["rules"]), 3)

    def test_arrows_icons(self):
        result = self.converter.convert_icon_rules("Trend", [0, 50], icon_set="arrows")
        self.assertEqual(result["iconSetName"], "arrows")

    def test_detect_traffic_light_pattern(self):
        highlights = [
            {"test_expression": "status == 'red'", "style": {"image": "traffic_light.png"}},
        ]
        icon_set = self.converter.detect_icon_pattern(highlights)
        self.assertEqual(icon_set, "traffic_light")

    def test_detect_arrow_pattern(self):
        highlights = [
            {"test_expression": "trend == 'up'", "style": {}},
        ]
        icon_set = self.converter.detect_icon_pattern(highlights)
        self.assertEqual(icon_set, "arrows")

    def test_no_pattern_detected(self):
        highlights = [
            {"test_expression": "x > 5", "style": {"color": "#FF0000"}},
        ]
        icon_set = self.converter.detect_icon_pattern(highlights)
        self.assertIsNone(icon_set)

    def test_all_icon_sets_available(self):
        for name in ("traffic_light", "arrows", "flags", "stars"):
            self.assertIn(name, IconSetConverter.ICON_SETS)


class TestThemeGeneration(unittest.TestCase):

    def test_generate_theme_file_to_disk(self):
        converter = StyleConverter()
        styles = [
            {"color": "#FF0000", "font-family": "Segoe UI"},
            {"color": "#0000FF", "font-family": "Segoe UI"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "theme.json"
            theme = converter.generate_theme_file(styles, output_path=str(path))
            self.assertTrue(path.exists())
            data = json.loads(path.read_text())
            self.assertIn("$schema", data)
            self.assertIn("textClasses", data)
            self.assertIn("visualStyles", data)
            self.assertEqual(data["name"], "MigratedTheme")

    def test_theme_with_chart_palettes(self):
        converter = StyleConverter()
        palettes = [["#FF6384", "#36A2EB", "#FFCE56"]]
        theme = converter.generate_theme_file([], chart_palettes=palettes)
        self.assertTrue(len(theme["dataColors"]) >= 3)

    def test_theme_font_classes(self):
        converter = StyleConverter()
        styles = [{"font-family": "Courier New"}]
        theme = converter.generate_theme_file(styles)
        self.assertEqual(theme["textClasses"]["label"]["fontFace"], "Courier New")


# ═══════════════════════════════════════════════════════════════
# Sprint 26 — Drill-Through & Sub-Reports
# ═══════════════════════════════════════════════════════════════

class TestPageNavigator(unittest.TestCase):

    def test_generate_page_navigator(self):
        pages = [
            {"name": "Page1", "displayName": "Overview"},
            {"name": "Page2", "displayName": "Details"},
            {"name": "DrillPage_1", "displayName": "Customer Detail"},
        ]
        nav = generate_page_navigator(pages)
        self.assertEqual(nav["visual_type"], "pageNavigator")
        self.assertEqual(len(nav["config"]["buttons"]), 3)
        self.assertEqual(nav["config"]["buttons"][0]["name"], "Overview")

    def test_empty_pages(self):
        nav = generate_page_navigator([])
        self.assertEqual(len(nav["config"]["buttons"]), 0)


class TestDrillPageBuilder(unittest.TestCase):

    def test_build_from_hyperlinks(self):
        builder = DrillPageBuilder()
        hyperlinks = [
            {"target_report": "Detail", "parameters": {"id": "123"},
             "source_column": "Name", "action": "drillthrough"},
        ]
        pages = builder.build_pages(hyperlinks, [])
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["type"], 1)

    def test_build_from_subreports(self):
        builder = DrillPageBuilder()
        subreports = [
            {"name": "SubReport1", "parameters": {"dept": "Finance"}, "data_set": "DS1"},
        ]
        pages = builder.build_pages([], subreports)
        self.assertEqual(len(pages), 1)

    def test_build_mixed_hyperlinks_and_subreports(self):
        builder = DrillPageBuilder()
        hyperlinks = [
            {"target_report": "Page1", "parameters": {},
             "source_column": "A", "action": "drillthrough"},
        ]
        subreports = [
            {"name": "Sub1", "parameters": {}, "data_set": "DS1"},
        ]
        pages = builder.build_pages(hyperlinks, subreports)
        self.assertEqual(len(pages), 2)

    def test_empty_inputs(self):
        builder = DrillPageBuilder()
        pages = builder.build_pages([], [])
        self.assertEqual(len(pages), 0)


# ═══════════════════════════════════════════════════════════════
# Sprint 27 — Multi-Data-Source Reports
# ═══════════════════════════════════════════════════════════════

class TestMultiDataSourceV2(unittest.TestCase):

    def setUp(self):
        self.analyzer = DataSourceAnalyzer()

    def test_generate_m_queries(self):
        connections = [
            {"name": "OracleDS", "odaDriverClass": "oracle.jdbc.OracleDriver",
             "odaURL": "jdbc:oracle:thin:@host:1521:xe", "type": "jdbc"},
        ]
        datasets = [
            {"name": "Sales", "data_source": "OracleDS", "query": "SELECT * FROM sales"},
        ]
        result = self.analyzer.generate_m_queries(connections, datasets)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["dataset_name"], "Sales")
        self.assertEqual(result[0]["source_name"], "OracleDS")
        self.assertTrue(len(result[0]["m_query"]) > 0)

    def test_composite_model_generation(self):
        connections = [
            {"name": "Oracle", "odaDriverClass": "oracle.jdbc.OracleDriver",
             "odaURL": "jdbc:oracle:thin:@host:1521:xe", "type": "jdbc"},
            {"name": "CSV", "driver": "", "type": "csv"},
        ]
        datasets = [
            {"name": "Sales", "data_source": "Oracle", "query": "SELECT * FROM sales"},
            {"name": "Lookup", "data_source": "CSV"},
        ]
        model = self.analyzer.build_composite_model(connections, datasets)
        self.assertEqual(model["model_mode"], "composite")
        self.assertEqual(len(model["tables"]), 2)
        self.assertTrue(model["total_sources"] >= 2)

    def test_cross_source_relationship_suggestion(self):
        datasets = [
            {"name": "Orders", "data_source": "Oracle",
             "column_hints": [{"columnName": "customer_id"}, {"columnName": "amount"}]},
            {"name": "Customers", "data_source": "CSV",
             "column_hints": [{"columnName": "customer_id"}, {"columnName": "name"}]},
        ]
        rels = self.analyzer._suggest_cross_source_relationships(datasets)
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0]["column"], "customer_id")

    def test_no_cross_source_relationships(self):
        datasets = [
            {"name": "Sales", "column_hints": [{"columnName": "amount"}]},
            {"name": "Products", "column_hints": [{"columnName": "name"}]},
        ]
        rels = self.analyzer._suggest_cross_source_relationships(datasets)
        self.assertEqual(len(rels), 0)


# ═══════════════════════════════════════════════════════════════
# Sprint 28 — Visual Fidelity Improvements
# ═══════════════════════════════════════════════════════════════

class TestVisualMapperV2(unittest.TestCase):

    def test_visual_map_has_35_plus_types(self):
        unique_pbi_types = set(VISUAL_TYPE_MAP.values())
        self.assertGreaterEqual(len(unique_pbi_types), 20)
        # Total mappings (many BIRT types → same PBI type)
        self.assertGreaterEqual(len(VISUAL_TYPE_MAP), 35)

    def test_new_visual_types_mapped(self):
        new_types = {
            "histogram": "clusteredColumnChart",
            "heatmap": "tableHeatmap",
            "rvisual": "scriptVisual",
            "narrative": "smartNarrative",
            "progress": "gauge",
            "percentstackedarea": "hundredPercentStackedAreaChart",
        }
        for birt, pbi in new_types.items():
            self.assertEqual(VISUAL_TYPE_MAP[birt], pbi,
                             f"Expected {birt} → {pbi}")

    def test_chart_axis_mapping(self):
        mapper = VisualMapper()
        element = {
            "element_type": "extended-item",
            "extension_name": "Chart",
            "name": "AxisChart",
            "chart_config": {
                "chart_type": "bar",
                "axes": [
                    {"type": "category", "title": "Product", "showGridlines": False},
                    {"type": "linear", "title": "Revenue", "min": 0, "max": 1000000},
                ],
                "series": [],
                "categories": [],
            },
            "properties": {},
            "children": [],
            "expressions": [],
        }
        visual = mapper.map_element(element)
        axes = visual["chart_config"]["axes"]
        self.assertEqual(len(axes), 2)
        self.assertEqual(axes[0]["title"], "Product")
        self.assertTrue(axes[0]["showTitle"])
        self.assertEqual(axes[1]["rangeMax"], 1000000)

    def test_legend_mapping(self):
        mapper = VisualMapper()
        element = {
            "element_type": "extended-item",
            "extension_name": "Chart",
            "name": "LegendChart",
            "chart_config": {
                "chart_type": "pie",
                "legend": {"position": "bottom", "visible": True, "fontSize": 11},
                "series": [],
                "categories": [],
            },
            "properties": {},
            "children": [],
            "expressions": [],
        }
        visual = mapper.map_element(element)
        legend = visual["chart_config"]["legend"]
        self.assertEqual(legend["position"], "bottom")
        self.assertTrue(legend["show"])
        self.assertEqual(legend["fontSize"], 11)

    def test_tooltip_mapping(self):
        mapper = VisualMapper()
        element = {
            "element_type": "extended-item",
            "extension_name": "Chart",
            "name": "TooltipChart",
            "chart_config": {
                "chart_type": "line",
                "tooltip": {"expression": "Revenue: $" + "{value}", "format": "#,##0"},
                "series": [],
                "categories": [],
            },
            "properties": {},
            "children": [],
            "expressions": [],
        }
        visual = mapper.map_element(element)
        tooltip = visual["chart_config"]["tooltip"]
        self.assertTrue(tooltip["show"])
        self.assertIn("custom_expression", tooltip)

    def test_group_subtotals_mapping(self):
        mapper = VisualMapper()
        element = {
            "element_type": "table",
            "name": "GroupTable",
            "dataset": "Sales",
            "columns": [{"name": "amount"}],
            "groups": [
                {"name": "RegionGroup", "key_expr": "region"},
                {"name": "YearGroup", "key_expr": "year"},
            ],
            "properties": {},
            "children": [],
            "expressions": [],
        }
        visual = mapper.map_element(element)
        self.assertIn("subtotals", visual)
        self.assertEqual(len(visual["subtotals"]), 2)
        self.assertEqual(visual["subtotals"][0]["group_name"], "RegionGroup")
        self.assertTrue(visual["subtotals"][0]["show_header"])

    def test_deep_traversal_finds_nested_tables(self):
        """Tables nested in grid→row→cell must be found by map_all()."""
        mapper = VisualMapper()
        elements = [
            {
                "element_type": "grid", "name": "Layout",
                "properties": {}, "children": [
                    {"element_type": "column", "name": "", "properties": {},
                     "children": [], "expressions": []},
                    {"element_type": "row", "name": "", "properties": {},
                     "children": [
                         {"element_type": "cell", "name": "", "properties": {},
                          "children": [
                              {"element_type": "table", "name": "Sales",
                               "dataset": "SalesDS",
                               "columns": [{"name": "Region"}, {"name": "Revenue"}],
                               "groups": [], "properties": {},
                               "children": [], "expressions": []},
                          ], "expressions": []},
                     ], "expressions": []},
                ], "expressions": [],
            },
        ]
        visuals = mapper.map_all(elements)
        tables = [v for v in visuals if v["visual_type"] == "tableEx"]
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["dataset"], "SalesDS")
        self.assertEqual(len(tables[0]["columns"]), 2)

    def test_structural_elements_not_mapped_as_visuals(self):
        """Column/row/cell/group layout elements must not become PBI visuals."""
        mapper = VisualMapper()
        elements = [
            {
                "element_type": "table", "name": "T1", "dataset": "DS1",
                "columns": [{"name": "A"}], "groups": [], "properties": {},
                "children": [
                    {"element_type": "column", "name": "", "properties": {},
                     "children": [], "expressions": []},
                    {"element_type": "column", "name": "", "properties": {},
                     "children": [], "expressions": []},
                    {"element_type": "row", "name": "", "properties": {},
                     "children": [], "expressions": []},
                    {"element_type": "header", "name": "", "properties": {},
                     "children": [], "expressions": []},
                    {"element_type": "detail", "name": "", "properties": {},
                     "children": [], "expressions": []},
                    {"element_type": "group", "name": "", "properties": {},
                     "children": [], "expressions": []},
                ], "expressions": [],
            },
        ]
        visuals = mapper.map_all(elements)
        # Only the table itself — no structural children
        self.assertEqual(len(visuals), 1)
        self.assertEqual(visuals[0]["visual_type"], "tableEx")

    def test_visual_query_state_generated_for_table(self):
        """Tables with columns+dataset must produce a queryState in PBIR."""
        from report_converter.pbip_generator import PBIPGenerator
        mapper = VisualMapper()
        elements = [
            {
                "element_type": "table", "name": "Sales", "dataset": "SalesDS",
                "columns": [{"name": "Region"}, {"name": "Revenue"}],
                "groups": [], "properties": {},
                "children": [], "expressions": [],
            },
        ]
        visuals = mapper.map_all(elements)
        gen = PBIPGenerator("Test")
        config = gen._build_visual_config(visuals[0])
        query = config["visual"].get("query", {})
        qs = query.get("queryState", {})
        self.assertIn("Values", qs)
        projections = qs["Values"]["projections"]
        self.assertEqual(len(projections), 2)
        self.assertEqual(projections[0]["queryRef"], "SalesDS.Region")
        self.assertEqual(projections[1]["queryRef"], "SalesDS.Revenue")


# ═══════════════════════════════════════════════════════════════
# Sprint 29 — iHub / Server Integration
# ═══════════════════════════════════════════════════════════════

class TestScheduleConverter(unittest.TestCase):

    def test_convert_daily_schedule(self):
        converter = ScheduleConverter()
        schedules = [
            {"name": "Daily Refresh", "frequency": "daily", "cron": "0 6 * * *"},
        ]
        result = converter.convert_schedules(schedules)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["frequency"], "Daily")
        self.assertIn("06:00", result[0]["times"])

    def test_convert_weekly_schedule(self):
        converter = ScheduleConverter()
        schedules = [
            {"name": "Weekly", "frequency": "weekly", "cron": "30 8 * * 1,3,5"},
        ]
        result = converter.convert_schedules(schedules)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["frequency"], "Weekly")
        self.assertIn("Monday", result[0]["days"])
        self.assertIn("Friday", result[0]["days"])

    def test_parse_cron_time(self):
        result = ScheduleConverter._parse_cron("30 14 * * *")
        self.assertEqual(result["times"], ["14:30"])

    def test_parse_cron_weekdays(self):
        result = ScheduleConverter._parse_cron("0 9 * * 1,2,3,4,5")
        self.assertEqual(len(result["days"]), 5)
        self.assertIn("Monday", result["days"])
        self.assertNotIn("Saturday", result["days"])

    def test_empty_schedule(self):
        converter = ScheduleConverter()
        result = converter.convert_schedules([])
        self.assertEqual(len(result), 0)


class TestIHubBulkMigration(unittest.TestCase):

    def setUp(self):
        self.client = IHubClient(
            base_url="https://ihub.example.com",
            username="admin",
            password="pass",
        )
        self.client._auth_token = "test_token"

    @patch.object(IHubClient, "discover_reports")
    @patch.object(IHubClient, "download_report")
    def test_bulk_download(self, mock_download, mock_discover):
        mock_discover.return_value = [
            {"name": "report1.rptdesign", "path": "/Reports/report1.rptdesign"},
            {"name": "report2.rptdesign", "path": "/Reports/report2.rptdesign"},
        ]
        mock_download.return_value = ""

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create dummy files so stat() works
            (Path(tmpdir) / "Reports").mkdir(parents=True)
            for name in ("report1.rptdesign", "report2.rptdesign"):
                (Path(tmpdir) / "Reports" / name).write_text("<report/>")

            mock_download.side_effect = lambda src, dst: Path(dst).parent.mkdir(parents=True, exist_ok=True) or Path(dst).write_text("<report/>") or dst
            results = self.client.bulk_download_reports("/Reports", tmpdir)
            self.assertEqual(len(results), 2)
            self.assertTrue(all(r["status"] == "success" for r in results))

    @patch.object(IHubClient, "discover_reports")
    @patch.object(IHubClient, "get_data_sources")
    @patch.object(IHubClient, "get_schedules")
    def test_build_migration_inventory(self, mock_sched, mock_ds, mock_reports):
        mock_reports.return_value = [
            {"name": "r1.rptdesign", "path": "/r1.rptdesign", "parameters": []},
            {"name": "r2.rptdesign", "path": "/r2.rptdesign",
             "parameters": [{"name": "date", "dataType": "date"}]},
        ]
        mock_ds.return_value = [{"name": "OracleDS"}]
        mock_sched.return_value = [{"name": "Daily"}]

        inventory = self.client.build_migration_inventory()
        self.assertEqual(inventory["total_reports"], 2)
        self.assertEqual(inventory["parameterized_reports"], 1)
        self.assertEqual(inventory["total_data_sources"], 1)
        self.assertEqual(inventory["total_schedules"], 1)
        self.assertEqual(inventory["complexity_breakdown"]["simple"], 1)
        self.assertEqual(inventory["complexity_breakdown"]["parameterized"], 1)


# ═══════════════════════════════════════════════════════════════
# Sprint 25 (Expression Converter v2) — LOD, Window, Date Intelligence
# ═══════════════════════════════════════════════════════════════

class TestExpressionConverterV2(unittest.TestCase):

    def setUp(self):
        self.converter = ExpressionConverter()

    # LOD / cross-tab aggregations
    def test_sum_by_group(self):
        result = self.converter.convert('Total.sumByGroup(row["amount"], row["region"])')
        self.assertIn("CALCULATE", result["converted"])
        self.assertIn("ALLEXCEPT", result["converted"])

    def test_percent_of_group(self):
        result = self.converter.convert('Total.percentOfGroup(row["amount"], row["region"])')
        self.assertIn("DIVIDE", result["converted"])
        self.assertIn("ALLEXCEPT", result["converted"])

    # Window functions
    def test_running_avg(self):
        result = self.converter.convert('Total.runningAvg(row["amount"])')
        self.assertIn("AVERAGE", result["converted"])
        self.assertIn("EARLIER", result["converted"])

    def test_dense_rank(self):
        result = self.converter.convert('Total.denseRank(row["score"])')
        self.assertIn("RANKX", result["converted"])
        self.assertIn("Dense", result["converted"])

    def test_lag(self):
        result = self.converter.convert('Total.lag(row["value"], 1)')
        self.assertIn("LOOKUPVALUE", result["converted"])

    def test_lead(self):
        result = self.converter.convert('Total.lead(row["value"], 2)')
        self.assertIn("LOOKUPVALUE", result["converted"])

    def test_ntile(self):
        result = self.converter.convert('Total.ntile(row["score"], 4)')
        self.assertIn("RANKX", result["converted"])

    # Date intelligence
    def test_datetime_span_year(self):
        result = self.converter.convert(
            'BirtDateTime.dateTimeSpan(row["start"], row["end"], "year")'
        )
        self.assertIn("DATEDIFF", result["converted"])
        self.assertIn("YEAR", result["converted"])

    def test_format_date(self):
        result = self.converter.convert('BirtDateTime.formatDate(row["date"], "yyyy-MM")')
        self.assertIn("FORMAT", result["converted"])

    def test_is_weekday(self):
        result = self.converter.convert('BirtDateTime.isWeekday(row["date"])')
        self.assertIn("WEEKDAY", result["converted"])

    def test_month_name(self):
        result = self.converter.convert('BirtDateTime.monthName(row["date"])')
        self.assertIn("FORMAT", result["converted"])
        self.assertIn("MMMM", result["converted"])

    def test_iso_week(self):
        result = self.converter.convert('BirtDateTime.isoWeek(row["date"])')
        self.assertIn("WEEKNUM", result["converted"])

    def test_start_of_week(self):
        result = self.converter.convert('BirtDateTime.startOfWeek(row["date"])')
        self.assertIn("WEEKDAY", result["converted"])

    # Parameter wiring
    def test_param_display_text(self):
        result = self.converter.convert('params["Region"].displayText')
        self.assertIn("SELECTEDVALUE", result["converted"])

    def test_param_dot_notation(self):
        result = self.converter.convert("params.StartDate.value")
        self.assertEqual(result["converted"], "[@StartDate]")


# ═══════════════════════════════════════════════════════════════
# Sprint 25 — BIRT Parser highlight/hyperlink extraction
# ═══════════════════════════════════════════════════════════════

class TestBIRTParserHighlightsHyperlinks(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        rptdesign = """<?xml version="1.0" encoding="UTF-8"?>
<report version="3.2.23">
    <data-sources>
        <oda-data-source name="DB" id="1">
            <property name="extensionID">org.eclipse.birt.report.data.oda.jdbc</property>
        </oda-data-source>
    </data-sources>
    <data-sets>
        <oda-data-set name="DS1" id="2">
            <property name="dataSource">DB</property>
            <property name="queryText">SELECT id, amount FROM t</property>
        </oda-data-set>
    </data-sets>
    <parameters/>
    <styles/>
    <page-setup>
        <simple-master-page name="Page" id="3"/>
    </page-setup>
    <body>
        <table name="T1" id="4">
            <property name="dataSet">DS1</property>
            <list-property name="highlightRules">
                <structure>
                    <property name="operator">gt</property>
                    <property name="value1">1000</property>
                    <property name="color">#FF0000</property>
                </structure>
            </list-property>
            <list-property name="action">
                <structure>
                    <property name="linkType">drill-through</property>
                    <property name="reportName">DetailReport</property>
                    <list-property name="paramBindings">
                        <structure>
                            <property name="paramName">orderId</property>
                            <expression name="expression" type="javascript">row["id"]</expression>
                        </structure>
                    </list-property>
                </structure>
            </list-property>
        </table>
    </body>
</report>"""
        self.report_path = Path(self.tmpdir) / "highlights_test.rptdesign"
        self.report_path.write_text(rptdesign, encoding="utf-8")

    def test_extract_highlights(self):
        from opentext_extract.birt_parser import BIRTParser
        parser = BIRTParser(self.report_path)
        data = parser.parse()
        highlights = data["highlights"]
        self.assertEqual(len(highlights), 1)
        self.assertEqual(highlights[0]["operator"], "gt")
        self.assertEqual(highlights[0]["value1"], "1000")

    def test_extract_hyperlinks(self):
        from opentext_extract.birt_parser import BIRTParser
        parser = BIRTParser(self.report_path)
        data = parser.parse()
        hyperlinks = data["hyperlinks"]
        self.assertEqual(len(hyperlinks), 1)
        self.assertEqual(hyperlinks[0]["target_report"], "DetailReport")
        self.assertIn("orderId", hyperlinks[0]["parameters"])

    def test_export_json_includes_highlights_hyperlinks(self):
        from opentext_extract.birt_parser import BIRTParser
        parser = BIRTParser(self.report_path)
        with tempfile.TemporaryDirectory() as outdir:
            files = parser.export_json(outdir)
            self.assertIn("highlights.json", files)
            self.assertIn("hyperlinks.json", files)
            hl_data = json.loads(Path(files["highlights.json"]).read_text())
            self.assertEqual(len(hl_data), 1)


# ═══════════════════════════════════════════════════════════════
# Regression — Ensure existing patterns still work
# ═══════════════════════════════════════════════════════════════

class TestExpressionConverterRegression(unittest.TestCase):
    """Verify existing expression patterns are not broken by v2 additions."""

    def setUp(self):
        self.converter = ExpressionConverter()

    def test_total_sum(self):
        result = self.converter.convert('Total.sum(row["amount"])')
        self.assertEqual(result["converted"], "SUM([amount])")

    def test_birt_str_upper(self):
        result = self.converter.convert('BirtStr.toUpper(row["name"])')
        self.assertEqual(result["converted"], "UPPER([name])")

    def test_birt_datetime_year(self):
        result = self.converter.convert('BirtDateTime.year(row["date"])')
        self.assertEqual(result["converted"], "YEAR([date])")

    def test_ternary_conversion(self):
        result = self.converter.convert('row["amount"] > 100 ? "High" : "Low"')
        self.assertIn("IF", result["converted"])

    def test_row_reference(self):
        result = self.converter.convert('row["x"]')
        self.assertEqual(result["converted"], "[x]")

    def test_params_reference(self):
        result = self.converter.convert('params["Region"].value')
        self.assertEqual(result["converted"], "[@Region]")


if __name__ == "__main__":
    unittest.main()
