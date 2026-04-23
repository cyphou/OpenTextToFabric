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

    # ── Bulk Migration ──────────────────────────────────────────

    def bulk_download_reports(
        self,
        root_path: str = "/",
        output_dir: str = "./downloads",
    ) -> list[dict[str, Any]]:
        """Download all BIRT reports under a folder recursively.

        Args:
            root_path: iHub root folder path.
            output_dir: Local directory to save reports.

        Returns:
            List of download results with path, status, and size.
        """
        from pathlib import Path
        reports = self.discover_reports(root_path)
        results: list[dict[str, Any]] = []
        out = Path(output_dir)

        for report in reports:
            ihub_path = report.get("path", "")
            name = report.get("name", "")
            if not ihub_path or not name:
                continue

            # Preserve folder structure under output_dir
            relative = ihub_path.lstrip("/")
            local_path = str(out / relative)

            result: dict[str, Any] = {
                "name": name,
                "ihub_path": ihub_path,
                "local_path": local_path,
                "status": "success",
                "size": 0,
                "error": "",
            }

            try:
                self.download_report(ihub_path, local_path)
                result["size"] = Path(local_path).stat().st_size
            except Exception as e:
                result["status"] = "failed"
                result["error"] = str(e)
                logger.warning("Failed to download %s: %s", ihub_path, e)

            results.append(result)

        success = sum(1 for r in results if r["status"] == "success")
        logger.info(
            "Bulk download: %d/%d reports downloaded to %s",
            success, len(results), output_dir,
        )
        return results

    def build_migration_inventory(
        self,
        root_path: str = "/",
    ) -> dict[str, Any]:
        """Scan entire iHub server and build a migration inventory.

        Returns:
            Inventory with report catalog, data sources, schedules,
            and migration readiness assessment.
        """
        reports = self.discover_reports(root_path)
        data_sources = self.get_data_sources()
        schedules = self.get_schedules()

        # Categorize reports by folder
        by_folder: dict[str, list[str]] = {}
        for r in reports:
            folder = "/".join(r.get("path", "/").split("/")[:-1]) or "/"
            by_folder.setdefault(folder, []).append(r.get("name", ""))

        # Report with parameters are more complex to migrate
        parameterized = [r for r in reports if r.get("parameters")]

        inventory: dict[str, Any] = {
            "total_reports": len(reports),
            "total_data_sources": len(data_sources),
            "total_schedules": len(schedules),
            "parameterized_reports": len(parameterized),
            "folders": {k: len(v) for k, v in by_folder.items()},
            "reports": reports,
            "data_sources": data_sources,
            "schedules": schedules,
            "complexity_breakdown": {
                "simple": sum(1 for r in reports if not r.get("parameters")),
                "parameterized": len(parameterized),
            },
        }

        logger.info(
            "Migration inventory: %d reports, %d data sources, %d schedules",
            len(reports), len(data_sources), len(schedules),
        )
        return inventory


class ScheduleConverter:
    """Converts iHub scheduled jobs to Power BI refresh configurations."""

    # iHub cron-like patterns → PBI refresh schedule
    FREQUENCY_MAP: dict[str, str] = {
        "daily": "Daily",
        "weekly": "Weekly",
        "monthly": "Monthly",
        "hourly": "Daily",  # PBI doesn't have hourly, use daily with multiple times
    }

    def convert_schedules(
        self,
        schedules: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert iHub schedules to PBI refresh schedule configs.

        Args:
            schedules: List of iHub schedule dicts.

        Returns:
            List of PBI refresh schedule configs.
        """
        configs: list[dict[str, Any]] = []

        for sched in schedules:
            config = self._convert_single(sched)
            if config:
                configs.append(config)

        logger.info("Converted %d/%d schedules to PBI refresh configs",
                     len(configs), len(schedules))
        return configs

    def _convert_single(self, schedule: dict[str, Any]) -> dict[str, Any]:
        """Convert a single iHub schedule to PBI refresh config."""
        name = schedule.get("name", "")
        cron = schedule.get("cron", schedule.get("schedule", ""))
        frequency = schedule.get("frequency", "")

        config: dict[str, Any] = {
            "name": name,
            "enabled": schedule.get("enabled", True),
            "frequency": self.FREQUENCY_MAP.get(frequency.lower(), "Daily"),
            "times": [],
            "days": [],
            "timezone": schedule.get("timezone", "UTC"),
        }

        # Parse cron expression if available
        if cron:
            parsed = self._parse_cron(cron)
            config["times"] = parsed.get("times", ["06:00"])
            config["days"] = parsed.get("days", [])
        else:
            config["times"] = [schedule.get("time", "06:00")]

        return config

    @staticmethod
    def _parse_cron(cron: str) -> dict[str, Any]:
        """Parse a cron expression to extract times and days.

        Handles standard 5-field cron: minute hour day month weekday
        """
        result: dict[str, Any] = {"times": [], "days": []}
        parts = cron.strip().split()
        if len(parts) < 5:
            return result

        minute, hour = parts[0], parts[1]

        # Parse hour/minute
        try:
            h = int(hour) if hour != "*" else 0
            m = int(minute) if minute != "*" else 0
            result["times"] = [f"{h:02d}:{m:02d}"]
        except ValueError:
            result["times"] = ["06:00"]

        # Parse weekday (0=Sun, 1=Mon, ... 6=Sat)
        weekday = parts[4]
        day_names = ["Sunday", "Monday", "Tuesday", "Wednesday",
                     "Thursday", "Friday", "Saturday"]
        if weekday != "*":
            try:
                for d in weekday.split(","):
                    idx = int(d.strip())
                    if 0 <= idx <= 6:
                        result["days"].append(day_names[idx])
            except ValueError:
                pass

        return result
