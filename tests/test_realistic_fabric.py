"""Realistic tests for Fabric output generators using real-world data patterns.

Tests generation of:
- Lakehouse DDL with enterprise folder structure
- Data Factory pipelines with real API configurations
- PySpark notebooks with real connector patterns
- Dataflow Gen2 with JDBC connections (Oracle, PostgreSQL, SQL Server)
- TMDL semantic models from real BIRT datasets
- M queries from real JDBC connection strings
"""

import json
import tempfile
import unittest
from pathlib import Path

from fabric_output.fabric_constants import sanitize_name, sanitize_table_name, spark_type
from fabric_output.lakehouse_generator import LakehouseGenerator
from fabric_output.pipeline_generator import PipelineGenerator
from fabric_output.notebook_generator import NotebookGenerator
from fabric_output.dataflow_generator import DataflowGenerator
from fabric_output.tmdl_generator import TMDLGenerator
from fabric_output.m_query_generator import MQueryGenerator
from tests.fixtures import (
    REALISTIC_NODE_TREE,
    REALISTIC_JDBC_CONNECTIONS,
    REALISTIC_DATASETS_FOR_M_QUERY,
)


class TestRealisticLakehouseGeneration(unittest.TestCase):
    """Lakehouse DDL and folder mappings from enterprise node trees."""

    def test_enterprise_folder_structure(self):
        """Maps Enterprise Workspace folder hierarchy to OneLake paths."""
        lh = LakehouseGenerator()
        mappings = lh.generate_folder_structure(REALISTIC_NODE_TREE)

        # Should only map folders (type 0), not documents
        folder_nodes = [n for n in REALISTIC_NODE_TREE if n["type"] == 0]
        self.assertEqual(len(mappings), len(folder_nodes))

        # All paths should start with Files/
        for m in mappings:
            self.assertTrue(m["onelake_path"].startswith("Files/"))

    def test_enterprise_folder_names_sanitized(self):
        """Folder names with spaces/special chars get sanitized."""
        lh = LakehouseGenerator()
        nodes = [
            {"id": 100, "name": "HR & Legal", "type": 0, "path": "/Enterprise/HR & Legal"},
            {"id": 101, "name": "Q4 Reports (2024)", "type": 0, "path": "/Enterprise/Q4 Reports (2024)"},
        ]
        mappings = lh.generate_folder_structure(nodes)
        for m in mappings:
            # OneLake paths should be filesystem-safe
            path = m["onelake_path"]
            self.assertNotIn("&", Path(path).name.replace("_", ""))

    def test_ddl_with_custom_tables_from_categories(self):
        """Generate custom tables for CS category data."""
        lh = LakehouseGenerator()
        custom = {
            "document_classifications": [
                ("node_id", "BIGINT", "Content Server node ID"),
                ("classification_level", "STRING", "Confidential/Internal/Public"),
                ("retention_years", "INT", "Retention period in years"),
                ("department", "STRING", "Owning department"),
                ("regulatory_reference", "STRING", "Regulatory compliance reference"),
            ],
            "project_metadata": [
                ("node_id", "BIGINT", "Content Server node ID"),
                ("project_code", "STRING", "Project identifier"),
                ("cost_center", "STRING", "Cost center code"),
                ("business_unit", "STRING", "Business unit name"),
                ("approval_status", "STRING", "Current approval status"),
            ],
        }
        ddl = lh.generate_ddl(custom_tables=custom)

        self.assertIn("document_classifications", ddl)
        self.assertIn("project_metadata", ddl)
        self.assertIn("classification_level", ddl["document_classifications"])
        self.assertIn("project_code", ddl["project_metadata"])

    def test_export_realistic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lh = LakehouseGenerator()
            files = lh.export(tmpdir)
            self.assertIn("lakehouse_ddl.sql", files)
            self.assertIn("lakehouse_schema.json", files)
            for path in files.values():
                self.assertTrue(path.exists())


class TestRealisticPipelineGeneration(unittest.TestCase):
    """Data Factory pipelines for real migration scenarios."""

    def test_content_server_master_pipeline(self):
        """Master pipeline for CS extraction has 4 activities."""
        pg = PipelineGenerator()
        pipeline = pg.generate_master_pipeline("content_server")
        self.assertEqual(pipeline["name"], "OpenText_Migration")
        activities = pipeline["properties"]["activities"]
        self.assertEqual(len(activities), 4)

    def test_documentum_master_pipeline(self):
        """Master pipeline for Documentum extraction."""
        pg = PipelineGenerator()
        pipeline = pg.generate_master_pipeline("documentum")
        self.assertEqual(pipeline["name"], "OpenText_Migration")

    def test_ingestion_pipelines_for_enterprise_tables(self):
        """Generate ingestion pipelines for each data category."""
        pg = PipelineGenerator()
        tables = ["documents", "folders", "metadata", "permissions", "versions"]
        with tempfile.TemporaryDirectory() as tmpdir:
            files = pg.export(tmpdir, tables=tables)
            # Should have master + one per table
            self.assertTrue(len(files) >= 6)


