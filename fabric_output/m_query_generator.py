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
    # ── AWS S3 (BEFORE athena — s3:// in URL must not match generic drivers) ──
    ("s3.amazonaws", "AmazonS3.Contents"),
    ("s3a://", "AmazonS3.Contents"),
    ("s3n://", "AmazonS3.Contents"),
    ("s3://", "AmazonS3.Contents"),
    ("athena", "Odbc.DataSource"),
    # ── File / document sources ──
    ("csv", "Csv.Document"),
    ("excel", "Excel.Workbook"),
    ("json", "Json.Document"),
    ("xml", "Xml.Document"),
    # ── Azure / Microsoft (BEFORE generic http — URLs contain https://) ──
    ("azure.datalake", "AzureStorage.DataLake"),
    ("datalakestore", "AzureStorage.DataLake"),
    ("dfs.core", "AzureStorage.DataLake"),
    ("adls", "AzureStorage.DataLake"),
    ("azureblob", "AzureStorage.Blobs"),
    ("blob.core", "AzureStorage.Blobs"),
    ("azuretable", "AzureStorage.Tables"),
    ("table.core", "AzureStorage.Tables"),
    ("dataverse", "CommonDataService.Database"),
    ("dynamics", "CommonDataService.Database"),
    ("kusto", "AzureDataExplorer.Contents"),
    ("azuredataexplorer", "AzureDataExplorer.Contents"),
    ("fabric", "Lakehouse.Contents"),
    ("lakehouse", "Lakehouse.Contents"),
    # ── AWS (BEFORE generic http — URLs contain https://*.amazonaws.com) ──
    ("dynamodb", "DynamoDB.Contents"),
    ("aurora", "PostgreSQL.Database"),  # Aurora PostgreSQL-compatible
    ("rds.amazonaws", "PostgreSQL.Database"),  # RDS default → PostgreSQL
    ("documentdb.amazonaws", "MongoDB.Database"),  # AWS DocumentDB is MongoDB-compatible
    ("neptune.amazonaws", "Odbc.DataSource"),  # Neptune graph DB via ODBC
    ("kinesis", "Odbc.DataSource"),  # Kinesis via ODBC/JDBC
    ("glue", "Odbc.DataSource"),  # AWS Glue via ODBC
    ("emr", "SparkThrift.Database"),  # EMR Spark/Hive
    ("timestream", "Odbc.DataSource"),  # Amazon Timestream via ODBC
    # ── Access / OLAP ──
    ("access", "Access.Database"),
    ("msaccess", "Access.Database"),
    ("ucanaccess", "Access.Database"),
    ("olap4j", "AnalysisServices.Database"),
    ("ssas", "AnalysisServices.Database"),
    ("mdx", "AnalysisServices.Database"),
    # ── Cloud / SaaS connectors ──
    ("sharepoint", "SharePoint.Contents"),
    ("odata", "OData.Feed"),
    # ── Generic catch-all (MUST be last — matches any https:// URL) ──
    ("rest", "Web.Contents"),
    ("http", "Web.Contents"),
    ("ftp", "File.Contents"),
    # ── Misc ──
    ("netezza", "Odbc.DataSource"),
    ("greenplum", "Odbc.DataSource"),
    ("exasol", "Odbc.DataSource"),
    ("dremio", "Odbc.DataSource"),
    ("denodo", "Odbc.DataSource"),
    ("singlestore", "MySQL.Database"),
    ("memsql", "MySQL.Database"),
    ("cockroach", "PostgreSQL.Database"),
    ("yugabyte", "PostgreSQL.Database"),
    ("timescale", "PostgreSQL.Database"),
    ("citus", "PostgreSQL.Database"),
]

