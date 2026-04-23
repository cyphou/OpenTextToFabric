"""Tests for deploy.refresh_gateway — schedule conversion and gateway binding."""

import unittest

from deploy.refresh_gateway import (
    GatewayConfig,
    RefreshScheduleGenerator,
)


class TestRefreshScheduleGenerator(unittest.TestCase):
    def test_from_birt_schedule_daily(self):
        schedule = {
            "frequency": "daily",
            "time": "08:00",
            "timezone": "UTC",
        }
        gen = RefreshScheduleGenerator()
        result = gen.from_birt_schedule(schedule)
        self.assertEqual(result["schedule"]["frequency"], "Daily")
        self.assertIn("08:00", result["schedule"]["times"])
        self.assertEqual(result["localTimeZoneId"], "UTC")

    def test_from_birt_schedule_weekly(self):
        schedule = {
            "frequency": "weekly",
            "time": "06:00",
            "days": ["Monday", "Wednesday", "Friday"],
            "timezone": "Europe/Paris",
        }
        gen = RefreshScheduleGenerator()
        result = gen.from_birt_schedule(schedule)
        self.assertEqual(result["schedule"]["frequency"], "Weekly")
        self.assertEqual(len(result["schedule"]["days"]), 3)

    def test_from_birt_schedule_hourly(self):
        schedule = {
            "frequency": "hourly",
        }
        gen = RefreshScheduleGenerator()
        result = gen.from_birt_schedule(schedule)
        self.assertTrue(result["enabled"])

    def test_from_ihub_schedule(self):
        schedule = {
            "recurrenceType": "DAILY",
            "startTime": "09:00",
            "timeZone": "America/New_York",
        }
        gen = RefreshScheduleGenerator()
        result = gen.from_ihub_schedule(schedule)
        self.assertEqual(result["schedule"]["frequency"], "Daily")

    def test_from_cron_daily(self):
        gen = RefreshScheduleGenerator()
        result = gen.from_cron("0 8 * * *")  # Daily at 8am
        self.assertEqual(result["schedule"]["frequency"], "Daily")
        self.assertIn("08:00", result["schedule"]["times"])

    def test_from_cron_weekly(self):
        gen = RefreshScheduleGenerator()
        result = gen.from_cron("0 6 * * 1,3,5")  # Mon, Wed, Fri at 6am
        self.assertEqual(result["schedule"]["frequency"], "Weekly")

    def test_summary(self):
        gen = RefreshScheduleGenerator()
        gen.from_birt_schedule({"frequency": "daily"})
        s = gen.summary()
        self.assertEqual(s["total_schedules"], 1)


class TestGatewayConfig(unittest.TestCase):
    def test_map_oracle_connection(self):
        gw = GatewayConfig()
        conn = {
            "driver": "oracle.jdbc.OracleDriver",
            "url": "jdbc:oracle:thin:@dbhost:1521:ORCL",
            "user": "scott",
        }
        result = gw.map_connection(conn)
        self.assertEqual(result["datasourceType"], "Oracle")
        self.assertIn("dbhost", result["connectionDetails"]["server"])

    def test_map_postgresql_connection(self):
        gw = GatewayConfig()
        conn = {
            "driver": "org.postgresql.Driver",
            "url": "jdbc:postgresql://pghost:5432/mydb",
            "user": "admin",
        }
        result = gw.map_connection(conn)
        self.assertEqual(result["datasourceType"], "PostgreSql")
        self.assertIn("pghost", result["connectionDetails"]["server"])
        self.assertEqual(result["connectionDetails"]["database"], "mydb")

    def test_map_sqlserver_connection(self):
        gw = GatewayConfig()
        conn = {
            "driver": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
            "url": "jdbc:sqlserver://sqlhost:1433;databaseName=AdventureWorks",
            "user": "sa",
        }
        result = gw.map_connection(conn)
        self.assertEqual(result["datasourceType"], "Sql")

    def test_map_mysql_connection(self):
        gw = GatewayConfig()
        conn = {
            "driver": "com.mysql.jdbc.Driver",
            "url": "jdbc:mysql://myhost:3306/shop",
            "user": "root",
        }
        result = gw.map_connection(conn)
        self.assertEqual(result["datasourceType"], "MySql")

    def test_map_unknown_driver(self):
        gw = GatewayConfig()
        conn = {
            "driver": "com.custom.UnknownDriver",
            "url": "jdbc:custom://host/db",
            "user": "user",
        }
        result = gw.map_connection(conn)
        self.assertEqual(result["datasourceType"], "Unknown")

    def test_map_db2_connection(self):
        gw = GatewayConfig()
        conn = {
            "driver": "com.ibm.db2.jcc.DB2Driver",
            "url": "jdbc:db2://db2host:50000/SAMPLE",
            "user": "db2inst",
        }
        result = gw.map_connection(conn)
        self.assertEqual(result["datasourceType"], "DB2")

    def test_map_teradata_connection(self):
        gw = GatewayConfig()
        conn = {
            "driver": "com.teradata.jdbc.TeraDriver",
            "url": "jdbc:teradata://tdhost/DBS_PORT=1025",
            "user": "dbc",
        }
        result = gw.map_connection(conn)
        self.assertEqual(result["datasourceType"], "Teradata")

    def test_map_sap_connection(self):
        gw = GatewayConfig()
        conn = {
            "driver": "com.sap.db.jdbc.Driver",
            "url": "jdbc:sap://hanahost:30015",
            "user": "SYSTEM",
        }
        result = gw.map_connection(conn)
        self.assertEqual(result["datasourceType"], "SapHana")

    def test_map_all(self):
        gw = GatewayConfig()
        connections = [
            {"driver": "oracle.jdbc.OracleDriver", "url": "jdbc:oracle:thin:@h:1521:S"},
            {"driver": "org.postgresql.Driver", "url": "jdbc:postgresql://h:5432/d"},
        ]
        results = gw.map_all(connections)
        self.assertEqual(len(results), 2)

    def test_summary(self):
        gw = GatewayConfig()
        gw.map_connection({"driver": "oracle.jdbc.OracleDriver", "url": ""})
        gw.map_connection({"driver": "oracle.jdbc.OracleDriver", "url": ""})
        s = gw.summary()
        self.assertEqual(s["total_mappings"], 2)
        self.assertEqual(s["by_type"]["Oracle"], 2)


if __name__ == "__main__":
    unittest.main()
