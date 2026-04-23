"""Tests for report_converter.multi_datasource."""

import unittest

from report_converter.multi_datasource import DataSourceAnalyzer


class TestDataSourceAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = DataSourceAnalyzer()

    def test_single_oracle_source(self):
        connections = [{"name": "OracleDS", "driver": "oracle.jdbc.OracleDriver", "type": "jdbc"}]
        datasets = [{"name": "Sales", "data_source": "OracleDS"}]
        result = self.analyzer.analyze(connections, datasets)
        self.assertEqual(result["mode"], "directlake")
        self.assertEqual(result["total_connections"], 1)

    def test_single_csv_source(self):
        connections = [{"name": "CSV", "driver": "", "type": "csv"}]
        datasets = [{"name": "Data", "data_source": "CSV"}]
        result = self.analyzer.analyze(connections, datasets)
        self.assertEqual(result["mode"], "import")

    def test_multi_source_composite(self):
        connections = [
            {"name": "Oracle", "driver": "oracle.jdbc.OracleDriver", "type": "jdbc"},
            {"name": "Postgres", "driver": "org.postgresql.Driver", "type": "jdbc"},
        ]
        datasets = [
            {"name": "Sales", "data_source": "Oracle"},
            {"name": "Inventory", "data_source": "Postgres"},
        ]
        result = self.analyzer.analyze(connections, datasets)
        # Multiple sources with cross-source joins → composite
        self.assertIn(result["mode"], ("directlake", "composite"))

    def test_cross_source_joins_detected(self):
        connections = [
            {"name": "Oracle", "driver": "oracle.jdbc.OracleDriver", "type": "jdbc"},
            {"name": "CSV", "driver": "", "type": "csv"},
        ]
        datasets = [
            {"name": "Sales", "data_source": "Oracle"},
            {"name": "Lookup", "data_source": "CSV"},
        ]
        result = self.analyzer.analyze(connections, datasets)
        self.assertTrue(len(result["cross_source_joins"]) > 0)
        self.assertEqual(result["mode"], "composite")

    def test_no_connections(self):
        result = self.analyzer.analyze([], [])
        self.assertEqual(result["mode"], "import")
        self.assertEqual(result["total_connections"], 0)

    def test_sqlserver_directlake(self):
        connections = [{"name": "MSSQL", "driver": "com.microsoft.sqlserver.jdbc.SQLServerDriver", "type": "jdbc"}]
        datasets = [{"name": "Data", "data_source": "MSSQL"}]
        result = self.analyzer.analyze(connections, datasets)
        self.assertEqual(result["mode"], "directlake")

    def test_recommendations_generated(self):
        connections = [{"name": "Oracle", "driver": "oracle.jdbc.OracleDriver", "type": "jdbc"}]
        datasets = [{"name": "Sales", "data_source": "Oracle"}]
        result = self.analyzer.analyze(connections, datasets)
        self.assertTrue(len(result["recommendations"]) > 0)

    def test_all_directlake_eligible(self):
        connections = [
            {"name": "Oracle", "driver": "oracle.jdbc.OracleDriver", "type": "jdbc"},
            {"name": "Postgres", "driver": "org.postgresql.Driver", "type": "jdbc"},
        ]
        # Same data source → no cross-source joins
        datasets = [
            {"name": "Sales", "data_source": "MainDS"},
            {"name": "Products", "data_source": "MainDS"},
        ]
        result = self.analyzer.analyze(connections, datasets)
        self.assertEqual(result["mode"], "directlake")

    def test_import_only_forces_import(self):
        connections = [
            {"name": "Excel", "driver": "", "type": "excel"},
        ]
        datasets = [{"name": "Data", "data_source": "Excel"}]
        result = self.analyzer.analyze(connections, datasets)
        self.assertEqual(result["mode"], "import")

    def test_classify_mysql(self):
        connections = [{"name": "MySQL", "driver": "com.mysql.cj.jdbc.Driver", "type": "jdbc"}]
        sources = self.analyzer._classify_sources(connections)
        self.assertEqual(sources[0]["category"], "mysql")
        self.assertTrue(sources[0]["directlake_eligible"])


if __name__ == "__main__":
    unittest.main()