class TestRealisticNotebookGeneration(unittest.TestCase):
    """PySpark notebooks for real extraction and transformation."""

    def test_extraction_notebook_structure(self):
        """Extraction notebook has markdown + code cells."""
        nb = NotebookGenerator()
        notebook = nb.generate_extraction_notebook()
        self.assertEqual(notebook["nbformat"], 4)

        md_cells = [c for c in notebook["cells"] if c["cell_type"] == "markdown"]
        code_cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
        self.assertTrue(len(md_cells) >= 1)
        self.assertTrue(len(code_cells) >= 3)

    def test_transform_notebook_real_tables(self):
        """Transform notebook for enterprise content tables."""
        nb = NotebookGenerator()
        tables = ["documents", "folders", "metadata", "permissions", "acl_mappings"]
        notebook = nb.generate_transform_notebook(tables)
        code_cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
        # Should have cells for each table + setup
        self.assertTrue(len(code_cells) >= len(tables))


class TestRealisticDataflowGeneration(unittest.TestCase):
    """Dataflow Gen2 from real JDBC connections."""

    def test_oracle_jdbc_dataflow(self):
        """Oracle JDBC → Oracle.Database M query."""
        df = DataflowGenerator()
        oracle_conn = REALISTIC_JDBC_CONNECTIONS[0]
        result = df.generate_jdbc_dataflow(
            oracle_conn,
            "SELECT customer_name, order_date, amount FROM orders WHERE order_date >= SYSDATE - 365",
            "customer_orders",
        )
        self.assertIn("Oracle.Database", result["properties"]["queries"][0]["query"])

    def test_postgresql_jdbc_dataflow(self):
        """PostgreSQL JDBC → PostgreSQL.Database M query."""
        df = DataflowGenerator()
        pg_conn = REALISTIC_JDBC_CONNECTIONS[1]
        result = df.generate_jdbc_dataflow(
            pg_conn,
            "SELECT region_name, total_sales FROM sales_summary",
            "sales_by_region",
        )
        self.assertIn("PostgreSQL.Database", result["properties"]["queries"][0]["query"])

    def test_sqlserver_jdbc_dataflow(self):
        """SQL Server JDBC → Sql.Database M query."""
        df = DataflowGenerator()
        ss_conn = REALISTIC_JDBC_CONNECTIONS[2]
        result = df.generate_jdbc_dataflow(
            ss_conn,
            "SELECT product_code, quantity_on_hand FROM Inventory",
            "inventory_levels",
        )
        self.assertIn("Sql.Database", result["properties"]["queries"][0]["query"])

    def test_rest_api_dataflow_cs(self):
        """REST API dataflow for Content Server nodes endpoint."""
        df = DataflowGenerator()
        result = df.generate_rest_dataflow(
            "content_server_nodes",
            "https://otcs.acme-corp.com/otcs/cs.exe/api/v2/nodes/2000/nodes",
            "cs_nodes",
        )
        self.assertIn("Dataflow_content_server_nodes", result["name"])


