"""Refresh scheduling — extract BIRT schedules and generate PBI refresh configs.

Maps BIRT scheduled report execution to Power BI dataset refresh schedules
and generates refresh configuration JSON for the PBI REST API.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# BIRT cron-like frequency → PBI refresh schedule
_FREQUENCY_MAP: dict[str, dict[str, Any]] = {
    "daily": {"frequency": "Daily", "interval": 1, "times": ["06:00"]},
    "hourly": {"frequency": "Daily", "interval": 1, "times": [f"{h:02d}:00" for h in range(6, 22)]},
    "weekly": {"frequency": "Weekly", "interval": 1, "days": ["Monday"], "times": ["06:00"]},
    "monthly": {"frequency": "Monthly", "interval": 1, "days": [1], "times": ["06:00"]},
    "biweekly": {"frequency": "Weekly", "interval": 2, "days": ["Monday"], "times": ["06:00"]},
    "quarterly": {"frequency": "Monthly", "interval": 3, "days": [1], "times": ["06:00"]},
}


class RefreshScheduleGenerator:
    """Generate Power BI refresh schedules from BIRT/iHub schedules."""

    def __init__(self):
        self._schedules: list[dict[str, Any]] = []

    def from_birt_schedule(self, schedule: dict[str, Any]) -> dict[str, Any]:
        """Convert a BIRT schedule definition to PBI refresh config.

        Args:
            schedule: Dict with keys like 'frequency', 'time', 'timezone',
                     'days', 'enabled'.

        Returns:
            PBI refresh schedule configuration.
        """
        freq = schedule.get("frequency", "daily").lower()
        base = _FREQUENCY_MAP.get(freq, _FREQUENCY_MAP["daily"]).copy()

        # Override times if specified
        if "time" in schedule:
            base["times"] = [schedule["time"]]
        if "times" in schedule:
            base["times"] = schedule["times"]

        # Override days if specified
        if "days" in schedule and freq in ("weekly", "monthly"):
            base["days"] = schedule["days"]

        config = {
            "enabled": schedule.get("enabled", True),
            "notifyOption": schedule.get("notify", "MailOnFailure"),
            "schedule": base,
            "localTimeZoneId": schedule.get("timezone", "UTC"),
        }

        self._schedules.append({
            "source": schedule,
            "pbi_config": config,
        })

        return config

    def from_ihub_schedule(self, ihub_schedule: dict[str, Any]) -> dict[str, Any]:
        """Convert an iHub scheduled job to PBI refresh config."""
        # Map iHub recurrence patterns
        recurrence = ihub_schedule.get("recurrenceType", "DAILY")
        freq_map = {
            "DAILY": "daily",
            "WEEKLY": "weekly",
            "MONTHLY": "monthly",
            "HOURLY": "hourly",
        }
        schedule = {
            "frequency": freq_map.get(recurrence, "daily"),
            "time": ihub_schedule.get("startTime", "06:00"),
            "timezone": ihub_schedule.get("timeZone", "UTC"),
            "enabled": ihub_schedule.get("active", True),
        }
        if recurrence == "WEEKLY":
            schedule["days"] = ihub_schedule.get("daysOfWeek", ["Monday"])

        return self.from_birt_schedule(schedule)

    def from_cron(self, cron_expression: str) -> dict[str, Any]:
        """Parse a cron expression and generate a PBI refresh schedule.

        Supports standard 5-field cron: minute hour day month weekday
        """
        parts = cron_expression.strip().split()
        if len(parts) < 5:
            return self.from_birt_schedule({"frequency": "daily"})

        minute, hour, day, month, weekday = parts[:5]

        schedule: dict[str, Any] = {"frequency": "daily"}

        if hour != "*" and minute != "*":
            schedule["time"] = f"{int(hour):02d}:{int(minute):02d}"

        if weekday != "*":
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            days = []
            for d in weekday.split(","):
                idx = int(d) % 7
                days.append(day_names[idx])
            schedule["frequency"] = "weekly"
            schedule["days"] = days

        if day != "*" and day != "1":
            schedule["frequency"] = "monthly"
            schedule["days"] = [int(d) for d in day.split(",")]

        return self.from_birt_schedule(schedule)

    def generate_all(self, schedules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert a batch of schedules."""
        return [self.from_birt_schedule(s) for s in schedules]

    def summary(self) -> dict[str, Any]:
        return {
            "total_schedules": len(self._schedules),
            "enabled": sum(1 for s in self._schedules if s["pbi_config"].get("enabled")),
        }


