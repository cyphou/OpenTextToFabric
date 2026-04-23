"""TMDL semantic model generator — tables, columns, measures, relationships."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .fabric_constants import BIRT_TO_TMDL_TYPE, sanitize_name

logger = logging.getLogger(__name__)


class TMDLGenerator:
    """Generates TMDL (Tabular Model Definition Language) semantic model files."""

    def __init__(self, model_name: str = "MigratedModel"):
        self.model_name = model_name
        self.tables: list[dict[str, Any]] = []
        self.relationships: list[dict[str, Any]] = []
        self.measures: list[dict[str, Any]] = []

    def add_table_from_dataset(self, dataset: dict[str, Any]) -> dict[str, Any]:
        """Add a table from a BIRT dataset definition.

        Args:
            dataset: Dataset entry from datasets.json.

        Returns:
            Table definition dict.
        """
        table_name = sanitize_name(dataset.get("name", "Table"))

        columns: list[dict[str, Any]] = []

        # From result columns / column hints
        for col in dataset.get("result_columns", []):
            columns.append({
                "name": sanitize_name(col.get("name", col.get("columnName", ""))),
                "dataType": BIRT_TO_TMDL_TYPE.get(
                    col.get("dataType", "string").lower(), "string"
                ),
                "sourceColumn": col.get("name", col.get("columnName", "")),
                "isHidden": False,
            })

        for hint in dataset.get("column_hints", []):
            col_name = hint.get("columnName", hint.get("name", ""))
            if col_name and not any(c["name"] == sanitize_name(col_name) for c in columns):
                columns.append({
                    "name": sanitize_name(col_name),
                    "dataType": BIRT_TO_TMDL_TYPE.get(
                        hint.get("dataType", "string").lower(), "string"
                    ),
                    "sourceColumn": col_name,
                    "displayName": hint.get("displayName", ""),
                    "isHidden": False,
                })

        # Computed columns → calculated columns
        for cc in dataset.get("computed_columns", []):
            col_name = cc.get("name", "")
            if col_name:
                columns.append({
                    "name": sanitize_name(col_name),
                    "dataType": BIRT_TO_TMDL_TYPE.get(
                        cc.get("dataType", "string").lower(), "string"
                    ),
                    "type": "calculated",
                    "expression": cc.get("expression", ""),
                    "isHidden": False,
                })

        table = {
            "name": table_name,
            "columns": columns,
            "source_dataset": dataset.get("name", ""),
            "source_query": dataset.get("query", ""),
            "data_source": dataset.get("data_source", ""),
        }
        self.tables.append(table)
        return table

    def add_measure(
        self,
        table_name: str,
        measure_name: str,
        dax_expression: str,
        format_string: str = "",
        display_folder: str = "",
    ) -> dict[str, Any]:
        """Add a DAX measure to a table."""
        measure = {
            "table": sanitize_name(table_name),
            "name": sanitize_name(measure_name),
            "expression": dax_expression,
            "formatString": format_string,
            "displayFolder": display_folder,
        }
        self.measures.append(measure)
        return measure

    def infer_relationships(
        self,
        datasets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Infer relationships from SQL JOIN clauses in dataset queries."""
        for ds in datasets:
            query = ds.get("query", "").upper()
            if " JOIN " not in query:
                continue

            # Simple pattern: FROM table1 JOIN table2 ON table1.col = table2.col
            import re
            join_pattern = re.compile(
                r"(\w+)\s+JOIN\s+(\w+)\s+ON\s+(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)",
                re.IGNORECASE,
            )
            for match in join_pattern.finditer(ds.get("query", "")):
                from_table = match.group(1)
                to_table = match.group(2)
                from_col = match.group(4)
                to_col = match.group(6)

                rel = {
                    "name": f"rel_{sanitize_name(from_table)}_{sanitize_name(to_table)}",
                    "fromTable": sanitize_name(from_table),
                    "fromColumn": sanitize_name(from_col),
                    "toTable": sanitize_name(to_table),
                    "toColumn": sanitize_name(to_col),
                    "crossFilteringBehavior": "oneDirection",
                    "cardinality": "manyToOne",
                }
                self.relationships.append(rel)

        logger.info("Inferred %d relationships from SQL joins", len(self.relationships))
        return self.relationships

    def generate_tmdl(self) -> dict[str, str]:
        """Generate TMDL content for each table.

        Returns dict of {filename: tmdl_content}.
        """
        files: dict[str, str] = {}

        # Model definition
        model_tmdl = f'model Model\n    culture: en-US\n'
        files["model.tmdl"] = model_tmdl

        # Tables
        for table in self.tables:
            tmdl = self._table_to_tmdl(table)
            files[f"tables/{table['name']}.tmdl"] = tmdl

        # Relationships
        if self.relationships:
            rel_tmdl = ""
            for rel in self.relationships:
                rel_tmdl += (
                    f"\nrelationship {rel['name']}\n"
                    f"    fromColumn: {rel['fromTable']}.{rel['fromColumn']}\n"
                    f"    toColumn: {rel['toTable']}.{rel['toColumn']}\n"
                    f"    crossFilteringBehavior: {rel['crossFilteringBehavior']}\n"
                )
            files["relationships.tmdl"] = rel_tmdl

        return files

    def _table_to_tmdl(self, table: dict[str, Any]) -> str:
        """Convert table definition to TMDL format."""
        lines = [f"table {table['name']}"]
        lines.append(f"    lineageTag: {table['name']}")
        lines.append("")

        # Columns
        for col in table.get("columns", []):
            col_type = col.get("type", "")
            if col_type == "calculated":
                lines.append(f"    column {col['name']} =")
                lines.append(f"        {col.get('expression', '')}")
            else:
                lines.append(f"    column {col['name']}")
            lines.append(f"        dataType: {col.get('dataType', 'string')}")
            if col.get("sourceColumn"):
                lines.append(f"        sourceColumn: {col['sourceColumn']}")
            if col.get("isHidden"):
                lines.append("        isHidden")
            if col.get("displayName"):
                lines.append(f"        displayName: {col['displayName']}")
            lines.append(f"        lineageTag: {col['name']}")
            lines.append("")

        # Measures for this table
        table_measures = [m for m in self.measures if m["table"] == table["name"]]
        for m in table_measures:
            lines.append(f"    measure {m['name']} =")
            lines.append(f"        {m['expression']}")
            if m.get("formatString"):
                lines.append(f"        formatString: {m['formatString']}")
            if m.get("displayFolder"):
                lines.append(f"        displayFolder: {m['displayFolder']}")
            lines.append(f"        lineageTag: {m['name']}")
            lines.append("")

        # Partition (M query source)
        if table.get("source_query"):
            lines.append(f"    partition {table['name']}")
            lines.append("        mode: import")
            lines.append(f"        source = m")
            lines.append(f'            let')
            lines.append(f'                Source = #"{table.get("data_source", "Source")}"')
            lines.append(f'            in')
            lines.append(f'                Source')
            lines.append("")

        return "\n".join(lines)

    def export(self, output_dir: str | Path) -> dict[str, Path]:
        """Export TMDL files to directory."""
        model_dir = Path(output_dir) / f"{self.model_name}.SemanticModel"
        out = model_dir / "definition"
        out.mkdir(parents=True, exist_ok=True)
        files: dict[str, Path] = {}

        tmdl_files = self.generate_tmdl()

        for filename, content in tmdl_files.items():
            path = out / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            files[filename] = path

        # .platform file (required by PBI Desktop)
        platform = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {
                "type": "SemanticModel",
                "displayName": self.model_name,
            },
            "config": {
                "version": "2.0",
                "logicalId": str(__import__("uuid").uuid4()),
            },
        }
        platform_path = model_dir / ".platform"
        with open(platform_path, "w", encoding="utf-8") as f:
            json.dump(platform, f, indent=2)
        files[".platform"] = platform_path

        # definition.pbism
        pbism = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.0",
            "settings": {},
        }
        pbism_path = model_dir / "definition.pbism"
        with open(pbism_path, "w", encoding="utf-8") as f:
            json.dump(pbism, f, indent=2)
        files["definition.pbism"] = pbism_path

        logger.info(
            "Exported TMDL: %d tables, %d relationships, %d measures",
            len(self.tables), len(self.relationships), len(self.measures),
        )
        return files
