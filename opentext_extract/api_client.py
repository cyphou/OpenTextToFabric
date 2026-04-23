"""Base REST API client for OpenText servers.

Handles authentication, pagination, rate limiting, and retry logic.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from http.client import HTTPResponse
from typing import Any

logger = logging.getLogger(__name__)

# Default retry-after header value in seconds
_DEFAULT_RETRY_DELAY = 2.0
_MAX_RETRIES = 3


class APIError(Exception):
    """Raised when an API request fails."""

    def __init__(self, message: str, status_code: int = 0, response_body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class APIClient:
    """Base REST API client with auth, pagination, rate-limiting, and retries.

    Uses only stdlib (urllib) — no external dependencies.
    """

    def __init__(
        self,
        base_url: str,
        username: str = "",
        password: str = "",
        auth_type: str = "basic",
        timeout: int = 30,
        max_retries: int = _MAX_RETRIES,
        retry_delay: float = _DEFAULT_RETRY_DELAY,
        page_size: int = 100,
        verify_ssl: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.auth_type = auth_type
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.page_size = page_size
        self.verify_ssl = verify_ssl

        self._token: str = ""
        self._session_headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # ── Authentication ──────────────────────────────────────────

    def authenticate(self) -> str:
        """Authenticate and obtain session token. Returns token string."""
        raise NotImplementedError("Subclasses must implement authenticate()")

    @property
    def is_authenticated(self) -> bool:
        return bool(self._token)

    # ── HTTP Methods ────────────────────────────────────────────

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """HTTP GET with retry and rate-limit handling."""
        url = self._build_url(path, params)
        return self._request("GET", url)

    def post(self, path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """HTTP POST with retry and rate-limit handling."""
        url = self._build_url(path)
        body = json.dumps(data).encode("utf-8") if data else None
        return self._request("POST", url, body=body)

    def get_binary(self, path: str) -> bytes:
        """Download binary content (documents)."""
        url = self._build_url(path)
        return self._request_binary("GET", url)

    # ── Pagination ──────────────────────────────────────────────

    def get_paginated(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        results_key: str = "results",
        page_param: str = "page",
        limit_param: str = "limit",
    ) -> list[dict[str, Any]]:
        """Fetch all pages of a paginated endpoint."""
        all_results: list[dict[str, Any]] = []
        page = 1
        params = dict(params) if params else {}
        params[limit_param] = self.page_size

        while True:
            params[page_param] = page
            response = self.get(path, params)

            results = response.get(results_key, [])
            if not results:
                break

            all_results.extend(results)
            logger.debug("Page %d: fetched %d items (total so far: %d)", page, len(results), len(all_results))

            # Check if there are more pages
            total = response.get("total_count", response.get("total", 0))
            if total and len(all_results) >= total:
                break
            if len(results) < self.page_size:
                break

            page += 1

        return all_results

    # ── Internal ────────────────────────────────────────────────

    def _build_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        """Build full URL from path and optional query parameters."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"
        return url

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers."""
        headers = dict(self._session_headers)
        if self._token:
            headers["OTCSTICKET"] = self._token  # Content Server
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _request(self, method: str, url: str, body: bytes | None = None) -> dict[str, Any]:
        """Execute HTTP request with retry logic."""
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                headers = self._get_auth_headers()
                req = urllib.request.Request(url, data=body, headers=headers, method=method)

                context = None
                if not self.verify_ssl:
                    import ssl
                    context = ssl.create_default_context()
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE

                with urllib.request.urlopen(req, timeout=self.timeout, context=context) as resp:
                    resp: HTTPResponse
                    data = resp.read().decode("utf-8")
                    if not data:
                        return {}
                    return json.loads(data)

            except urllib.error.HTTPError as e:
                if e.code == 429:
                    # Rate limited — respect Retry-After header
                    retry_after = float(e.headers.get("Retry-After", self.retry_delay))
                    logger.warning("Rate limited (429). Retry after %.1fs (attempt %d/%d)", retry_after, attempt, self.max_retries)
                    time.sleep(retry_after)
                    last_error = e
                    continue
                elif e.code >= 500:
                    logger.warning("Server error %d on %s (attempt %d/%d)", e.code, url, attempt, self.max_retries)
                    time.sleep(self.retry_delay * attempt)
                    last_error = e
                    continue
                else:
                    body_text = ""
                    try:
                        body_text = e.read().decode("utf-8", errors="replace")
                    except Exception:
                        pass
                    raise APIError(f"HTTP {e.code}: {e.reason}", status_code=e.code, response_body=body_text) from e

            except urllib.error.URLError as e:
                logger.warning("Connection error: %s (attempt %d/%d)", e.reason, attempt, self.max_retries)
                time.sleep(self.retry_delay * attempt)
                last_error = e
                continue

        raise APIError(f"Request failed after {self.max_retries} retries: {last_error}") from last_error

    def _request_binary(self, method: str, url: str) -> bytes:
        """Execute HTTP request returning raw bytes."""
        headers = self._get_auth_headers()
        headers.pop("Accept", None)
        req = urllib.request.Request(url, headers=headers, method=method)

        context = None
        if not self.verify_ssl:
            import ssl
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=context) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            raise APIError(f"Binary download failed: HTTP {e.code}", status_code=e.code) from e
