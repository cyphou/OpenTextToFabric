"""Tests for opentext_extract.ihub_client."""

import json
import unittest
from unittest.mock import patch, MagicMock

from opentext_extract.ihub_client import IHubClient, IHubError


class TestIHubClient(unittest.TestCase):

    def setUp(self):
        self.client = IHubClient(
            base_url="https://ihub.example.com",
            volume="Default Volume",
            username="admin",
            password="pass",
        )

    @patch("opentext_extract.ihub_client.urllib.request.urlopen")
    def test_authenticate(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({"authId": "abc123"}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        token = self.client.authenticate()
        self.assertEqual(token, "abc123")
        self.assertEqual(self.client._auth_token, "abc123")

    @patch("opentext_extract.ihub_client.urllib.request.urlopen")
    def test_auth_failure(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        with self.assertRaises(IHubError):
            self.client.authenticate()

    @patch("opentext_extract.ihub_client.urllib.request.urlopen")
    def test_list_files(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({
            "items": [
                {"name": "report1.rptdesign", "path": "/Reports/report1.rptdesign"},
                {"name": "report2.rptdesign", "path": "/Reports/report2.rptdesign"},
            ]
        }).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        self.client._auth_token = "tok"
        files = self.client.list_files("/Reports", file_type="rptdesign")
        self.assertEqual(len(files), 2)

    @patch("opentext_extract.ihub_client.urllib.request.urlopen")
    def test_get_data_sources(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({
            "dataSources": [{"name": "OracleDS"}]
        }).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        self.client._auth_token = "tok"
        sources = self.client.get_data_sources()
        self.assertEqual(len(sources), 1)

    @patch("opentext_extract.ihub_client.urllib.request.urlopen")
    def test_get_schedules(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({
            "schedules": [{"name": "Daily", "cron": "0 0 * * *"}]
        }).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        self.client._auth_token = "tok"
        schedules = self.client.get_schedules()
        self.assertEqual(len(schedules), 1)

    @patch("opentext_extract.ihub_client.urllib.request.urlopen")
    def test_get_report_parameters(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({
            "parameters": [
                {"name": "startDate", "dataType": "date"},
                {"name": "region", "dataType": "string"},
            ]
        }).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        self.client._auth_token = "tok"
        params = self.client.get_report_parameters("/Reports/sales.rptdesign")
        self.assertEqual(len(params), 2)

    @patch("opentext_extract.ihub_client.urllib.request.urlopen")
    def test_http_error(self, mock_urlopen):
        import urllib.error
        err = urllib.error.HTTPError(
            "http://x", 500, "Server Error", {}, MagicMock()
        )
        err.read = lambda: b"internal error"
        mock_urlopen.side_effect = err

        self.client._auth_token = "tok"
        with self.assertRaises(IHubError):
            self.client.list_files("/")

    @patch("opentext_extract.ihub_client.urllib.request.urlopen")
    def test_download_report(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b"<?xml version='1.0'?><report></report>"
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            self.client._auth_token = "tok"
            out = self.client.download_report(
                "/Reports/test.rptdesign",
                os.path.join(tmpdir, "test.rptdesign"),
            )
            self.assertTrue(os.path.exists(out))

    @patch("opentext_extract.ihub_client.urllib.request.urlopen")
    def test_discover_reports(self, mock_urlopen):
        # First call: list_files
        resp1 = MagicMock()
        resp1.read.return_value = json.dumps({
            "items": [{"name": "r1.rptdesign", "path": "/R/r1.rptdesign"}]
        }).encode()
        resp1.__enter__ = lambda s: s
        resp1.__exit__ = MagicMock(return_value=False)

        # Second call: get_report_parameters
        resp2 = MagicMock()
        resp2.read.return_value = json.dumps({"parameters": []}).encode()
        resp2.__enter__ = lambda s: s
        resp2.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [resp1, resp2]

        self.client._auth_token = "tok"
        reports = self.client.discover_reports("/R")
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["name"], "r1.rptdesign")


if __name__ == "__main__":
    unittest.main()
