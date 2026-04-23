"""Dataflow Gen2 generator — Power Query M for Fabric ingestion."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .fabric_constants import sanitize_table_name, BIRT_TO_M_TYPE

logger = logging.getLogger(__name__)


class DataflowGenerator:
    """Generates Dataflow Gen2 definitions with Power Query M queries."""

    def __init__(self, lakehouse_name: str = "OpenTextMigration"):
        self.lakehouse_name = sanitize_table_name(lakehouse_name)

    def generate_rest_dataflow(
        self,
        name: str,
        api_url: str,
        table_name: str,
        columns: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Generate a dataflow that ingests from REST API to Lakehouse table."""
        safe_table = sanitize_table_name(table_name)

        m_query = self._build_rest_m_query(api_url, safe_table, columns)

        return {
            "name": f"Dataflow_{name}",
            "properties": {
                "description": f"Ingest {table_name} from OpenText REST to Lakehouse",
                "type": "DataflowGen2",
                "queries": [
                    {
                        "name": safe_table,
                        "query": m_query,
                        "destination": {
                            "type": "Lakehouse",
                            "lakehouse": self.lakehouse_name,
                            "table": safe_table,
                            "loadMode": "Overwrite",
                        },
                    },
                ],
            },
        }

    def generate_metadata_dataflow(
        self,
        metadata: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate dataflow for flattened metadata views."""
        m_query = (
            'let\n'
            '    Source = Json.Document(File.Contents("metadata.json")),\n'
            '    Expanded = Table.FromList(Source, Splitter.SplitByNothing()),\n'
            '    ExpandedRecords = Table.ExpandRecordColumn(Expanded, "Column1",\n'
            '        {"node_id", "categories"}),\n'
            '    ExpandedCategories = Table.ExpandListColumn(ExpandedRecords, "categories"),\n'
            '    FinalExpand = Table.ExpandRecordColumn(ExpandedCategories, "categories",\n'
            '        {"category_name", "attributes"})\n'
            'in\n'
            '    FinalExpand'
        )

        return {
            "name": "Dataflow_Metadata",
            "properties": {
                "description": "Flatten OpenText metadata categories into Lakehouse table",
                "type": "DataflowGen2",
                "queries": [
                    {
                        "name": "metadata_flat",
                        "query": m_query,
                        "destination": {
                            "type": "Lakehouse",
                            "lakehouse": self.lakehouse_name,
                            "table": "metadata",
                            "loadMode": "Overwrite",
                        },
                    },
                ],
            },
        }

    def generate_jdbc_dataflow(
        self,
        connection: dict[str, Any],
        query: str,
        table_name: str,
    ) -> dict[str, Any]:
        """Generate dataflow for BIRT JDBC data source → Lakehouse."""
        safe_table = sanitize_table_name(table_name)
        driver_class = connection.get("odaDriverClass", connection.get("driverClass", ""))
        url = connection.get("odaURL", connection.get("url", ""))
        user = connection.get("odaUser", connection.get("user", ""))

        m_query = self._build_jdbc_m_query(driver_class, url, user, query, safe_table)

        return {
            "name": f"Dataflow_BIRT_{safe_table}",
            "properties": {
                "description": f"BIRT data source → Lakehouse table: {table_name}",
                "type": "DataflowGen2",
                "queries": [
                    {
                        "name": safe_table,
                        "query": m_query,
                        "destination": {
                            "type": "Lakehouse",
                            "lakehouse": self.lakehouse_name,
                            "table": safe_table,
                            "loadMode": "Overwrite",
                        },
                    },
                ],
            },
        }

    def export(
        self,
        output_dir: str | Path,
        dataflows: list[dict[str, Any]] | None = None,
    ) -> dict[str, Path]:
        """Export dataflow definitions to JSON."""
        out = Path(output_dir) / "dataflows"
        out.mkdir(parents=True, exist_ok=True)
        files: dict[str, Path] = {}

        for df in (dataflows or []):
            name = df.get("name", "unnamed")
            path = out / f"{name}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(df, f, indent=2)
            files[name] = path

        logger.info("Exported %d dataflow definitions", len(files))
        return files

    @staticmethod
    def _build_rest_m_query(
        api_url: str,
        table_name: str,
        columns: list[dict[str, str]] | None,
    ) -> str:
        """Build Power Query M for REST API ingestion."""
        col_types = ""
        if columns:
            type_mappings = [
                f'{{"{c["name"]}", {BIRT_TO_M_TYPE.get(c.get("type", "string"), "Text.Type")}}}'
                for c in columns
            ]
            col_types = f',\n    ChangedTypes = Table.TransformColumnTypes(Expanded, {{{", ".join(type_mappings)}}})'

        return (
            'let\n'
            f'    Source = Json.Document(Web.Contents("{api_url}")),\n'
            '    Results = Source[results],\n'
            '    Expanded = Table.FromList(Results, Splitter.SplitByNothing()),\n'
            '    ExpandedRecords = Table.ExpandRecordColumn(Expanded, "Column1", Record.FieldNames(Expanded{0}[Column1]))'
            f'{col_types}\n'
            'in\n'
            f'    {"ChangedTypes" if col_types else "ExpandedRecords"}'
        )

    @staticmethod
    def _build_jdbc_m_query(
        driver_class: str,
        url: str,
        user: str,
        query: str,
        table_name: str,
    ) -> str:
        """Build Power Query M for JDBC/database connection."""
        # Map JDBC drivers to M connectors
        if "oracle" in driver_class.lower():
            return (
                'let\n'
                f'    Source = Oracle.Database("{url}"),\n'
                f'    Query = Value.NativeQuery(Source, "{query.replace(chr(34), chr(34)+chr(34))}")\n'
                'in\n'
                '    Query'
            )
        elif "postgresql" in driver_class.lower():
            # Extract host/db from JDBC URL
            return (
                'let\n'
                f'    Source = PostgreSQL.Database("{url}"),\n'
                f'    Query = Value.NativeQuery(Source, "{query.replace(chr(34), chr(34)+chr(34))}")\n'
                'in\n'
                '    Query'
            )
        elif "sqlserver" in driver_class.lower() or "jtds" in driver_class.lower():
            return (
                'let\n'
                f'    Source = Sql.Database("{url}"),\n'
                f'    Query = Value.NativeQuery(Source, "{query.replace(chr(34), chr(34)+chr(34))}")\n'
                'in\n'
                '    Query'
            )
        else:
            # Generic ODBC fallback
            return (
                'let\n'
                f'    Source = Odbc.Query("DSN={table_name}", "{query.replace(chr(34), chr(34)+chr(34))}")\n'
                'in\n'
                '    Source'
            )
