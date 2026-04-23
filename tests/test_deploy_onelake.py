"""Tests for deploy.onelake_client — OneLakeClient."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from deploy.onelake_client import OneLakeClient, OneLakeError


class MockTokenProvider:
    def get_token(self):
        return "test-token"


class TestOneLakeClient(unittest.TestCase):

    def setUp(self):
        self.client = OneLakeClient(MockTokenProvider())

    @patch("deploy.onelake_client.urllib.request.urlopen")
    def test_create_directory(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b""
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        self.client.create_directory("ws1", "lh1", "Tables/mytable")
        self.assertTrue(mock_urlopen.called)

    @patch("deploy.onelake_client.urllib.request.urlopen")
    def test_upload_small_file(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b""
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"hello world")
            f.flush()
            temp_path = f.name

        try:
            self.client.upload_file("ws1", "lh1", "data/test.txt", temp_path)
            # 3 calls: create file, append data, flush
            self.assertEqual(mock_urlopen.call_count, 3)
        finally:
            os.unlink(temp_path)

    @patch("deploy.onelake_client.urllib.request.urlopen")
    def test_upload_directory(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b""
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 2 files
            (Path(tmpdir) / "file1.txt").write_text("hello")
            sub = Path(tmpdir) / "sub"
            sub.mkdir()
            (sub / "file2.txt").write_text("world")

            count = self.client.upload_directory("ws1", "lh1", "Tables", tmpdir)
            self.assertEqual(count, 2)

    @patch("deploy.onelake_client.urllib.request.urlopen")
    def test_error_handling(self, mock_urlopen):
        import urllib.error
        err = urllib.error.HTTPError("http://x", 403, "Forbidden", {}, MagicMock())
        err.read = lambda: b"access denied"
        mock_urlopen.side_effect = err

        with self.assertRaises(OneLakeError):
            self.client.create_directory("ws1", "lh1", "Tables")


if __name__ == "__main__":
    unittest.main()