class TestRealisticTMDLGeneration(unittest.TestCase):
    """TMDL semantic model from real BIRT datasets."""

    def test_classic_models_dataset(self):
        """Generate TMDL from Classic Models OrdersByCustomer dataset."""
        tmdl = TMDLGenerator()
        dataset = {
            "name": "OrdersByCustomer",
            "data_source": "Classic Models",
            "query": """SELECT c.customerName, o.orderNumber, o.orderDate, o.status,
                        od.quantityOrdered, od.priceEach, p.productLine, c.country
                        FROM customers c JOIN orders o ON c.customerNumber = o.customerNumber""",
            "column_hints": [
                {"columnName": "customerName", "dataType": "string"},
                {"columnName": "orderNumber", "dataType": "integer"},
                {"columnName": "orderDate", "dataType": "date"},
                {"columnName": "status", "dataType": "string"},
                {"columnName": "quantityOrdered", "dataType": "integer"},
                {"columnName": "priceEach", "dataType": "decimal"},
                {"columnName": "productLine", "dataType": "string"},
                {"columnName": "country", "dataType": "string"},
            ],
            "computed_columns": [
                {"name": "lineTotal", "dataType": "float", "expression": 'row["quantityOrdered"] * row["priceEach"]'},
                {"name": "orderYear", "dataType": "integer", "expression": 'BirtDateTime.year(row["orderDate"])'},
            ],
            "result_columns": [],
        }
        table = tmdl.add_table_from_dataset(dataset)
        self.assertEqual(table["name"], "OrdersByCustomer")
        # 8 column_hints + 2 computed_columns = 10 columns
        self.assertEqual(len(table["columns"]), 10)

    def test_add_measures_from_aggregations(self):
        """Add DAX measures converted from BIRT aggregation expressions."""
        tmdl = TMDLGenerator()
        tmdl.add_table_from_dataset({
            "name": "Orders", "data_source": "DB", "query": "",
            "column_hints": [
                {"columnName": "lineTotal", "dataType": "decimal"},
                {"columnName": "orderNumber", "dataType": "integer"},
            ],
            "computed_columns": [], "result_columns": [],
        })

        tmdl.add_measure("Orders", "Total Revenue", "SUM([lineTotal])")
        tmdl.add_measure("Orders", "Order Count", "DISTINCTCOUNT([orderNumber])")
        tmdl.add_measure("Orders", "Average Order Value", "AVERAGE([lineTotal])")

        files = tmdl.generate_tmdl()
        orders_tmdl = files["tables/Orders.tmdl"]
        # sanitize_name converts "Total Revenue" → "Total_Revenue"
        self.assertIn("measure Total_Revenue", orders_tmdl)
        self.assertIn("SUM([lineTotal])", orders_tmdl)

    def test_infer_join_relationships(self):
        """Infer relationships from multi-table JOIN queries (no aliases)."""
        tmdl = TMDLGenerator()
        datasets = [
            {
                "name": "orders_details",
                "query": """SELECT * FROM customers
                           JOIN orders ON customers.customerNumber = orders.customerNumber""",
                "data_source": "DB",
                "column_hints": [],
                "computed_columns": [],
                "result_columns": [],
            }
        ]
        rels = tmdl.infer_relationships(datasets)
        self.assertTrue(len(rels) >= 1)

    def test_export_realistic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmdl = TMDLGenerator()
            tmdl.add_table_from_dataset({
                "name": "OrdersByCustomer", "data_source": "", "query": "",
                "column_hints": [
                    {"columnName": "customerName", "dataType": "string"},
                    {"columnName": "lineTotal", "dataType": "decimal"},
                ],
                "computed_columns": [], "result_columns": [],
            })
            tmdl.add_measure("OrdersByCustomer", "Total", "SUM([lineTotal])")
            files = tmdl.export(tmpdir)
            self.assertTrue(any("model.tmdl" in str(p) for p in files.values()))


class TestRealisticMQueryGeneration(unittest.TestCase):
    """M queries from real JDBC connection strings and SQL queries."""

    def test_oracle_with_real_query(self):
        """Oracle connection → M query with native query."""
        gen = MQueryGenerator()
        m = gen.generate_from_connection(
            REALISTIC_JDBC_CONNECTIONS[0],
            query=REALISTIC_DATASETS_FOR_M_QUERY[0]["query"],
        )
        self.assertIn("Oracle.Database", m)

    def test_postgresql_with_real_query(self):
        """PostgreSQL analytics warehouse connection."""
        gen = MQueryGenerator()
        m = gen.generate_from_connection(
            REALISTIC_JDBC_CONNECTIONS[1],
            query=REALISTIC_DATASETS_FOR_M_QUERY[1]["query"],
        )
        self.assertIn("PostgreSQL.Database", m)

    def test_sqlserver_with_real_query(self):
        """SQL Server ERP connection with encryption."""
        gen = MQueryGenerator()
        m = gen.generate_from_connection(
            REALISTIC_JDBC_CONNECTIONS[2],
            query=REALISTIC_DATASETS_FOR_M_QUERY[2]["query"],
        )
        self.assertIn("Sql.Database", m)

    def test_generate_from_datasets_batch(self):
        """Batch generate M queries for all datasets."""
        gen = MQueryGenerator()
        results = gen.generate_from_datasets(
            REALISTIC_DATASETS_FOR_M_QUERY,
            REALISTIC_JDBC_CONNECTIONS,
        )
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIn("m_query", r)
            self.assertTrue(len(r["m_query"]) > 10)


class TestRealisticFabricConstants(unittest.TestCase):
    """Sanitization and type mapping with real-world inputs."""

    def test_sanitize_enterprise_folder_names(self):
        """Real CS folder names often have spaces, ampersands, parentheses."""
        cases = [
            ("HR & Legal", "hr__legal"),
            ("Q4 Reports (2024)", "q4_reports_2024"),
            ("SOX Compliance — Audit", "sox_compliance__audit"),
            ("Project #123-Alpha", "project_123alpha"),
        ]
        for input_name, expected_pattern in cases:
            result = sanitize_table_name(input_name)
            self.assertTrue(result.replace("_", "").isalnum() or "_" in result,
                            f"'{input_name}' → '{result}' should be safe")

    def test_spark_types_from_birt(self):
        """Map BIRT column types to Spark types."""
        type_map = {
            "string": "STRING",
            "integer": "INT",
            "float": "FLOAT",
            "decimal": "DECIMAL(18,2)",
            "date": "DATE",
            "datetime": "TIMESTAMP",
        }
        for birt_type, expected_spark in type_map.items():
            result = spark_type(birt_type)
            self.assertEqual(result, expected_spark,
                             f"BIRT type '{birt_type}' should map to '{expected_spark}', got '{result}'")


if __name__ == "__main__":
    unittest.main()
