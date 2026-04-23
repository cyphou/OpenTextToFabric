"""Tests for deploy.auth — TokenProvider."""

import unittest
from unittest.mock import patch, MagicMock

from deploy.auth import TokenProvider, AuthError


class TestTokenProvider(unittest.TestCase):
    """Tests for TokenProvider."""

    def test_init_service_principal(self):
        tp = TokenProvider("tenant", "client", "secret")
        self.assertEqual(tp.tenant_id, "tenant")
        self.assertEqual(tp.client_id, "client")
        self.assertEqual(tp.client_secret, "secret")
        self.assertFalse(tp.use_managed_identity)

    def test_init_managed_identity(self):
        tp = TokenProvider(use_managed_identity=True)
        self.assertTrue(tp.use_managed_identity)

    @patch("deploy.auth.urllib.request.urlopen")
    def test_get_token_service_principal(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b'{"access_token": "tok123", "expires_in": 3600}'
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        tp = TokenProvider("t", "c", "s")
        token = tp.get_token()
        self.assertEqual(token, "tok123")

    @patch("deploy.auth.urllib.request.urlopen")
    def test_token_caching(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b'{"access_token": "cached", "expires_in": 3600}'
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        tp = TokenProvider("t", "c", "s")
        tp.get_token()
        tp.get_token()  # should use cache
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("deploy.auth.urllib.request.urlopen")
    def test_managed_identity_error(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("no IMDS")

        tp = TokenProvider(use_managed_identity=True)
        with self.assertRaises(AuthError):
            tp.get_token()

    def test_no_credentials_no_azure_identity(self):
        tp = TokenProvider()
        # When azure-identity is installed, DefaultAzureCredential may raise
        # its own error instead of our AuthError
        with self.assertRaises(Exception):
            tp.get_token()


class TestAuthEdgeCases(unittest.TestCase):
    @patch("deploy.auth.urllib.request.urlopen")
    def test_http_error_raises_auth_error(self, mock_urlopen):
        import urllib.error
        err = urllib.error.HTTPError(
            "http://x", 401, "Unauthorized", {}, MagicMock()
        )
        err.read = lambda: b"bad creds"
        mock_urlopen.side_effect = err

        tp = TokenProvider("t", "c", "s")
        with self.assertRaises(AuthError):
            tp.get_token()


if __name__ == "__main__":
    unittest.main()