# BIRT ODA extensionID → M connector mapping.
# When JDBC URL/driver are missing (e.g. library references), the extensionID
# from the <oda-data-source> element is the best signal for connector type.
_EXTENSION_ID_MAP: dict[str, str] = {
    # ── JDBC (default to Oracle — most common in BIRT enterprise) ──
    "org.eclipse.birt.report.data.oda.jdbc": "Oracle.Database",
    # ── File-based ODA drivers ──
    "org.eclipse.datatools.connectivity.oda.flatfile": "Csv.Document",
    "org.eclipse.datatools.enablement.oda.xml": "Xml.Document",
    "org.eclipse.birt.report.data.oda.excel": "Excel.Workbook",
    "com.actuate.birt.data.json": "Json.Document",
    # ── Database ODA drivers ──
    "org.eclipse.birt.data.oda.mongodb": "MongoDB.Database",
    "org.eclipse.datatools.enablement.oda.ecore": "Odbc.DataSource",
    # ── Cloud / SaaS ODA drivers ──
    "org.eclipse.datatools.enablement.oda.ws": "Web.Contents",
    "com.actuate.birt.data.rest": "Web.Contents",
    "com.actuate.birt.data.salesforce": "Web.Contents",
    "com.actuate.birt.data.odata": "OData.Feed",
    # ── Big Data ODA drivers ──
    "com.actuate.birt.data.cassandra": "Odbc.DataSource",
    "com.actuate.birt.data.hadoop.hive": "SparkThrift.Database",
    "com.actuate.birt.data.hadoop.hbase": "Odbc.DataSource",
    "com.actuate.birt.data.spark": "SparkThrift.Database",
    # ── AWS ODA / JDBC drivers ──
    "com.simba.athena": "Odbc.DataSource",
    "com.simba.dynamodb": "DynamoDB.Contents",
    "com.simba.redshift": "AmazonRedshift.Database",
    # ── Scripted / in-memory ──
    "org.eclipse.birt.report.data.oda.sampledb": "Sql.Database",
    "org.eclipse.birt.report.data.oda.sampledb.ui": "Sql.Database",
}

