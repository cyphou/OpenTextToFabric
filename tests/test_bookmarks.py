"""Tests for PBIP generator bookmark support."""

import json
import tempfile
import unittest

from report_converter.pbip_generator import PBIPGenerator


class TestBookmarkInit(unittest.TestCase):
    def test_empty_bookmarks(self):
        gen = PBIPGenerator()
        self.assertEqual(gen._bookmarks, [])


class TestAddBookmark(unittest.TestCase):
    def test_add_simple_bookmark(self):
        gen = PBIPGenerator()
        bm = gen.add_bookmark("BM1", display_name="My Bookmark")
        self.assertEqual(bm["name"], "BM1")
        self.assertEqual(bm["displayName"], "My Bookmark")
        self.assertIn("explorationState", bm)

    def test_add_bookmark_default_display_name(self):
        gen = PBIPGenerator()
        bm = gen.add_bookmark("BM2")
        self.assertEqual(bm["displayName"], "BM2")

    def test_add_bookmark_with_page_id(self):
        gen = PBIPGenerator()
        bm = gen.add_bookmark("BM3", page_id="page_1")
        self.assertEqual(bm["explorationState"]["activeSection"], "page_1")

    def test_add_bookmark_with_visual_states(self):
        gen = PBIPGenerator()
        bm = gen.add_bookmark(
            "BM4",
            page_id="p1",
            visual_states={"chart1": True, "table1": False},
        )
        sections = bm["explorationState"]["sections"]
        self.assertIn("p1", sections)
        containers = sections["p1"]["visualContainers"]
        self.assertEqual(containers["chart1"]["visibility"], 0)  # visible
        self.assertEqual(containers["table1"]["visibility"], 1)  # hidden

    def test_multiple_bookmarks(self):
        gen = PBIPGenerator()
        gen.add_bookmark("BM1")
        gen.add_bookmark("BM2")
        gen.add_bookmark("BM3")
        self.assertEqual(len(gen._bookmarks), 3)


class TestBookmarkInGenerate(unittest.TestCase):
    def test_bookmarks_json_generated(self):
        gen = PBIPGenerator()
        gen.add_bookmark("BM1", display_name="Test Bookmark")

        with tempfile.TemporaryDirectory() as td:
            visuals = [
                {"type": "chart", "title": "Sales", "x": 0, "y": 0, "width": 400, "height": 300},
            ]
            files = gen.generate(visuals, td)
            self.assertIn("bookmarks.json", files)
            bm_path = files["bookmarks.json"]
            self.assertTrue(bm_path.exists())

            with open(bm_path) as f:
                data = json.load(f)
            self.assertIn("bookmarks", data)
            self.assertEqual(len(data["bookmarks"]), 1)
            self.assertEqual(data["bookmarks"][0]["name"], "BM1")

    def test_no_bookmarks_no_file(self):
        gen = PBIPGenerator()
        with tempfile.TemporaryDirectory() as td:
            visuals = [
                {"type": "chart", "title": "X", "x": 0, "y": 0, "width": 400, "height": 300},
            ]
            files = gen.generate(visuals, td)
            self.assertNotIn("bookmarks.json", files)


class TestBookmarkReportId(unittest.TestCase):
    def test_bookmark_has_report_id(self):
        gen = PBIPGenerator()
        bm = gen.add_bookmark("BM1")
        self.assertEqual(bm["reportId"], gen._report_id)


if __name__ == "__main__":
    unittest.main()
