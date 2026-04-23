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
        # Data source connections keyed by source name
        self.data_sources: dict[str, dict[str, Any]] = {}

    def add_data_sources(self, connections: list[dict[str, Any]]) -> None:
        """Register data source connections so shared M expressions can be emitted."""
        for conn in connections or []:
            name = conn.get("name")
            if name:
                self.data_sources[sanitize_name(name)] = conn

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
                    "expression": self._birt_js_to_dax(cc.get("expression", "")),
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
        """Add a DAX measure to a table.

        Skips if a column with the same name already exists on the table
        (Power BI forbids duplicate names between columns and measures).
        """
        safe_table = sanitize_name(table_name)
        safe_name = sanitize_name(measure_name)

        # Check for column name conflict
        for t in self.tables:
            if t["name"] == safe_table:
                if any(c["name"] == safe_name for c in t.get("columns", [])):
                    logger.warning(
                        "Skipping measure '%s' — column with same name exists on '%s'",
                        safe_name, safe_table,
                    )
                    return {}

        measure = {
            "table": safe_table,
            "name": safe_name,
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
        """Infer relationships between *imported tables* using shared column names.

        SQL JOIN clauses reference base tables (e.g. orders/regions) that are not
        modeled as PBI tables — only the dataset result-sets become tables. The
        only reliable signal across them is shared column names. We pick a
        candidate FK when a column exists in two different tables and at least
        one of them looks like a dimension (smaller cardinality / lookup).
        """
        # Build column -> [tables] index from the registered tables
        col_to_tables: dict[str, list[str]] = {}
        for tbl in self.tables:
            for col in tbl.get("columns", []):
                if col.get("type") == "calculated":
                    continue
                col_to_tables.setdefault(col["name"], []).append(tbl["name"])

        seen: set[tuple[str, str, str]] = set()
        for col_name, tables in col_to_tables.items():
            if len(tables) < 2:
                continue
            # Treat the *smaller* table (fewer columns) as the dimension side
            ranked = sorted(
                tables,
                key=lambda n: len(next(
                    (t["columns"] for t in self.tables if t["name"] == n), []
                )),
            )
            dim_table = ranked[0]
            for fact_table in ranked[1:]:
                key = (fact_table, dim_table, col_name)
                if key in seen:
                    continue
                seen.add(key)
                self.relationships.append({
                    "name": f"rel_{fact_table}_{dim_table}_{col_name}",
                    "fromTable": fact_table,
                    "fromColumn": col_name,
                    "toTable": dim_table,
                    "toColumn": col_name,
                    "crossFilteringBehavior": "oneDirection",
                    "cardinality": "manyToOne",
                })

        logger.info("Inferred %d relationships from shared columns", len(self.relationships))
        return self.relationships

    def generate_tmdl(self) -> dict[str, str]:
        """Generate TMDL content for each table.

        Returns dict of {filename: tmdl_content}.
        """
        files: dict[str, str] = {}

        # Model definition — declare expressions/tables references implicitly
        model_tmdl = 'model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tdiscourageImplicitMeasures\n'
        files["model.tmdl"] = model_tmdl

        # Shared expressions (one per data source) — partitions reference these
        if self.data_sources:
            files["expressions.tmdl"] = self._build_expressions_tmdl()

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
                    f"\tfromColumn: {rel['fromTable']}.{rel['fromColumn']}\n"
                    f"\ttoColumn: {rel['toTable']}.{rel['toColumn']}\n"
                    f"\tcrossFilteringBehavior: {rel['crossFilteringBehavior']}\n"
                )
            files["relationships.tmdl"] = rel_tmdl

        return files

    def _build_expressions_tmdl(self) -> str:
        """Generate shared M expressions for each data source.

        Maps known driver classes to PBI connectors. Falls back to a literal
        sample table so the model still loads when the source can't be reached.
        """
        lines: list[str] = []
        for src_name, conn in self.data_sources.items():
            driver = (conn.get("odaDriverClass") or "").lower()
            url = conn.get("odaURL") or ""
            m_expr = self._build_source_m(driver, url, src_name)
            quoted = self._quote_name(src_name)
            # Multi-line M body must be fenced with triple backticks in TMDL
            lines.append(f"expression {quoted} = ```")
            for ln in m_expr.split("\n"):
                lines.append(f"\t\t{ln}")
            lines.append("\t\t```")
            lines.append(f"\tlineageTag: {src_name}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _build_source_m(driver: str, url: str, name: str) -> str:
        """Map a JDBC connection to an M source expression."""
        import re
        if "oracle" in driver:
            # jdbc:oracle:thin:@host:port:SID  OR  @host:port/SERVICE
            m = re.search(r"@([^:/?#]+)(?::(\d+))?[:/]([\w.]+)", url)
            if m:
                host, port, sid = m.group(1), m.group(2) or "1521", m.group(3)
                return f'Oracle.Database("{host}:{port}/{sid}", [HierarchicalNavigation=true])'
        if "sqlserver" in driver or "mssql" in driver:
            m = re.search(r"//([^:/?#;]+)(?::(\d+))?[/;]?(?:databaseName=)?([\w.]+)?", url)
            if m:
                host = m.group(1)
                db = m.group(3) or "master"
                return f'Sql.Database("{host}", "{db}")'
        if "postgres" in driver:
            m = re.search(r"//([^:/?#]+)(?::(\d+))?/([\w.]+)", url)
            if m:
                host, port, db = m.group(1), m.group(2) or "5432", m.group(3)
                return f'PostgreSQL.Database("{host}:{port}", "{db}")'
        # Fallback: empty literal table — loads cleanly so the model isn't broken
        return '#table({}, {})'

    @staticmethod
    def _quote_name(name: str) -> str:
        """Quote a TMDL name if it contains special characters."""
        if any(c in name for c in " ./-()'+@#$%^&*!~`<>?;:{}|\\,"):
            return f"'{name}'"
        return name

    @staticmethod
    def _birt_js_to_dax(expr: str) -> str:
        """Translate simple BIRT JavaScript expressions to DAX.

        Handles `row["col"]` / `row['col']` / `row.col` -> `[col]` and the
        common JS operators that map 1:1 to DAX. Anything that doesn't match
        is returned unchanged so the user can fix it in PBI.
        """
        import re
        if not expr:
            return expr
        out = expr
        out = re.sub(r"row\[\s*[\"']([\w]+)[\"']\s*\]", r"[\1]", out)
        out = re.sub(r"\brow\.([A-Za-z_]\w*)", r"[\1]", out)
        # Common JS string ops -> DAX
        out = out.replace(" && ", " && ").replace(" || ", " || ")
        return out

    def _table_to_tmdl(self, table: dict[str, Any]) -> str:
        """Convert table definition to TMDL format."""
        tname = self._quote_name(table['name'])
        lines = [f"table {tname}"]
        lines.append(f"\tlineageTag: {table['name']}")
        lines.append("")

        # Columns
        for col in table.get("columns", []):
            cname = self._quote_name(col['name'])
            col_type = col.get("type", "")
            if col_type == "calculated":
                expr = col.get('expression', '')
                if '\n' in expr:
                    lines.append(f"\tcolumn {cname} = ```")
                    for expr_line in expr.split('\n'):
                        lines.append(f"\t\t\t{expr_line}")
                    lines.append("\t\t\t```")
                else:
                    lines.append(f"\tcolumn {cname} = {expr}")
            else:
                lines.append(f"\tcolumn {cname}")
            lines.append(f"\t\tdataType: {col.get('dataType', 'string')}")
            if col.get("sourceColumn") and col_type != "calculated":
                lines.append(f"\t\tsourceColumn: {col['sourceColumn']}")
            if col.get("isHidden"):
                lines.append("\t\tisHidden")
            if col.get("displayName"):
                lines.append(f"\t\tdisplayName: {col['displayName']}")
            lines.append(f"\t\tlineageTag: {col['name']}")
            lines.append(f"\t\tsummarizeBy: none")
            lines.append("")

        # Measures for this table
        table_measures = [m for m in self.measures if m["table"] == table["name"]]
        for m in table_measures:
            mname = self._quote_name(m['name'])
            expr = m['expression']
            if '\n' in expr:
                lines.append(f"\tmeasure {mname} = ```")
                for expr_line in expr.split('\n'):
                    lines.append(f"\t\t\t{expr_line}")
                lines.append("\t\t\t```")
            else:
                lines.append(f"\tmeasure {mname} = {expr}")
            if m.get("formatString"):
                lines.append(f"\t\tformatString: {m['formatString']}")
            if m.get("displayFolder"):
                lines.append(f"\t\tdisplayFolder: {m['displayFolder']}")
            lines.append(f"\t\tlineageTag: {m['name']}")
            lines.append("")

        # Partition (M query source) — multi-line M MUST be triple-backtick fenced
        ds_name = table.get("data_source", "Source") or "Source"
        part_name = self._quote_name(table['name'])
        lines.append(f"\tpartition {part_name} = m")
        lines.append("\t\tmode: import")
        lines.append("\t\tsource = ```")
        lines.append("\t\t\t\tlet")
        lines.append(f'\t\t\t\t\tSource = #"{ds_name}"')
        if table.get("source_query"):
            # Add native query step if SQL is available
            sql = table['source_query'].replace('"', '""').replace('\n', ' ')
            lines.append(f'\t\t\t\t\tQuery = Value.NativeQuery(Source, "{sql}", null, [EnableFolding=true])')
            lines.append("\t\t\t\tin")
            lines.append("\t\t\t\t\tQuery")
        else:
            lines.append("\t\t\t\tin")
            lines.append("\t\t\t\t\tSource")
        lines.append("\t\t\t\t```")
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