class GatewayConfig:
    """Map on-premises data source connections to PBI gateway bindings.

    When BIRT reports connect to on-prem databases (Oracle, SQL Server, etc.),
    the generated PBI datasets need gateway bindings to reach the same sources.
    """

    def __init__(self):
        self._mappings: list[dict[str, Any]] = []

    def map_connection(
        self,
        connection: dict[str, Any],
        gateway_id: str = "",
        datasource_id: str = "",
    ) -> dict[str, Any]:
        """Map a BIRT data source connection to a gateway binding.

        Args:
            connection: BIRT connection dict (driver, url, user, etc.).
            gateway_id: PBI gateway cluster ID.
            datasource_id: PBI gateway datasource ID.

        Returns:
            Gateway binding configuration.
        """
        driver = connection.get("driver", "").lower()
        url = connection.get("url", "")

        # Infer gateway datasource type from JDBC driver
        ds_type = "Unknown"
        if "oracle" in driver:
            ds_type = "Oracle"
        elif "postgresql" in driver or "postgres" in driver:
            ds_type = "PostgreSql"
        elif "sqlserver" in driver or "jtds" in driver:
            ds_type = "Sql"
        elif "mysql" in driver:
            ds_type = "MySql"
        elif "db2" in driver:
            ds_type = "DB2"
        elif "teradata" in driver:
            ds_type = "Teradata"
        elif "sap" in driver:
            ds_type = "SapHana"

        # Parse server/database from JDBC URL
        server, database = self._parse_jdbc_url(url)

        binding = {
            "gatewayObjectId": gateway_id,
            "datasourceObjectIds": [datasource_id] if datasource_id else [],
            "datasourceType": ds_type,
            "connectionDetails": {
                "server": server,
                "database": database,
                "url": url,
            },
            "credential": {
                "credentialType": "Windows"
                if ds_type in ("Sql", "Oracle")
                else "Basic",
            },
            "source_connection": connection.get("name", ""),
        }

        self._mappings.append(binding)
        return binding

    def _parse_jdbc_url(self, url: str) -> tuple[str, str]:
        """Extract server and database from a JDBC URL."""
        server = ""
        database = ""

        if not url:
            return server, database

        # jdbc:oracle:thin:@host:port:sid
        if "oracle" in url.lower():
            parts = url.split("@")
            if len(parts) > 1:
                server = parts[-1].split("/")[0].split(":")[0]
                if "/" in parts[-1]:
                    database = parts[-1].split("/")[-1]
                elif ":" in parts[-1]:
                    segments = parts[-1].split(":")
                    if len(segments) >= 3:
                        database = segments[2]

        # jdbc:postgresql://host:port/database
        elif "postgresql" in url.lower() or "mysql" in url.lower():
            if "://" in url:
                rest = url.split("://", 1)[1]
                server = rest.split("/")[0].split(":")[0]
                if "/" in rest:
                    database = rest.split("/")[1].split("?")[0]

        # jdbc:sqlserver://host:port;databaseName=db
        elif "sqlserver" in url.lower():
            if "://" in url:
                rest = url.split("://", 1)[1]
                server = rest.split(";")[0].split(":")[0]
            if "databaseName=" in url:
                database = url.split("databaseName=")[1].split(";")[0]

        return server, database

    def map_all(self, connections: list[dict[str, Any]], gateway_id: str = "") -> list[dict[str, Any]]:
        """Map all connections to gateway bindings."""
        return [self.map_connection(c, gateway_id=gateway_id) for c in connections]

    def summary(self) -> dict[str, Any]:
        types = {}
        for m in self._mappings:
            t = m.get("datasourceType", "Unknown")
            types[t] = types.get(t, 0) + 1
        return {
            "total_mappings": len(self._mappings),
            "by_type": types,
        }
