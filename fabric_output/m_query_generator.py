"""Power Query M generator — JDBC/ODA connections → M queries."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# JDBC URL pattern → M connector mapping
_JDBC_CONNECTORS: list[tuple[str, str]] = [
    ("oracle", "Oracle.Database"),
    ("postgresql", "PostgreSQL.Database"),
    ("sqlserver", "Sql.Database"),
    ("jtds:sqlserver", "Sql.Database"),
    ("mysql", "MySQL.Database"),
    ("db2", "DB2.Database"),
    ("teradata", "Teradata.Database"),
]


class MQueryGenerator:
    """Generates Power Query M expressions from BIRT data source connections."""

    def generate_from_connection(
        self,
        connection: dict[str, Any],
        query: str = "",
    ) -> str:
        """Generate M query from a BIRT data source connection.

        Args:
            connection: Data source entry from connections.json.
            query: SQL query from the dataset.

        Returns:
            Power Query M expression string.
        """
        driver_class = connection.get("odaDriverClass", connection.get("driverClass", ""))
        url = connection.get("odaURL", connection.get("url", ""))
        user = connection.get("odaUser", connection.get("user", ""))
        ext_id = connection.get("extension_id", "")

        # Determine connector type
        connector = self._resolve_connector(driver_class, url, ext_id)

        if connector == "Oracle.Database":
            return self._oracle_m_query(url, query)
        elif connector == "PostgreSQL.Database":
            return self._postgresql_m_query(url, query)
        elif connector == "Sql.Database":
            return self._sqlserver_m_query(url, query)
        elif connector == "MySQL.Database":
            return self._mysql_m_query(url, query)
        else:
            return self._odbc_m_query(url, query, driver_class)

    def generate_from_datasets(
        self,
        datasets: list[dict[str, Any]],
        connections: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate M queries for all datasets.

        Args:
            datasets: Dataset entries from datasets.json.
            connections: Connection entries from connections.json.

        Returns:
            List of {dataset_name, m_query, connection_name} dicts.
        """
        # Build connection lookup
        conn_map: dict[str, dict[str, Any]] = {}
        for conn in connections:
            conn_map[conn.get("name", "")] = conn

        results: list[dict[str, Any]] = []
        for ds in datasets:
            ds_name = ds.get("name", "")
            conn_name = ds.get("data_source", "")
            conn = conn_map.get(conn_name, {})
            query = ds.get("query", "")

            if conn:
                m_query = self.generate_from_connection(conn, query)
            elif query:
                # No connection info — generate native query placeholder
                m_query = self._native_query_placeholder(query)
            else:
                m_query = f'// No data source found for dataset: {ds_name}\nnull'

            results.append({
                "dataset_name": ds_name,
                "connection_name": conn_name,
                "m_query": m_query,
                "sql_query": query,
            })

        logger.info("Generated %d M queries from %d datasets", len(results), len(datasets))
        return results

    def _resolve_connector(self, driver_class: str, url: str, ext_id: str) -> str:
        """Resolve JDBC driver to M connector type."""
        search_str = f"{driver_class} {url} {ext_id}".lower()
        for pattern, connector in _JDBC_CONNECTORS:
            if pattern in search_str:
                return connector
        return "Odbc.DataSource"

    def _oracle_m_query(self, url: str, query: str) -> str:
        """Generate Oracle connector M query."""
        # Extract host:port/service from JDBC URL
        server = self._parse_jdbc_url(url, "oracle")
        safe_query = self._escape_m_string(query)

        if query:
            return (
                f'let\n'
                f'    Source = Oracle.Database("{server}"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n'
                f'    Query'
            )
        return (
            f'let\n'
            f'    Source = Oracle.Database("{server}")\n'
            f'in\n'
            f'    Source'
        )

    def _postgresql_m_query(self, url: str, query: str) -> str:
        """Generate PostgreSQL connector M query."""
        server = self._parse_jdbc_url(url, "postgresql")
        safe_query = self._escape_m_string(query)

        parts = server.split("/", 1)
        host = parts[0]
        db = parts[1] if len(parts) > 1 else "postgres"

        if query:
            return (
                f'let\n'
                f'    Source = PostgreSQL.Database("{host}", "{db}"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n'
                f'    Query'
            )
        return (
            f'let\n'
            f'    Source = PostgreSQL.Database("{host}", "{db}")\n'
            f'in\n'
            f'    Source'
        )

    def _sqlserver_m_query(self, url: str, query: str) -> str:
        """Generate SQL Server connector M query."""
        server = self._parse_jdbc_url(url, "sqlserver")
        safe_query = self._escape_m_string(query)

        if query:
            return (
                f'let\n'
                f'    Source = Sql.Database("{server}"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n'
                f'    Query'
            )
        return (
            f'let\n'
            f'    Source = Sql.Database("{server}")\n'
            f'in\n'
            f'    Source'
        )

    def _mysql_m_query(self, url: str, query: str) -> str:
        """Generate MySQL connector M query."""
        server = self._parse_jdbc_url(url, "mysql")
        safe_query = self._escape_m_string(query)

        if query:
            return (
                f'let\n'
                f'    Source = MySQL.Database("{server}"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n'
                f'    Query'
            )
        return (
            f'let\n'
            f'    Source = MySQL.Database("{server}")\n'
            f'in\n'
            f'    Source'
        )

    def _odbc_m_query(self, url: str, query: str, driver: str) -> str:
        """Generate generic ODBC M query."""
        safe_query = self._escape_m_string(query)

        if query:
            return (
                f'let\n'
                f'    Source = Odbc.DataSource("DRIVER={{{driver}}};SERVER={url}"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n'
                f'    Query'
            )
        return (
            f'let\n'
            f'    Source = Odbc.DataSource("DRIVER={{{driver}}};SERVER={url}")\n'
            f'in\n'
            f'    Source'
        )

    def _native_query_placeholder(self, query: str) -> str:
        """Generate placeholder M query when no connection info available."""
        safe_query = self._escape_m_string(query)
        return (
            f'let\n'
            f'    // TODO: Configure data source connection\n'
            f'    Source = /* DataSource */,\n'
            f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
            f'in\n'
            f'    Query'
        )

    @staticmethod
    def _parse_jdbc_url(url: str, db_type: str) -> str:
        """Extract server/host info from JDBC URL."""
        # jdbc:oracle:thin:@host:port:sid or jdbc:oracle:thin:@//host:port/service
        # jdbc:postgresql://host:port/database
        # jdbc:sqlserver://host:port;databaseName=db
        match = re.search(r"//([^;?\s]+)", url)
        if match:
            return match.group(1)

        # Oracle thin format
        match = re.search(r"@([^;\s]+)", url)
        if match:
            return match.group(1)

        return url

    @staticmethod
    def _escape_m_string(s: str) -> str:
        """Escape a string for use in Power Query M."""
        return s.replace('"', '""').replace("\n", " ").replace("\r", "").strip()
