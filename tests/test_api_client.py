"""Tests for opentext_extract.api_client."""

import json
import unittest
from unittest.mock import patch, MagicMock
from opentext_extract.api_client import APIClient, APIError


class TestAPIClient(unittest.TestCase):
    """Tests for the base REST API client."""

    def setUp(self):
        self.client = APIClient(
            base_url="https://example.com/otcs/cs.exe",
            username="admin",
            password="pass",
            max_retries=2,
            retry_delay=0.01,
        )

    def test_init_strips_trailing_slash(self):
        c = APIClient(base_url="https://example.com/api/")
        self.assertEqual(c.base_url, "https://example.com/api")

    def test_build_url_no_params(self):
        url = self.client._build_url("/api/v2/nodes/100")
        self.assertEqual(url, "https://example.com/otcs/cs.exe/api/v2/nodes/100")

    def test_build_url_with_params(self):
        url = self.client._build_url("/api/v2/nodes", {"page": 1, "limit": 50})
        self.assertIn("page=1", url)
        self.assertIn("limit=50", url)

    def test_not_authenticated_initially(self):
        self.assertFalse(self.client.is_authenticated)

    def test_authenticated_after_token_set(self):
        self.client._token = "test-token"
        self.assertTrue(self.client.is_authenticated)

    def test_authenticate_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.client.authenticate()

    def test_get_auth_headers_with_token(self):
        self.client._token = "ticket123"
        headers = self.client._get_auth_headers()
        self.assertEqual(headers["OTCSTICKET"], "ticket123")
        self.assertIn("Bearer ticket123", headers["Authorization"])

    def test_get_auth_headers_without_token(self):
        headers = self.client._get_auth_headers()
        self.assertNotIn("OTCSTICKET", headers)

    @patch("urllib.request.urlopen")
    def test_get_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"results": [1, 2, 3]}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = self.client.get("/api/v2/nodes/100")
        self.assertEqual(result, {"results": [1, 2, 3]})

    @patch("urllib.request.urlopen")
    def test_get_empty_response(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = self.client.get("/api/v2/nodes/100")
        self.assertEqual(result, {})

    @patch("urllib.request.urlopen")
    def test_http_error_non_retryable(self, mock_urlopen):
        import urllib.error
        error = urllib.error.HTTPError(
            "https://example.com", 404, "Not Found", {}, MagicMock()
        )
        error.read = MagicMock(return_value=b"not found")
        mock_urlopen.side_effect = error

        with self.assertRaises(APIError) as ctx:
            self.client.get("/api/v2/nodes/999")
        self.assertEqual(ctx.exception.status_code, 404)

    @patch("urllib.request.urlopen")
    def test_http_429_retries(self, mock_urlopen):
        import urllib.error
        error = urllib.error.HTTPError(
            "https://example.com", 429, "Too Many Requests", {"Retry-After": "0"}, MagicMock()
        )
        mock_urlopen.side_effect = error

        with self.assertRaises(APIError) as ctx:
            self.client.get("/api/v2/nodes/100")
        self.assertIn("failed after", str(ctx.exception))
        self.assertEqual(mock_urlopen.call_count, 2)  # max_retries=2

    @patch("urllib.request.urlopen")
    def test_http_500_retries(self, mock_urlopen):
        import urllib.error
        error = urllib.error.HTTPError(
            "https://example.com", 500, "Server Error", {}, MagicMock()
        )
        mock_urlopen.side_effect = error

        with self.assertRaises(APIError):
            self.client.get("/api/v2/nodes/100")
        self.assertEqual(mock_urlopen.call_count, 2)


class TestAPIError(unittest.TestCase):
    def test_error_attributes(self):
        e = APIError("test error", status_code=403, response_body="forbidden")
        self.assertEqual(str(e), "test error")
        self.assertEqual(e.status_code, 403)
        self.assertEqual(e.response_body, "forbidden")


class TestPagination(unittest.TestCase):

    @patch("urllib.request.urlopen")
    def test_get_paginated_single_page(self, mock_urlopen):
        client = APIClient(base_url="https://example.com", page_size=10, max_retries=1)

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "results": [{"id": 1}, {"id": 2}],
            "total_count": 2,
        }).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        results = client.get_paginated("/api/v2/nodes/100/nodes")
        self.assertEqual(len(results), 2)

    @patch("urllib.request.urlopen")
    def test_get_paginated_empty(self, mock_urlopen):
        client = APIClient(base_url="https://example.com", page_size=10, max_retries=1)

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"results": []}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        results = client.get_paginated("/api/v2/nodes/100/nodes")
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
