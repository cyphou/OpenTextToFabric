"""Tests for report_converter.drill_through."""

import unittest

from report_converter.drill_through import (
    DrillThroughConverter,
    generate_drill_page_json,
)


class TestDrillThroughConverter(unittest.TestCase):

    def setUp(self):
        self.converter = DrillThroughConverter()

    def test_same_report_drill(self):
        hyperlinks = [{
            "target_report": "DetailPage",
            "parameters": {"CustomerId": 'row["id"]'},
            "source_column": "CustomerName",
            "action": "drillthrough",
        }]
        result = self.converter.convert_hyperlinks(hyperlinks)
        self.assertEqual(len(result["drill_pages"]), 1)
        page = result["drill_pages"][0]
        self.assertEqual(page["name"], "DetailPage")
        self.assertEqual(page["type"], "drillThrough")
        self.assertEqual(len(page["filters"]), 1)

    def test_url_action(self):
        hyperlinks = [{
            "target_report": "https://example.com",
            "source_column": "Link",
            "action": "url",
        }]
        result = self.converter.convert_hyperlinks(hyperlinks)
        self.assertEqual(len(result["bookmarks"]), 1)
        self.assertEqual(result["bookmarks"][0]["type"], "webUrl")

    def test_bookmark_action(self):
        hyperlinks = [{
            "target_report": "SummaryView",
            "source_column": "Toggle",
            "action": "bookmark",
        }]
        result = self.converter.convert_hyperlinks(hyperlinks)
        self.assertEqual(len(result["bookmarks"]), 1)
        self.assertEqual(result["bookmarks"][0]["type"], "bookmark")

    def test_cross_report_drill(self):
        hyperlinks = [{
            "target_report": "reports/detail.rptdesign",
            "parameters": {"id": "123"},
            "source_column": "Name",
            "action": "drillthrough",
        }]
        result = self.converter.convert_hyperlinks(hyperlinks)
        self.assertEqual(len(result["cross_report"]), 1)
        self.assertEqual(result["cross_report"][0]["target_report"], "reports/detail.rptdesign")

    def test_mixed_hyperlinks(self):
        hyperlinks = [
            {"target_report": "Page1", "source_column": "A", "action": "drillthrough", "parameters": {}},
            {"target_report": "https://x.com", "source_column": "B", "action": "url"},
            {"target_report": "sub/rpt.rptdesign", "source_column": "C", "action": "drillthrough", "parameters": {}},
        ]
        result = self.converter.convert_hyperlinks(hyperlinks)
        self.assertEqual(len(result["drill_pages"]), 1)
        self.assertEqual(len(result["bookmarks"]), 1)
        self.assertEqual(len(result["cross_report"]), 1)

    def test_no_params_uses_source_column(self):
        hyperlinks = [{
            "target_report": "DetailPage",
            "parameters": {},
            "source_column": "Region",
            "action": "drillthrough",
        }]
        result = self.converter.convert_hyperlinks(hyperlinks)
        page = result["drill_pages"][0]
        self.assertEqual(len(page["filters"]), 1)
        self.assertEqual(page["filters"][0]["column"], "Region")

    def test_convert_subreports(self):
        subreports = [
            {"name": "SubReport1", "parameters": {"dept": "Finance"}, "data_set": "DeptData"},
            {"name": "SubReport2", "parameters": {}, "data_set": "Sales"},
        ]
        result = self.converter.convert_subreports(subreports)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "SubReport1")
        self.assertEqual(result[0]["type"], "drillThrough")
        self.assertEqual(len(result[0]["filters"]), 1)

    def test_is_cross_report(self):
        self.assertTrue(DrillThroughConverter._is_cross_report("sub/rpt.rptdesign"))
        self.assertTrue(DrillThroughConverter._is_cross_report("report.rptdesign"))
        self.assertFalse(DrillThroughConverter._is_cross_report("DetailPage"))
        self.assertFalse(DrillThroughConverter._is_cross_report(""))

    def test_convert_params_row_ref(self):
        params = {"id": 'row["CustomerId"]'}
        result = DrillThroughConverter._convert_params(params)
        self.assertEqual(result["id"], "[CustomerId]")


class TestGenerateDrillPageJson(unittest.TestCase):

    def test_basic_page(self):
        config = {
            "displayName": "Detail View",
            "filters": [{"column": "Region"}],
        }
        page = generate_drill_page_json(config, page_index=3)
        self.assertEqual(page["name"], "DrillPage_3")
        self.assertEqual(page["displayName"], "Detail View")
        self.assertEqual(page["type"], 1)
        self.assertEqual(len(page["filters"]), 1)

    def test_empty_filters(self):
        config = {"displayName": "Empty", "filters": []}
        page = generate_drill_page_json(config)
        self.assertEqual(page["filters"], [])


if __name__ == "__main__":
    unittest.main()
