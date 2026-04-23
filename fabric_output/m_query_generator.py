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
    # ── Sprint 31: Extended connectors ──
    ("mariadb", "MySQL.Database"),
    ("sap", "SapHana.Database"),
    ("hana", "SapHana.Database"),
    ("snowflake", "Snowflake.Databases"),
    ("bigquery", "GoogleBigQuery.Database"),
    ("redshift", "AmazonRedshift.Database"),
    ("mongodb", "MongoDB.Database"),
    ("cosmosdb", "DocumentDB.Contents"),
    ("cosmos", "DocumentDB.Contents"),
    ("elasticsearch", "Elasticsearch.Contents"),
    ("elastic", "Elasticsearch.Contents"),
    ("databricks", "Databricks.Catalogs"),
    ("spark", "SparkThrift.Database"),
    ("hive", "SparkThrift.Database"),
    ("azuresql", "Sql.Database"),
    ("synapse", "Sql.Database"),
    ("sqlite", "Sqlite.Database"),
    ("firebird", "Odbc.DataSource"),
    ("informix", "Odbc.DataSource"),
    ("sybase", "Sybase.Database"),
    ("h2", "Odbc.DataSource"),
    ("vertica", "Odbc.DataSource"),
    ("clickhouse", "Odbc.DataSource"),
    ("presto", "Odbc.DataSource"),
    ("trino", "Odbc.DataSource"),
    ("athena", "Odbc.DataSource"),
    ("csv", "Csv.Document"),
    ("excel", "Excel.Workbook"),
    ("json", "Json.Document"),
    ("xml", "Xml.Document"),
    ("sharepoint", "SharePoint.Contents"),
    ("odata", "OData.Feed"),
    ("rest", "Web.Contents"),
    ("http", "Web.Contents"),
    ("ftp", "File.Contents"),
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
        elif connector == "SapHana.Database":
            return self._sap_hana_m_query(url, query)
        elif connector == "Snowflake.Databases":
            return self._snowflake_m_query(url, query)
        elif connector == "GoogleBigQuery.Database":
            return self._bigquery_m_query(url, query)
        elif connector == "AmazonRedshift.Database":
            return self._redshift_m_query(url, query)
        elif connector == "MongoDB.Database":
            return self._mongodb_m_query(url, query)
        elif connector == "DocumentDB.Contents":
            return self._cosmosdb_m_query(url, query)
        elif connector == "Elasticsearch.Contents":
            return self._elasticsearch_m_query(url, query)
        elif connector == "Databricks.Catalogs":
            return self._databricks_m_query(url, query)
        elif connector == "SparkThrift.Database":
            return self._spark_m_query(url, query)
        elif connector == "Sqlite.Database":
            return self._sqlite_m_query(url, query)
        elif connector == "Sybase.Database":
            return self._sybase_m_query(url, query)
        elif connector == "DB2.Database":
            return self._db2_m_query(url, query)
        elif connector == "Teradata.Database":
            return self._teradata_m_query(url, query)
        elif connector == "Csv.Document":
            return self._csv_m_query(url, query)
        elif connector == "Excel.Workbook":
            return self._excel_m_query(url, query)
        elif connector == "Json.Document":
            return self._json_m_query(url, query)
        elif connector == "Xml.Document":
            return self._xml_m_query(url, query)
        elif connector == "SharePoint.Contents":
            return self._sharepoint_m_query(url, query)
        elif connector == "OData.Feed":
            return self._odata_m_query(url, query)
        elif connector == "Web.Contents":
            return self._web_m_query(url, query)
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

    # ── Sprint 31: New connector methods ──

    def _sap_hana_m_query(self, url: str, query: str) -> str:
        """Generate SAP HANA connector M query."""
        server = self._parse_jdbc_url(url, "sap")
        safe_query = self._escape_m_string(query)
        if query:
            return (
                f'let\n'
                f'    Source = SapHana.Database("{server}"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n    Query'
            )
        return f'let\n    Source = SapHana.Database("{server}")\nin\n    Source'

    def _snowflake_m_query(self, url: str, query: str) -> str:
        """Generate Snowflake connector M query."""
        server = self._parse_jdbc_url(url, "snowflake")
        parts = server.split("/", 1)
        host = parts[0]
        db = parts[1] if len(parts) > 1 else "WAREHOUSE"
        safe_query = self._escape_m_string(query)
        if query:
            return (
                f'let\n'
                f'    Source = Snowflake.Databases("{host}", "{db}"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n    Query'
            )
        return f'let\n    Source = Snowflake.Databases("{host}", "{db}")\nin\n    Source'

    def _bigquery_m_query(self, url: str, query: str) -> str:
        """Generate Google BigQuery connector M query."""
        project = self._parse_jdbc_url(url, "bigquery") or "my-project"
        safe_query = self._escape_m_string(query)
        if query:
            return (
                f'let\n'
                f'    Source = GoogleBigQuery.Database([BillingProject="{project}"]),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n    Query'
            )
        return f'let\n    Source = GoogleBigQuery.Database([BillingProject="{project}"])\nin\n    Source'

    def _redshift_m_query(self, url: str, query: str) -> str:
        """Generate Amazon Redshift connector M query."""
        server = self._parse_jdbc_url(url, "redshift")
        parts = server.split("/", 1)
        host = parts[0]
        db = parts[1] if len(parts) > 1 else "dev"
        safe_query = self._escape_m_string(query)
        if query:
            return (
                f'let\n'
                f'    Source = AmazonRedshift.Database("{host}", "{db}"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n    Query'
            )
        return f'let\n    Source = AmazonRedshift.Database("{host}", "{db}")\nin\n    Source'

    def _mongodb_m_query(self, url: str, query: str) -> str:
        """Generate MongoDB connector M query."""
        server = self._parse_jdbc_url(url, "mongodb")
        return (
            f'let\n'
            f'    Source = MongoDB.Database("{server}")\n'
            f'in\n    Source'
        )

    def _cosmosdb_m_query(self, url: str, query: str) -> str:
        """Generate Azure Cosmos DB connector M query."""
        server = self._parse_jdbc_url(url, "cosmosdb") or url
        return (
            f'let\n'
            f'    Source = DocumentDB.Contents("{server}")\n'
            f'in\n    Source'
        )

    def _elasticsearch_m_query(self, url: str, query: str) -> str:
        """Generate Elasticsearch connector M query."""
        server = self._parse_jdbc_url(url, "elasticsearch")
        return (
            f'let\n'
            f'    Source = Elasticsearch.Contents("{server}")\n'
            f'in\n    Source'
        )

    def _databricks_m_query(self, url: str, query: str) -> str:
        """Generate Databricks connector M query."""
        server = self._parse_jdbc_url(url, "databricks")
        safe_query = self._escape_m_string(query)
        if query:
            return (
                f'let\n'
                f'    Source = Databricks.Catalogs("{server}", "/sql/1.0/warehouses/default"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n    Query'
            )
        return f'let\n    Source = Databricks.Catalogs("{server}", "/sql/1.0/warehouses/default")\nin\n    Source'

    def _spark_m_query(self, url: str, query: str) -> str:
        """Generate Spark / Hive ThriftServer M query."""
        server = self._parse_jdbc_url(url, "spark")
        safe_query = self._escape_m_string(query)
        if query:
            return (
                f'let\n'
                f'    Source = SparkThrift.Database("{server}"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n    Query'
            )
        return f'let\n    Source = SparkThrift.Database("{server}")\nin\n    Source'

    def _sqlite_m_query(self, url: str, query: str) -> str:
        """Generate SQLite connector M query."""
        path = url.replace("jdbc:sqlite:", "")
        safe_query = self._escape_m_string(query)
        if query:
            return (
                f'let\n'
                f'    Source = Sqlite.Database("{path}"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n    Query'
            )
        return f'let\n    Source = Sqlite.Database("{path}")\nin\n    Source'

    def _sybase_m_query(self, url: str, query: str) -> str:
        """Generate Sybase connector M query."""
        server = self._parse_jdbc_url(url, "sybase")
        safe_query = self._escape_m_string(query)
        if query:
            return (
                f'let\n'
                f'    Source = Sybase.Database("{server}"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n    Query'
            )
        return f'let\n    Source = Sybase.Database("{server}")\nin\n    Source'

    def _db2_m_query(self, url: str, query: str) -> str:
        """Generate DB2 connector M query."""
        server = self._parse_jdbc_url(url, "db2")
        parts = server.split("/", 1)
        host = parts[0]
        db = parts[1] if len(parts) > 1 else "SAMPLE"
        safe_query = self._escape_m_string(query)
        if query:
            return (
                f'let\n'
                f'    Source = DB2.Database("{host}", "{db}"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n    Query'
            )
        return f'let\n    Source = DB2.Database("{host}", "{db}")\nin\n    Source'

    def _teradata_m_query(self, url: str, query: str) -> str:
        """Generate Teradata connector M query."""
        server = self._parse_jdbc_url(url, "teradata")
        safe_query = self._escape_m_string(query)
        if query:
            return (
                f'let\n'
                f'    Source = Teradata.Database("{server}"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n    Query'
            )
        return f'let\n    Source = Teradata.Database("{server}")\nin\n    Source'

    def _csv_m_query(self, url: str, query: str) -> str:
        """Generate CSV file connector M query."""
        return (
            f'let\n'
            f'    Source = Csv.Document(File.Contents("{url}"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]),\n'
            f'    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true])\n'
            f'in\n    PromotedHeaders'
        )

    def _excel_m_query(self, url: str, query: str) -> str:
        """Generate Excel file connector M query."""
        return (
            f'let\n'
            f'    Source = Excel.Workbook(File.Contents("{url}"), null, true)\n'
            f'in\n    Source'
        )

    def _json_m_query(self, url: str, query: str) -> str:
        """Generate JSON file connector M query."""
        return (
            f'let\n'
            f'    Source = Json.Document(File.Contents("{url}")),\n'
            f'    ToTable = Table.FromRecords(Source)\n'
            f'in\n    ToTable'
        )

    def _xml_m_query(self, url: str, query: str) -> str:
        """Generate XML file connector M query."""
        return (
            f'let\n'
            f'    Source = Xml.Document(File.Contents("{url}")),\n'
            f'    ToTable = Table.FromValue(Source)\n'
            f'in\n    ToTable'
        )

    def _sharepoint_m_query(self, url: str, query: str) -> str:
        """Generate SharePoint connector M query."""
        return (
            f'let\n'
            f'    Source = SharePoint.Contents("{url}", [ApiVersion = 15])\n'
            f'in\n    Source'
        )

    def _odata_m_query(self, url: str, query: str) -> str:
        """Generate OData connector M query."""
        return (
            f'let\n'
            f'    Source = OData.Feed("{url}")\n'
            f'in\n    Source'
        )

    def _web_m_query(self, url: str, query: str) -> str:
        """Generate Web.Contents connector M query."""
        return (
            f'let\n'
            f'    Source = Web.Contents("{url}"),\n'
            f'    Data = Json.Document(Source)\n'
            f'in\n    Data'
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
