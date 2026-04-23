"""Tests for M query generator — extended connectors."""

import unittest

from fabric_output.m_query_generator import MQueryGenerator


class TestOracleConnector(unittest.TestCase):
    def test_oracle_with_query(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "oracle.jdbc.OracleDriver", "odaURL": "jdbc:oracle:thin:@dbhost:1521:ORCL"}
        result = gen.generate_from_connection(conn, "SELECT * FROM orders")
        self.assertIn("Oracle.Database", result)
        self.assertIn("Value.NativeQuery", result)

    def test_oracle_without_query(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "oracle.jdbc.OracleDriver", "odaURL": "jdbc:oracle:thin:@dbhost:1521:ORCL"}
        result = gen.generate_from_connection(conn)
        self.assertIn("Oracle.Database", result)
        self.assertNotIn("NativeQuery", result)


class TestPostgresConnector(unittest.TestCase):
    def test_postgresql_with_query(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "org.postgresql.Driver", "odaURL": "jdbc:postgresql://pghost:5432/mydb"}
        result = gen.generate_from_connection(conn, "SELECT 1")
        self.assertIn("PostgreSQL.Database", result)
        self.assertIn("pghost", result)
        self.assertIn("mydb", result)


class TestSqlServerConnector(unittest.TestCase):
    def test_sqlserver(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
                "odaURL": "jdbc:sqlserver://sqlhost:1433;databaseName=DB"}
        result = gen.generate_from_connection(conn, "SELECT 1")
        self.assertIn("Sql.Database", result)


class TestMySQLConnector(unittest.TestCase):
    def test_mysql(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "com.mysql.jdbc.Driver",
                "odaURL": "jdbc:mysql://myhost:3306/shop"}
        result = gen.generate_from_connection(conn, "SELECT 1")
        self.assertIn("MySQL.Database", result)


class TestSapHanaConnector(unittest.TestCase):
    def test_sap_hana(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "com.sap.db.jdbc.Driver",
                "odaURL": "jdbc:sap://hanahost:30015"}
        result = gen.generate_from_connection(conn, "SELECT 1")
        self.assertIn("SapHana.Database", result)

    def test_sap_hana_no_query(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "com.sap.db.jdbc.Driver",
                "odaURL": "jdbc:sap://hanahost:30015"}
        result = gen.generate_from_connection(conn)
        self.assertIn("SapHana.Database", result)
        self.assertNotIn("NativeQuery", result)


class TestSnowflakeConnector(unittest.TestCase):
    def test_snowflake(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "net.snowflake.client.jdbc.SnowflakeDriver",
                "odaURL": "jdbc:snowflake://account.snowflakecomputing.com/mydb"}
        result = gen.generate_from_connection(conn, "SELECT 1")
        self.assertIn("Snowflake.Databases", result)

    def test_snowflake_no_query(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "net.snowflake.client.jdbc.SnowflakeDriver",
                "odaURL": "jdbc:snowflake://account.snowflakecomputing.com/wh"}
        result = gen.generate_from_connection(conn)
        self.assertNotIn("NativeQuery", result)


class TestBigQueryConnector(unittest.TestCase):
    def test_bigquery(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "com.simba.googlebigquery.jdbc.Driver",
                "odaURL": "jdbc:bigquery://https://www.googleapis.com/bigquery/v2:443;ProjectId=my-project"}
        result = gen.generate_from_connection(conn, "SELECT 1")
        self.assertIn("GoogleBigQuery.Database", result)


class TestRedshiftConnector(unittest.TestCase):
    def test_redshift(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "com.amazon.redshift.jdbc.Driver",
                "odaURL": "jdbc:redshift://cluster.us-east-1.redshift.amazonaws.com:5439/dev"}
        result = gen.generate_from_connection(conn, "SELECT 1")
        self.assertIn("AmazonRedshift.Database", result)


class TestMongoDBConnector(unittest.TestCase):
    def test_mongodb(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "mongodb.jdbc.MongoDriver",
                "odaURL": "jdbc:mongodb://mongohost:27017/mydb"}
        result = gen.generate_from_connection(conn)
        self.assertIn("MongoDB.Database", result)


class TestCosmosDBConnector(unittest.TestCase):
    def test_cosmosdb(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "com.azure.cosmos.Driver",
                "odaURL": "jdbc:cosmosdb://myaccount.documents.azure.com:443"}
        result = gen.generate_from_connection(conn)
        self.assertIn("DocumentDB.Contents", result)


class TestElasticsearchConnector(unittest.TestCase):
    def test_elasticsearch(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "org.elasticsearch.xpack.sql.jdbc.EsDriver",
                "odaURL": "jdbc:elasticsearch://eshost:9200"}
        result = gen.generate_from_connection(conn)
        self.assertIn("Elasticsearch.Contents", result)


class TestDatabricksConnector(unittest.TestCase):
    def test_databricks(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "com.databricks.client.jdbc.Driver",
                "odaURL": "jdbc:databricks://adb-xxx.azuredatabricks.net:443/default"}
        result = gen.generate_from_connection(conn, "SELECT 1")
        self.assertIn("Databricks.Catalogs", result)


