"""Tests for fabric_output modules."""

import json
import tempfile
import unittest
from pathlib import Path

from fabric_output.fabric_constants import (
    sanitize_name, sanitize_table_name, sanitize_column_name, spark_type,
)
from fabric_output.lakehouse_generator import LakehouseGenerator
from fabric_output.pipeline_generator import PipelineGenerator
from fabric_output.notebook_generator import NotebookGenerator
from fabric_output.dataflow_generator import DataflowGenerator
from fabric_output.tmdl_generator import TMDLGenerator
from fabric_output.m_query_generator import MQueryGenerator


class TestFabricConstants(unittest.TestCase):

    def test_sanitize_name_basic(self):
        self.assertEqual(sanitize_name("my_table"), "my_table")

    def test_sanitize_name_special_chars(self):
        self.assertEqual(sanitize_name("my table!@#"), "my_table")

    def test_sanitize_name_leading_digit(self):
        result = sanitize_name("123table")
        self.assertTrue(result.startswith("_"))

    def test_sanitize_name_empty(self):
        self.assertEqual(sanitize_name(""), "unnamed")

    def test_sanitize_name_max_length(self):
        result = sanitize_name("a" * 200, max_length=128)
        self.assertTrue(len(result) <= 128)

    def test_sanitize_table_name_lowercase(self):
        self.assertEqual(sanitize_table_name("MyTable"), "mytable")

    def test_spark_type_varchar(self):
        self.assertEqual(spark_type("varchar"), "STRING")

    def test_spark_type_integer(self):
        self.assertEqual(spark_type("integer"), "INT")

    def test_spark_type_parameterized(self):
        self.assertEqual(spark_type("varchar(255)"), "STRING")

    def test_spark_type_unknown(self):
        self.assertEqual(spark_type("xyz_unknown"), "STRING")


class TestLakehouseGenerator(unittest.TestCase):

    def test_generate_ddl(self):
        lh = LakehouseGenerator()
        ddl = lh.generate_ddl()
        self.assertIn("documents", ddl)
        self.assertIn("folders", ddl)
        self.assertIn("metadata", ddl)
        self.assertIn("CREATE TABLE", ddl["documents"])

    def test_generate_ddl_with_custom(self):
        lh = LakehouseGenerator()
        custom = {"custom_table": [("col1", "STRING", "test column")]}
        ddl = lh.generate_ddl(custom_tables=custom)
        self.assertIn("custom_table", ddl)

    def test_generate_folder_structure(self):
        lh = LakehouseGenerator()
        nodes = [
            {"id": 1, "name": "Finance", "type": 0, "path": "/Enterprise/Finance"},
            {"id": 2, "name": "doc.pdf", "type": 144, "path": "/Enterprise/doc.pdf"},
        ]
        mappings = lh.generate_folder_structure(nodes)
        self.assertEqual(len(mappings), 1)  # Only folders
        self.assertTrue(mappings[0]["onelake_path"].startswith("Files/"))

    def test_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lh = LakehouseGenerator()
            files = lh.export(tmpdir)
            self.assertIn("lakehouse_ddl.sql", files)
            self.assertIn("lakehouse_schema.json", files)
            self.assertTrue(files["lakehouse_ddl.sql"].exists())


class TestPipelineGenerator(unittest.TestCase):

    def test_generate_master_pipeline(self):
        pg = PipelineGenerator()
        pipeline = pg.generate_master_pipeline("content_server")
        self.assertEqual(pipeline["name"], "OpenText_Migration")
        self.assertEqual(len(pipeline["properties"]["activities"]), 4)

    def test_generate_ingestion_pipeline(self):
        pg = PipelineGenerator()
        pipeline = pg.generate_ingestion_pipeline("documents", {"endpoint": "/api/v2/nodes"})
        self.assertIn("Ingest_", pipeline["name"])

    def test_generate_incremental_pipeline(self):
        pg = PipelineGenerator()
        pipeline = pg.generate_incremental_pipeline("documents")
        self.assertIn("IncrSync_", pipeline["name"])

    def test_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pg = PipelineGenerator()
            files = pg.export(tmpdir, tables=["documents", "folders"])
            self.assertIn("master_pipeline", files)
            self.assertTrue(len(files) >= 3)


class TestNotebookGenerator(unittest.TestCase):

    def test_generate_extraction_notebook(self):
        nb = NotebookGenerator()
        notebook = nb.generate_extraction_notebook()
        self.assertEqual(notebook["nbformat"], 4)
        self.assertTrue(len(notebook["cells"]) >= 3)

    def test_generate_transform_notebook(self):
        nb = NotebookGenerator()
        notebook = nb.generate_transform_notebook(["documents", "folders"])
        cells = notebook["cells"]
        code_cells = [c for c in cells if c["cell_type"] == "code"]
        self.assertTrue(len(code_cells) >= 3)

    def test_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nb = NotebookGenerator()
            files = nb.export(tmpdir)
            self.assertEqual(len(files), 4)
            for path in files.values():
                self.assertTrue(path.suffix == ".ipynb")


