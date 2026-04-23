"""OpenText iHub (Information Hub) REST API client.

Connects to iHub to discover and extract BIRT reports, data sources,
and schedule configurations via the iHub REST API.
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from typing import Any

logger = logging.getLogger(__name__)


class IHubError(Exception):
    """Raised on iHub API errors."""


class IHubClient:
    """Client for OpenText iHub (Information Hub) REST API.

    Supports:
    - Authentication (volume-based)
    - File/folder enumeration
    - Report download (.rptdesign)
    - Data source configuration extraction
    - Schedule listing
    """

    def __init__(
        self,
        base_url: str,
        volume: str = "Default Volume",
        username: str = "",
        password: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.volume = volume
        self.username = username
        self.password = password
        self._auth_token: str = ""

    def authenticate(self) -> str:
        """Authenticate to iHub and return auth token."""
        url = f"{self.base_url}/api/v2/login"
        body = {
            "username": self.username,
            "password": self.password,
            "volume": self.volume,
        }
        result = self._request("POST", url, body=body, auth=False)
        self._auth_token = result.get("authId", "")
        if not self._auth_token:
            raise IHubError("Authentication failed — no authId returned")
        logger.info("Authenticated to iHub as %s", self.username)
        return self._auth_token

    def list_files(
        self,
        folder_path: str = "/",
        file_type: str = "",
        recursive: bool = False,
    ) -> list[dict[str, Any]]:
        """List files in an iHub folder.

        Args:
            folder_path: iHub folder path (e.g. "/Reports/Finance").
            file_type: Filter by type (e.g. "rptdesign", "rptdocument").
            recursive: If True, list all files recursively.

        Returns:
            List of file metadata dicts.
        """
        encoded_path = urllib.parse.quote(folder_path)
        url = f"{self.base_url}/api/v2/files{encoded_path}"
        params: dict[str, str] = {}
        if file_type:
            params["type"] = file_type
        if recursive:
            params["recursive"] = "true"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        result = self._request("GET", url)
        items = result.get("items", result.get("files", []))

        if isinstance(items, list):
            logger.info("Listed %d items in %s", len(items), folder_path)
            return items
        return []

    def download_report(
        self,
        file_path: str,
        output_path: str,
    ) -> str:
        """Download a .rptdesign file from iHub.

        Args:
            file_path: iHub path to the report file.
            output_path: Local path to save the file.

        Returns:
            Path to the downloaded file.
        """
        encoded_path = urllib.parse.quote(file_path)
        url = f"{self.base_url}/api/v2/files{encoded_path}/content"

        data = self._request_raw("GET", url)
        from pathlib import Path
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)

        logger.info("Downloaded %s → %s (%d bytes)", file_path, output_path, len(data))
        return output_path

    def get_data_sources(self) -> list[dict[str, Any]]:
        """List configured data sources on iHub."""
        url = f"{self.base_url}/api/v2/datasources"
        result = self._request("GET", url)
        return result.get("items", result.get("dataSources", []))

    def get_schedules(self) -> list[dict[str, Any]]:
        """List scheduled jobs on iHub."""
        url = f"{self.base_url}/api/v2/schedules"
        result = self._request("GET", url)
        return result.get("items", result.get("schedules", []))

    def get_report_parameters(self, file_path: str) -> list[dict[str, Any]]:
        """Get report parameters for a .rptdesign file."""
        encoded_path = urllib.parse.quote(file_path)
        url = f"{self.base_url}/api/v2/files{encoded_path}/parameters"
        result = self._request("GET", url)
        return result.get("parameters", [])

    def discover_reports(
        self,
        root_path: str = "/",
    ) -> list[dict[str, Any]]:
        """Discover all BIRT reports under a folder, recursively.

        Returns a list of report metadata including parameters and data sources.
        """
        files = self.list_files(root_path, file_type="rptdesign", recursive=True)
        reports: list[dict[str, Any]] = []

        for f in files:
            path = f.get("path", f.get("name", ""))
            report_meta: dict[str, Any] = {
                "name": f.get("name", ""),
                "path": path,
                "size": f.get("size", 0),
                "modified": f.get("lastModified", ""),
                "type": "rptdesign",
            }

            # Try to get parameters (non-critical)
            try:
                params = self.get_report_parameters(path)
                report_meta["parameters"] = params
            except Exception:
                report_meta["parameters"] = []

            reports.append(report_meta)

        logger.info("Discovered %d reports under %s", len(reports), root_path)
        return reports

    def _request(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None = None,
        *,
        auth: bool = True,
    ) -> dict[str, Any]:
        """Make an authenticated JSON API request."""
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")

        if auth and self._auth_token:
            req.add_header("AuthId", self._auth_token)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            body_text = e.read().decode(errors="replace")
            raise IHubError(f"iHub {method} {e.code}: {body_text}") from e

    def _request_raw(self, method: str, url: str) -> bytes:
        """Make an authenticated raw (binary) API request."""
        req = urllib.request.Request(url, method=method)
        if self._auth_token:
            req.add_header("AuthId", self._auth_token)

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            body_text = e.read().decode(errors="replace")
            raise IHubError(f"iHub {method} {e.code}: {body_text}") from e