class TestSparkConnector(unittest.TestCase):
    def test_spark(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "org.apache.hive.jdbc.HiveDriver",
                "odaURL": "jdbc:hive2://sparkhost:10000/default"}
        result = gen.generate_from_connection(conn, "SELECT 1")
        self.assertIn("SparkThrift.Database", result)


class TestSqliteConnector(unittest.TestCase):
    def test_sqlite(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "org.sqlite.JDBC",
                "odaURL": "jdbc:sqlite:///path/to/db.sqlite"}
        result = gen.generate_from_connection(conn, "SELECT 1")
        self.assertIn("Sqlite.Database", result)


class TestDB2Connector(unittest.TestCase):
    def test_db2(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "com.ibm.db2.jcc.DB2Driver",
                "odaURL": "jdbc:db2://db2host:50000/SAMPLE"}
        result = gen.generate_from_connection(conn, "SELECT 1")
        self.assertIn("DB2.Database", result)


class TestTeradataConnector(unittest.TestCase):
    def test_teradata(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "com.teradata.jdbc.TeraDriver",
                "odaURL": "jdbc:teradata://tdhost/DBS_PORT=1025"}
        result = gen.generate_from_connection(conn, "SELECT 1")
        self.assertIn("Teradata.Database", result)


class TestFileConnectors(unittest.TestCase):
    def test_csv(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "", "extension_id": "csv",
                "odaURL": "/data/sales.csv"}
        result = gen.generate_from_connection(conn)
        self.assertIn("Csv.Document", result)

    def test_excel(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "", "extension_id": "excel",
                "odaURL": "/data/report.xlsx"}
        result = gen.generate_from_connection(conn)
        self.assertIn("Excel.Workbook", result)

    def test_json(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "", "extension_id": "json",
                "odaURL": "/data/config.json"}
        result = gen.generate_from_connection(conn)
        self.assertIn("Json.Document", result)

    def test_xml(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "", "extension_id": "xml",
                "odaURL": "/data/data.xml"}
        result = gen.generate_from_connection(conn)
        self.assertIn("Xml.Document", result)


class TestWebConnectors(unittest.TestCase):
    def test_odata(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "", "extension_id": "odata",
                "odaURL": "https://api.example.com/odata"}
        result = gen.generate_from_connection(conn)
        self.assertIn("OData.Feed", result)

    def test_rest_api(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "", "extension_id": "rest",
                "odaURL": "https://api.example.com/data"}
        result = gen.generate_from_connection(conn)
        self.assertIn("Web.Contents", result)

    def test_sharepoint(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "", "extension_id": "sharepoint",
                "odaURL": "https://company.sharepoint.com/sites/data"}
        result = gen.generate_from_connection(conn)
        self.assertIn("SharePoint.Contents", result)


class TestSybaseConnector(unittest.TestCase):
    def test_sybase(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "com.sybase.jdbc4.jdbc.SybDriver",
                "odaURL": "jdbc:sybase:Tds:sybhost:5000/mydb"}
        result = gen.generate_from_connection(conn, "SELECT 1")
        self.assertIn("Sybase.Database", result)


class TestODBCFallback(unittest.TestCase):
    def test_unknown_driver_uses_odbc(self):
        gen = MQueryGenerator()
        conn = {"odaDriverClass": "com.vendor.Unknown",
                "odaURL": "jdbc:vendor://host/db"}
        result = gen.generate_from_connection(conn)
        self.assertIn("Odbc.DataSource", result)


class TestGenerateFromDatasets(unittest.TestCase):
    def test_multiple_datasets(self):
        gen = MQueryGenerator()
        datasets = [
            {"name": "DS1", "data_source": "OraConn", "query": "SELECT 1 FROM dual"},
            {"name": "DS2", "data_source": "PgConn", "query": "SELECT 1"},
        ]
        connections = [
            {"name": "OraConn", "odaDriverClass": "oracle.jdbc.OracleDriver",
             "odaURL": "jdbc:oracle:thin:@host:1521:SID"},
            {"name": "PgConn", "odaDriverClass": "org.postgresql.Driver",
             "odaURL": "jdbc:postgresql://pghost:5432/db"},
        ]
        results = gen.generate_from_datasets(datasets, connections)
        self.assertEqual(len(results), 2)
        self.assertIn("Oracle", results[0]["m_query"])
        self.assertIn("PostgreSQL", results[1]["m_query"])

    def test_dataset_without_connection(self):
        gen = MQueryGenerator()
        datasets = [{"name": "DS1", "data_source": "Missing", "query": "SELECT 1"}]
        connections = []
        results = gen.generate_from_datasets(datasets, connections)
        self.assertEqual(len(results), 1)
        self.assertIn("TODO", results[0]["m_query"])


class TestEscapeMString(unittest.TestCase):
    def test_double_quotes(self):
        result = MQueryGenerator._escape_m_string('He said "hello"')
        self.assertIn('""hello""', result)

    def test_newlines(self):
        result = MQueryGenerator._escape_m_string("line1\nline2")
        self.assertNotIn("\n", result)

    def test_empty(self):
        result = MQueryGenerator._escape_m_string("")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
