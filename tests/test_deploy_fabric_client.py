"""Tests for deploy.fabric_client — FabricClient."""

import json
import unittest
from unittest.mock import patch, MagicMock

from deploy.fabric_client import FabricClient, FabricAPIError


class MockTokenProvider:
    def get_token(self):
        return "test-token"


class TestFabricClient(unittest.TestCase):

    def setUp(self):
        self.client = FabricClient(MockTokenProvider())

    @patch("deploy.fabric_client.urllib.request.urlopen")
    def test_list_workspaces(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({
            "value": [{"id": "ws1", "displayName": "Test"}]
        }).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = self.client.list_workspaces()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "ws1")

    @patch("deploy.fabric_client.urllib.request.urlopen")
    def test_get_workspace(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({"id": "ws1", "displayName": "WS"}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = self.client.get_workspace("ws1")
        self.assertEqual(result["displayName"], "WS")

    @patch("deploy.fabric_client.urllib.request.urlopen")
    def test_create_workspace(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({"id": "new-ws"}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = self.client.create_workspace("NewWS", capacity_id="cap1")
        self.assertEqual(result["id"], "new-ws")

    @patch("deploy.fabric_client.urllib.request.urlopen")
    def test_create_item(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({"id": "item1"}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = self.client.create_item("ws1", "MyItem", "Lakehouse")
        self.assertEqual(result["id"], "item1")

    @patch("deploy.fabric_client.urllib.request.urlopen")
    def test_api_error(self, mock_urlopen):
        import urllib.error
        err = urllib.error.HTTPError("http://x", 404, "Not Found", {}, MagicMock())
        err.read = lambda: b"not found"
        mock_urlopen.side_effect = err

        with self.assertRaises(FabricAPIError):
            self.client.get_workspace("nonexistent")

    @patch("deploy.fabric_client.urllib.request.urlopen")
    def test_throttled_429(self, mock_urlopen):
        import urllib.error
        headers = MagicMock()
        headers.get.return_value = "30"
        err = urllib.error.HTTPError("http://x", 429, "Too Many", headers, MagicMock())
        err.read = lambda: b"throttled"
        err.headers = headers
        mock_urlopen.side_effect = err

        with self.assertRaises(FabricAPIError) as ctx:
            self.client.list_workspaces()
        self.assertEqual(ctx.exception.status, 429)

    @patch("deploy.fabric_client.urllib.request.urlopen")
    def test_list_items_with_type(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({"value": []}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = self.client.list_items("ws1", item_type="Lakehouse")
        self.assertEqual(result, [])

    @patch("deploy.fabric_client.urllib.request.urlopen")
    def test_delete_item(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b""
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        self.client.delete_item("ws1", "item1")  # should not raise


if __name__ == "__main__":
    unittest.main()