class TestDataflowGenerator(unittest.TestCase):

    def test_generate_rest_dataflow(self):
        df = DataflowGenerator()
        result = df.generate_rest_dataflow("test", "https://api.example.com", "test_table")
        self.assertIn("Dataflow_test", result["name"])

    def test_generate_metadata_dataflow(self):
        df = DataflowGenerator()
        result = df.generate_metadata_dataflow([])
        self.assertEqual(result["name"], "Dataflow_Metadata")

    def test_generate_jdbc_dataflow_oracle(self):
        df = DataflowGenerator()
        conn = {"odaDriverClass": "oracle.jdbc.OracleDriver", "odaURL": "jdbc:oracle:thin:@host:1521:xe"}
        result = df.generate_jdbc_dataflow(conn, "SELECT 1 FROM dual", "test")
        self.assertIn("Oracle.Database", result["properties"]["queries"][0]["query"])


class TestTMDLGenerator(unittest.TestCase):

    def test_add_table_from_dataset(self):
        tmdl = TMDLGenerator()
        dataset = {
            "name": "SalesData",
            "data_source": "DB",
            "query": "SELECT id, name FROM sales",
            "column_hints": [
                {"columnName": "id", "dataType": "integer"},
                {"columnName": "name", "dataType": "string"},
            ],
            "computed_columns": [],
            "result_columns": [],
        }
        table = tmdl.add_table_from_dataset(dataset)
        self.assertEqual(table["name"], "SalesData")
        self.assertEqual(len(table["columns"]), 2)

    def test_add_measure(self):
        tmdl = TMDLGenerator()
        measure = tmdl.add_measure("Sales", "TotalSales", "SUM([Amount])")
        self.assertEqual(measure["name"], "TotalSales")

    def test_generate_tmdl(self):
        tmdl = TMDLGenerator()
        tmdl.add_table_from_dataset({
            "name": "Test", "data_source": "", "query": "",
            "column_hints": [{"columnName": "col1", "dataType": "string"}],
            "computed_columns": [], "result_columns": [],
        })
        files = tmdl.generate_tmdl()
        self.assertIn("model.tmdl", files)
        self.assertIn("tables/Test.tmdl", files)
        self.assertIn("column col1", files["tables/Test.tmdl"])

    def test_infer_relationships(self):
        # Relationships are now inferred from shared column names across the
        # registered tables (not from raw SQL JOIN clauses, which reference
        # base tables that don't become PBI tables).
        tmdl = TMDLGenerator()
        tmdl.add_table_from_dataset({
            "name": "Sales", "data_source": "", "query": "",
            "column_hints": [
                {"columnName": "region", "dataType": "string"},
                {"columnName": "amount", "dataType": "decimal"},
            ],
            "computed_columns": [], "result_columns": [],
        })
        tmdl.add_table_from_dataset({
            "name": "Region", "data_source": "", "query": "",
            "column_hints": [
                {"columnName": "region", "dataType": "string"},
            ],
            "computed_columns": [], "result_columns": [],
        })
        rels = tmdl.infer_relationships([])
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0]["fromColumn"], "region")
        self.assertEqual(rels[0]["toColumn"], "region")

    def test_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmdl = TMDLGenerator()
            tmdl.add_table_from_dataset({
                "name": "T1", "data_source": "", "query": "",
                "column_hints": [{"columnName": "c", "dataType": "string"}],
                "computed_columns": [], "result_columns": [],
            })
            files = tmdl.export(tmpdir)
            self.assertTrue(any("model.tmdl" in str(p) for p in files.values()))


class TestMQueryGenerator(unittest.TestCase):

    def test_oracle_connection(self):
        gen = MQueryGenerator()
        m = gen.generate_from_connection(
            {"odaDriverClass": "oracle.jdbc.OracleDriver", "odaURL": "jdbc:oracle:thin:@host:1521:xe"},
            query="SELECT 1 FROM dual",
        )
        self.assertIn("Oracle.Database", m)

    def test_postgresql_connection(self):
        gen = MQueryGenerator()
        m = gen.generate_from_connection(
            {"odaDriverClass": "org.postgresql.Driver", "odaURL": "jdbc:postgresql://host:5432/mydb"},
        )
        self.assertIn("PostgreSQL.Database", m)

    def test_sqlserver_connection(self):
        gen = MQueryGenerator()
        m = gen.generate_from_connection(
            {"odaDriverClass": "com.microsoft.sqlserver.jdbc.SQLServerDriver", "odaURL": "jdbc:sqlserver://host:1433"},
            query="SELECT 1",
        )
        self.assertIn("Sql.Database", m)

    def test_generate_from_datasets(self):
        gen = MQueryGenerator()
        datasets = [{"name": "ds1", "data_source": "conn1", "query": "SELECT 1"}]
        connections = [{"name": "conn1", "odaDriverClass": "oracle.jdbc.OracleDriver", "odaURL": "jdbc:oracle:thin:@host:1521:xe"}]
        results = gen.generate_from_datasets(datasets, connections)
        self.assertEqual(len(results), 1)
        self.assertIn("Oracle.Database", results[0]["m_query"])


if __name__ == "__main__":
    unittest.main()