# Flat-file delimiter names used by the BIRT flat-file ODA driver.
_BIRT_DELIMITERS: dict[str, str] = {
    "COMMA": ",",
    "SEMICOLON": ";",
    "TAB": "#(tab)",
    "PIPE": "|",
}


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

        # Flat-file ODA sources carry URI/DELIMTYPE/CHARSET instead of a JDBC URL
        if connector == "Csv.Document":
            return self._flatfile_m_query(connection)

        # Library-reference sources: no URL/driver, but we know the connector
        # type from extensionID.  Use the data source name as a hint.
        if not url and connection.get("extends"):
            lib_ref = connection["extends"]
            ds_name = connection.get("name", lib_ref)
            logger.info(
                "Library-ref data source '%s' (extends=%s) → %s",
                ds_name, lib_ref, connector,
            )

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
        elif connector == "AzureStorage.DataLake":
            return self._adls_m_query(url, query)
        elif connector == "AzureStorage.Blobs":
            return self._azure_blob_m_query(url, query)
        elif connector == "AzureStorage.Tables":
            return self._azure_table_m_query(url, query)
        elif connector == "CommonDataService.Database":
            return self._dataverse_m_query(url, query)
        elif connector == "AzureDataExplorer.Contents":
            return self._adx_m_query(url, query)
        elif connector == "Lakehouse.Contents":
            return self._lakehouse_m_query(url, query)
        elif connector == "AmazonS3.Contents":
            return self._s3_m_query(url, query)
        elif connector == "DynamoDB.Contents":
            return self._dynamodb_m_query(url, query)
        elif connector == "Access.Database":
            return self._access_m_query(url, query)
        elif connector == "AnalysisServices.Database":
            return self._ssas_m_query(url, query)
        elif connector == "File.Contents":
            return self._file_m_query(url, query)
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

        # Two-pass approach:
        #   Pass 1 — generate M queries for regular (non-joined) datasets
        #   Pass 2 — generate joinedDataSet queries, inlining pass-1 results

        # Pass 1: regular datasets
        m_query_map: dict[str, str] = {}  # dataset_name → M query
        deferred: list[dict[str, Any]] = []  # joinedDataSets for pass 2

        results: list[dict[str, Any]] = []
        for ds in datasets:
            ds_name = ds.get("name", "")
            conn_name = ds.get("data_source", "")
            conn = conn_map.get(conn_name, {})
            query = ds.get("query", "")

            is_joined = query and (
                query.lstrip().startswith("<?xml") or "<joinedDataSet" in query
            )

            if is_joined:
                deferred.append(ds)
                continue

            if conn:
                m_query = self.generate_from_connection(conn, query)
            elif query:
                m_query = self._native_query_placeholder(query)
            else:
                m_query = f'// No data source found for dataset: {ds_name}\nnull'

            # Append Table.AddColumn steps for BIRT computed columns
            cc = ds.get("computed_columns", [])
            if cc:
                m_query = self._append_computed_columns(m_query, cc)

            m_query_map[ds_name] = m_query
            results.append({
                "dataset_name": ds_name,
                "connection_name": conn_name,
                "m_query": m_query,
                "sql_query": query,
            })

        # Pass 2: joinedDataSets — inline constituent queries
        for ds in deferred:
            ds_name = ds.get("name", "")
            conn_name = ds.get("data_source", "")
            query = ds.get("query", "")

            m_query = self._joined_dataset_m_query(query, m_query_map)

            # Append Table.AddColumn steps for BIRT computed columns
            cc = ds.get("computed_columns", [])
            if cc:
                m_query = self._append_computed_columns(m_query, cc)

            m_query_map[ds_name] = m_query
            results.append({
                "dataset_name": ds_name,
                "connection_name": conn_name,
                "m_query": m_query,
                "sql_query": query,
            })

        logger.info("Generated %d M queries from %d datasets", len(results), len(datasets))
        return results

    def _resolve_connector(self, driver_class: str, url: str, ext_id: str) -> str:
        """Resolve JDBC driver / ODA extensionID to M connector type."""
        # 1. Try JDBC pattern matching on driver + URL + ext_id
        search_str = f"{driver_class} {url} {ext_id}".lower()
        for pattern, connector in _JDBC_CONNECTORS:
            if pattern in search_str:
                return connector
        # 2. Fall back to extensionID mapping (library-ref sources with no URL)
        if ext_id and ext_id in _EXTENSION_ID_MAP:
            return _EXTENSION_ID_MAP[ext_id]
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

    def _flatfile_m_query(self, connection: dict[str, Any]) -> str:
        """Generate M query from BIRT flat-file ODA properties."""
        uri = connection.get("URI", "")
        delim_key = connection.get("DELIMTYPE", "COMMA")
        charset = connection.get("CHARSET", "UTF-8")
        has_header = connection.get("INCLCOLUMNNAME", "YES") == "YES"

        delimiter = _BIRT_DELIMITERS.get(delim_key, ",")

        # Map BIRT charset names → Power Query encoding code pages
        _CHARSET_MAP: dict[str, int] = {
            "UTF-8": 65001,
            "UTF8": 65001,
            "ISO-8859-1": 28591,
            "ISO-8859-15": 28605,
            "WINDOWS-1252": 1252,
            "CP1252": 1252,
            "US-ASCII": 20127,
            "UTF-16": 1200,
        }
        encoding = _CHARSET_MAP.get(charset.upper(), 65001)

        if has_header:
            return (
                f'let\n'
                f'    Source = Csv.Document(File.Contents("{uri}"), '
                f'[Delimiter="{delimiter}", Encoding={encoding}, '
                f'QuoteStyle=QuoteStyle.None]),\n'
                f'    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true])\n'
                f'in\n'
                f'    PromotedHeaders'
            )
        return (
            f'let\n'
            f'    Source = Csv.Document(File.Contents("{uri}"), '
            f'[Delimiter="{delimiter}", Encoding={encoding}, '
            f'QuoteStyle=QuoteStyle.None])\n'
            f'in\n'
            f'    Source'
        )

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

    # ── Azure / Microsoft connectors ──

    def _adls_m_query(self, url: str, query: str) -> str:
        """Generate Azure Data Lake Storage Gen2 M query."""
        server = self._parse_jdbc_url(url, "adls") or url
        return (
            f'let\n'
            f'    Source = AzureStorage.DataLake("{server}")\n'
            f'in\n    Source'
        )

    def _azure_blob_m_query(self, url: str, query: str) -> str:
        """Generate Azure Blob Storage M query."""
        server = self._parse_jdbc_url(url, "blob") or url
        return (
            f'let\n'
            f'    Source = AzureStorage.Blobs("{server}")\n'
            f'in\n    Source'
        )

    def _azure_table_m_query(self, url: str, query: str) -> str:
        """Generate Azure Table Storage M query."""
        server = self._parse_jdbc_url(url, "table") or url
        return (
            f'let\n'
            f'    Source = AzureStorage.Tables("{server}")\n'
            f'in\n    Source'
        )

    def _dataverse_m_query(self, url: str, query: str) -> str:
        """Generate Dataverse / Dynamics 365 M query."""
        server = self._parse_jdbc_url(url, "dataverse") or url
        return (
            f'let\n'
            f'    Source = CommonDataService.Database("{server}")\n'
            f'in\n    Source'
        )

    def _adx_m_query(self, url: str, query: str) -> str:
        """Generate Azure Data Explorer (Kusto) M query."""
        server = self._parse_jdbc_url(url, "kusto") or url
        safe_query = self._escape_m_string(query)
        if query:
            return (
                f'let\n'
                f'    Source = AzureDataExplorer.Contents("{server}", "database", '
                f'"{safe_query}")\n'
                f'in\n    Source'
            )
        return (
            f'let\n'
            f'    Source = AzureDataExplorer.Contents("{server}", "database")\n'
            f'in\n    Source'
        )

    def _lakehouse_m_query(self, url: str, query: str) -> str:
        """Generate Microsoft Fabric Lakehouse M query."""
        return (
            f'let\n'
            f'    Source = Lakehouse.Contents(null, null)\n'
            f'in\n    Source'
        )

    # ── Desktop DB / OLAP connectors ──

    def _access_m_query(self, url: str, query: str) -> str:
        """Generate Microsoft Access M query."""
        path = url.replace("jdbc:ucanaccess://", "").split(";")[0]
        safe_query = self._escape_m_string(query)
        if query:
            return (
                f'let\n'
                f'    Source = Access.Database("{path}"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n    Query'
            )
        return (
            f'let\n'
            f'    Source = Access.Database("{path}")\n'
            f'in\n    Source'
        )

    def _ssas_m_query(self, url: str, query: str) -> str:
        """Generate Analysis Services / SSAS M query."""
        server = self._parse_jdbc_url(url, "ssas") or url
        safe_query = self._escape_m_string(query)
        if query:
            return (
                f'let\n'
                f'    Source = AnalysisServices.Database("{server}"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n    Query'
            )
        return (
            f'let\n'
            f'    Source = AnalysisServices.Database("{server}")\n'
            f'in\n    Source'
        )

    # ── AWS connectors ──

    def _s3_m_query(self, url: str, query: str) -> str:
        """Generate Amazon S3 M query.

        Power BI connects to S3 via the Web.Contents / Csv.Document pattern
        or via the AmazonS3.Contents custom connector.
        """
        # Normalise s3:// URIs to https:// endpoint
        bucket_url = url
        for prefix in ("s3://", "s3a://", "s3n://"):
            if url.lower().startswith(prefix):
                path = url[len(prefix):]
                bucket = path.split("/")[0]
                key = "/".join(path.split("/")[1:]) if "/" in path else ""
                bucket_url = f"https://{bucket}.s3.amazonaws.com/{key}"
                break
        return (
            f'let\n'
            f'    Source = Web.Contents("{bucket_url}"),\n'
            f'    Data = Csv.Document(Source, [Delimiter=",", Encoding=65001])\n'
            f'in\n    Data'
        )

    def _dynamodb_m_query(self, url: str, query: str) -> str:
        """Generate Amazon DynamoDB M query.

        PBI has no native DynamoDB connector — use ODBC with the
        CData / Simba DynamoDB driver, or export to S3 + Csv.
        """
        server = self._parse_jdbc_url(url, "dynamodb") or url
        region = "us-east-1"  # default; real region extracted from URL if present
        import re as _re
        m = _re.search(r'dynamodb\.([a-z0-9-]+)\.amazonaws', url)
        if m:
            region = m.group(1)
        safe_query = self._escape_m_string(query)
        if query:
            return (
                f'let\n'
                f'    Source = Odbc.DataSource("DRIVER={{CData ODBC Driver for DynamoDB}};'
                f'Region={region};"),\n'
                f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
                f'in\n    Query'
            )
        return (
            f'let\n'
            f'    Source = Odbc.DataSource("DRIVER={{CData ODBC Driver for DynamoDB}};'
            f'Region={region};")\n'
            f'in\n    Source'
        )

    def _file_m_query(self, url: str, query: str) -> str:
        """Generate generic File.Contents M query (FTP / local files)."""
        return (
            f'let\n'
            f'    Source = File.Contents("{url}")\n'
            f'in\n    Source'
        )

    def _native_query_placeholder(self, query: str) -> str:
        """Generate placeholder M query when no connection info available."""
        if query.lstrip().startswith("<?xml") or "<joinedDataSet" in query:
            return self._joined_dataset_m_query(query, {})

        safe_query = self._escape_m_string(query)
        return (
            f'let\n'
            f'    // TODO: Configure data source connection\n'
            f'    Source = Odbc.DataSource(""),\n'
            f'    Query = Value.NativeQuery(Source, "{safe_query}")\n'
            f'in\n'
            f'    Query'
        )

    # ── BIRT joinedDataSet → Table.NestedJoin ──

    _BIRT_JOIN_KIND: dict[str, str] = {
        "inner": "JoinKind.Inner",
        "left": "JoinKind.LeftOuter",
        "right": "JoinKind.RightOuter",
        "full": "JoinKind.FullOuter",
        "cross": "JoinKind.FullOuter",
    }

    def _joined_dataset_m_query(self, xml_text: str, m_query_map: dict[str, str]) -> str:
        """Translate BIRT joinedDataSet XML into a self-contained M query.

        Each constituent dataset's M query is inlined as a ``let`` step
        so the partition is fully standalone (TMDL partitions can't
        reference other partitions by name).

        Generates::

            let
                controle_fond = let Source = Oracle.Database("") ... in Query,
                Completions = let Source = Csv.Document(...) ... in Source,
                Merged = Table.NestedJoin(controle_fond, {"Key"}, Completions, {"Key"}, "Joined", JoinKind.Inner),
                Expanded = Table.ExpandTableColumn(Merged, "Joined", {"col1", ...}),
                Selected = Table.SelectColumns(Expanded, {"col1", "col2", ...})
            in
                Selected
        """
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            logger.warning("Failed to parse joinedDataSet XML — using #table fallback")
            return self._joined_dataset_fallback(xml_text)

        # Namespace handling — ElementTree converts tns:/ns0: to full URI
        ns = ""
        birt_ns = "{http://schemas.actuate.com/birt/dataset_join.xsd}"
        if root.find(f".//{birt_ns}startingDataSet") is not None:
            ns = birt_ns
        elif root.find(".//startingDataSet") is not None:
            ns = ""
        else:
            m = re.match(r"\{([^}]+)\}", root.tag)
            if m:
                ns = f"{{{m.group(1)}}}"

        # 1. Parse selected columns
        select_cols: list[tuple[str, str]] = []
        for col_el in root.iter(f"{ns}Column"):
            raw = col_el.text or ""
            if "::" in raw:
                ds_name, col_name = raw.split("::", 1)
            else:
                ds_name, col_name = "", raw
            select_cols.append((ds_name, col_name))

        # 2. Parse starting dataset
        start_el = root.find(f".//{ns}startingDataSet")
        if start_el is None:
            return self._joined_dataset_fallback(xml_text)
        left_ds = start_el.get("name", "")

        # 3. Parse joins
        joins: list[dict[str, Any]] = []
        for join_el in root.iter(f"{ns}join"):
            ds_el = join_el.find(f"{ns}dataSet")
            type_el = join_el.find(f"{ns}type")
            right_ds = ds_el.get("name", "") if ds_el is not None else ""
            join_type = (type_el.text or "inner").strip().lower() if type_el is not None else "inner"

            left_keys: list[str] = []
            right_keys: list[str] = []
            for cond_el in join_el.iter(f"{ns}condition"):
                left_col_el = cond_el.find(f"{ns}leftColumn")
                right_col_el = cond_el.find(f"{ns}rightColumn")
                lc = (left_col_el.text or "").split("::")[-1] if left_col_el is not None else ""
                rc = (right_col_el.text or "").split("::")[-1] if right_col_el is not None else ""
                if lc:
                    left_keys.append(lc)
                if rc:
                    right_keys.append(rc)

            joins.append({
                "right_ds": right_ds,
                "join_type": join_type,
                "left_keys": left_keys,
                "right_keys": right_keys,
            })

        if not joins:
            return self._joined_dataset_fallback(xml_text)

        # 4. Collect all referenced dataset names
        referenced_ds = [left_ds] + [j["right_ds"] for j in joins]

        # 5. Build M query with inlined constituent queries
        lines: list[str] = ["let"]

        # Inline each constituent dataset's M query as a let step
        for ds_name in referenced_ds:
            source_m = m_query_map.get(ds_name, "")
            if source_m:
                # Wrap the full M expression in parentheses so it becomes
                # a single value expression:  ds_name = (let ... in Result),
                # Indent the inlined M for readability
                indented = source_m.replace("\n", "\n        ")
                lines.append(f"    {ds_name} = ({indented}),")
            else:
                # No M query available — use an empty #table placeholder
                ds_cols = [c for d, c in select_cols if d == ds_name]
                if ds_cols:
                    cols_m = ", ".join(f'"{self._escape_m_string(c)}"' for c in ds_cols)
                    lines.append(f"    // TODO: Configure source for {ds_name}")
                    lines.append(f"    {ds_name} = #table({{{cols_m}}}, {{}}),")
                else:
                    lines.append(f"    // TODO: Configure source for {ds_name}")
                    lines.append(f"    {ds_name} = #table({{}}, {{}}),")

        # Generate Table.NestedJoin steps
        current_table = left_ds
        for i, j in enumerate(joins):
            right_ds = j["right_ds"]
            join_kind = self._BIRT_JOIN_KIND.get(j["join_type"], "JoinKind.Inner")
            l_keys = ", ".join(f'"{self._escape_m_string(k)}"' for k in j["left_keys"])
            r_keys = ", ".join(f'"{self._escape_m_string(k)}"' for k in j["right_keys"])
            joined_alias = f"_joined_{i}" if len(joins) > 1 else "Joined"
            step_name = f"Merged{i}" if len(joins) > 1 else "Merged"

            lines.append(
                f'    {step_name} = Table.NestedJoin('
                f'{current_table}, {{{l_keys}}}, '
                f'{right_ds}, {{{r_keys}}}, '
                f'"{joined_alias}", {join_kind}),'
            )

            right_cols = [c for ds, c in select_cols if ds == right_ds]
            if right_cols:
                cols_m = ", ".join(f'"{self._escape_m_string(c)}"' for c in right_cols)
                expand_step = f"Expanded{i}" if len(joins) > 1 else "Expanded"
                lines.append(
                    f'    {expand_step} = Table.ExpandTableColumn('
                    f'{step_name}, "{joined_alias}", {{{cols_m}}}),'
                )
                current_table = expand_step
            else:
                current_table = step_name

        # Select final columns
        all_col_names = [c for _, c in select_cols]
        if all_col_names:
            final_cols = ", ".join(f'"{self._escape_m_string(c)}"' for c in all_col_names)
            lines.append(
                f'    Selected = Table.SelectColumns({current_table}, {{{final_cols}}})'
            )
            lines.append("in\n    Selected")
        else:
            lines[-1] = lines[-1].rstrip(",")
            lines.append(f"in\n    {current_table}")

        return "\n".join(lines)

    def _joined_dataset_fallback(self, xml_text: str) -> str:
        """Fallback: extract column names from XML and generate #table."""
        col_names: list[str] = []
        for m in re.finditer(r"<(?:tns|ns0):Column>([^<]+)</(?:tns|ns0):Column>", xml_text):
            raw = m.group(1)
            col = raw.split("::")[-1] if "::" in raw else raw
            col_names.append(col)
        if col_names:
            cols_m = ", ".join(f'"{self._escape_m_string(c)}"' for c in col_names)
            return (
                f'let\n'
                f'    // TODO: BIRT joinedDataSet — configure join in Power Query\n'
                f'    Source = #table({{{cols_m}}}, {{}})\n'
                f'in\n'
                f'    Source'
            )
        return (
            'let\n'
            '    // TODO: BIRT joinedDataSet — configure in Power Query\n'
            '    Source = #table({}, {})\n'
            'in\n'
            '    Source'
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

    # ── BIRT computed columns → Table.AddColumn ──

    @staticmethod
    def _m_field_ref(name: str) -> str:
        """Return a Power Query M field-access expression for *name*.

        Simple identifiers (ASCII alphanumeric + underscore, not starting
        with a digit) use plain ``[Name]``; everything else uses the
        escaped form ``[#"Name"]``.
        """
        if re.fullmatch(r"[A-Za-z_]\w*", name):
            return f"[{name}]"
        return f'[#"{name}"]'

    @classmethod
    def _birt_js_to_m(cls, expr: str) -> str:
        """Translate a BIRT JavaScript computed-column expression to M.

        Handles ``row["col"]`` → ``[#"col"]``, JS ``if/else`` → M
        ``if/then/else``, common operators, and known BIRT functions.
        """
        if not expr:
            return "null"
        out = expr.strip()

        # row["Column Name"] or row['Column Name'] → [#"Column Name"]
        out = re.sub(
            r'row\[\s*"([^"]+)"\s*\]',
            lambda m: cls._m_field_ref(m.group(1)),
            out,
        )
        out = re.sub(
            r"row\[\s*'([^']+)'\s*\]",
            lambda m: cls._m_field_ref(m.group(1)),
            out,
        )
        out = re.sub(
            r"\brow\.([A-Za-z_]\w*)",
            lambda m: cls._m_field_ref(m.group(1)),
            out,
        )

        # BirtMath.round(x) → Number.Round(x)
        out = re.sub(r"\bBirtMath\.round\s*", "Number.Round", out)

        # Operators: != → <>, && → and, || → or
        out = out.replace("!=", "<>")
        out = re.sub(r"&&", " and ", out)
        out = re.sub(r"\|\|", " or ", out)

        # Remove JS block braces — M uses if/then/else without braces
        out = out.replace("{", "").replace("}", "")

        # Convert  if (...) body  →  if ... then body
        # Handle balanced parentheses for the condition.
        result: list[str] = []
        i = 0
        while i < len(out):
            # Match "if (" or "else if ("
            m = re.match(r"(else\s+)?if\s*\(", out[i:])
            if m:
                prefix = (m.group(1) or "").strip()
                prefix = f"{prefix} " if prefix else ""
                i += m.end()
                # Find matching closing paren
                depth, start = 1, i
                while i < len(out) and depth > 0:
                    if out[i] == "(":
                        depth += 1
                    elif out[i] == ")":
                        depth -= 1
                    i += 1
                cond = out[start : i - 1].strip()
                result.append(f"{prefix}if {cond} then ")
            else:
                result.append(out[i])
                i += 1
        out = "".join(result)

        # Normalise "else" (standalone, not part of "else if")
        out = re.sub(r"\belse\b(?!\s+if\b)", "else", out)

        # Clean up whitespace — collapse to single line
        out = re.sub(r"\s+", " ", out)
        out = out.strip()

        # M requires every "if ... then ..." to have an "else" clause.
        # Count unmatched if/then vs else and append "else null" for each.
        if_count = len(re.findall(r"\bif\b", out))
        else_count = len(re.findall(r"\belse\b", out))
        for _ in range(if_count - else_count):
            out += " else null"

        return out

    def _append_computed_columns(
        self, m_query: str, computed_columns: list[dict[str, Any]]
    ) -> str:
        """Wrap an M query to add Table.AddColumn steps for computed columns.

        Transforms::

            let Source = ... in Result

        into::

            let
                _base = (let Source = ... in Result),
                _c1 = Table.AddColumn(_base, "col", each <m_expr>),
                _c2 = Table.AddColumn(_c1, "col2", each <m_expr>)
            in _c2
        """
        if not computed_columns:
            return m_query

        # Filter to valid computed columns only
        valid_cc = [cc for cc in computed_columns if cc.get("name")]
        if not valid_cc:
            return m_query

        lines = ["let"]
        # Inline the original query as _base
        indented = m_query.replace("\n", "\n        ")
        lines.append(f"    _base = ({indented}),")

        prev_step = "_base"
        for i, cc in enumerate(valid_cc):
            col_name = cc["name"]
            expr = cc.get("expression", "")
            m_expr = self._birt_js_to_m(expr)
            safe_name = self._escape_m_string(col_name)
            step = f"_c{i}"
            comma = "," if i < len(valid_cc) - 1 else ""
            lines.append(
                f'    {step} = Table.AddColumn({prev_step}, '
                f'"{safe_name}", each {m_expr}){comma}'
            )
            prev_step = step

        lines.append(f"in\n    {prev_step}")
        return "\n".join(lines)
