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
        self.hierarchies: list[dict[str, Any]] = []
        self.roles: list[dict[str, Any]] = []
        self.calculation_groups: list[dict[str, Any]] = []
        # Data source connections keyed by source name
        self.data_sources: dict[str, dict[str, Any]] = {}
        # Real M query expressions keyed by table name (from MQueryGenerator)
        self._partition_m_queries: dict[str, str] = {}

    def add_data_sources(self, connections: list[dict[str, Any]]) -> None:
        """Register data source connections so shared M expressions can be emitted."""
        for conn in connections or []:
            name = conn.get("name")
            if name:
                self.data_sources[sanitize_name(name)] = conn

    def set_partition_m_queries(
        self,
        m_query_results: list[dict[str, Any]],
    ) -> None:
        """Set real Power Query M expressions for table partitions.

        Args:
            m_query_results: Output of ``MQueryGenerator.generate_from_datasets()``,
                each containing ``dataset_name`` and ``m_query``.
        """
        for entry in m_query_results:
            table_name = sanitize_name(entry.get("dataset_name", ""))
            m_query = entry.get("m_query", "")
            if table_name and m_query and not m_query.startswith("//"):
                self._partition_m_queries[table_name] = m_query

    def add_table_from_dataset(self, dataset: dict[str, Any]) -> dict[str, Any]:
        """Add a table from a BIRT dataset definition.

        Args:
            dataset: Dataset entry from datasets.json.

        Returns:
            Table definition dict.
        """
        table_name = sanitize_name(dataset.get("name", "Table"))

        columns: list[dict[str, Any]] = []

        # Collect computed column names — BIRT lists them in both
        # result_columns and computed_columns.  Skip them from
        # result_columns so they are added only once (as regular
        # sourceColumn-based columns — the M query generator adds
        # Table.AddColumn steps for them in Power Query).
        computed_names: set[str] = set()
        for cc in dataset.get("computed_columns", []):
            col_name = cc.get("name", "")
            if col_name:
                computed_names.add(sanitize_name(col_name))

        # From result columns / column hints — skip computed columns
        seen_names: set[str] = set()
        for col in dataset.get("result_columns", []):
            col_safe = sanitize_name(col.get("name", col.get("columnName", "")))
            if col_safe in seen_names or col_safe in computed_names:
                continue
            seen_names.add(col_safe)
            columns.append({
                "name": col_safe,
                "dataType": BIRT_TO_TMDL_TYPE.get(
                    col.get("dataType", "string").lower(), "string"
                ),
                "sourceColumn": col.get("name", col.get("columnName", "")),
                "isHidden": False,
            })

        for hint in dataset.get("column_hints", []):
            col_name = hint.get("columnName", hint.get("name", ""))
            col_safe = sanitize_name(col_name) if col_name else ""
            if col_safe and col_safe not in seen_names and col_safe not in computed_names:
                seen_names.add(col_safe)
                columns.append({
                    "name": sanitize_name(col_name),
                    "dataType": BIRT_TO_TMDL_TYPE.get(
                        hint.get("dataType", "string").lower(), "string"
                    ),
                    "sourceColumn": col_name,
                    "displayName": hint.get("displayName", ""),
                    "isHidden": False,
                })

        # Computed columns → regular sourceColumn columns.
        # The M query generator produces them via Table.AddColumn.
        for cc in dataset.get("computed_columns", []):
            col_name = cc.get("name", "")
            col_safe = sanitize_name(col_name) if col_name else ""
            if col_safe and col_safe not in seen_names:
                seen_names.add(col_safe)
                columns.append({
                    "name": sanitize_name(col_name),
                    "dataType": BIRT_TO_TMDL_TYPE.get(
                        cc.get("dataType", "string").lower(), "string"
                    ),
                    "sourceColumn": col_name,
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

    def add_hierarchy(
        self,
        table_name: str,
        hierarchy_name: str,
        levels: list[str],
        display_folder: str = "",
    ) -> dict[str, Any]:
        """Add a hierarchy to a table.

        Args:
            table_name: Table containing the hierarchy columns.
            hierarchy_name: Display name for the hierarchy.
            levels: Ordered list of column names (top → bottom).
            display_folder: Optional display folder for organization.
        """
        h = {
            "table": sanitize_name(table_name),
            "name": sanitize_name(hierarchy_name),
            "levels": [sanitize_name(l) for l in levels],
            "displayFolder": display_folder,
        }
        self.hierarchies.append(h)
        return h

    def add_role(
        self,
        role_name: str,
        table_filters: dict[str, str],
        description: str = "",
    ) -> dict[str, Any]:
        """Add an RLS (Row-Level Security) role.

        Args:
            role_name: Name of the security role.
            table_filters: Dict of {table_name: dax_filter_expression}.
            description: Optional role description.
        """
        role = {
            "name": sanitize_name(role_name),
            "description": description,
            "tablePermissions": [
                {"table": sanitize_name(t), "filterExpression": expr}
                for t, expr in table_filters.items()
            ],
        }
        self.roles.append(role)
        return role

    def add_calculation_group(
        self,
        name: str,
        items: list[dict[str, str]],
        precedence: int = 0,
    ) -> dict[str, Any]:
        """Add a calculation group.

        Args:
            name: Calculation group table name.
            items: List of dicts with 'name' and 'expression' keys.
            precedence: Evaluation order precedence.
        """
        cg = {
            "name": sanitize_name(name),
            "items": [
                {"name": sanitize_name(i["name"]), "expression": i["expression"]}
                for i in items
            ],
            "precedence": precedence,
        }
        self.calculation_groups.append(cg)
        return cg

    def infer_hierarchies(self) -> list[dict[str, Any]]:
        """Auto-detect hierarchies from common column name patterns.

        Detects patterns like Year→Quarter→Month→Day, Country→State→City,
        Category→SubCategory.
        """
        hierarchy_patterns = [
            ("Date Hierarchy", ["Year", "Quarter", "Month", "Day"]),
            ("Date Hierarchy", ["ANNEE", "MOIS", "JOUR"]),
            ("Date Hierarchy", ["Year", "Month", "Day"]),
            ("Geography", ["Country", "State", "City"]),
            ("Geography", ["Region", "Department", "City"]),
            ("Geography", ["PAYS", "REGION", "VILLE"]),
            ("Category", ["Category", "SubCategory"]),
            ("Category", ["CATEGORIE", "SOUS_CATEGORIE"]),
            ("Organization", ["Division", "Department", "Team"]),
        ]

        for table in self.tables:
            col_names = {c["name"] for c in table.get("columns", [])}
            col_names_lower = {c.lower() for c in col_names}

            for hier_name, pattern in hierarchy_patterns:
                matched = [p for p in pattern if p.lower() in col_names_lower]
                if len(matched) >= 2:
                    # Get actual column names (preserve case)
                    actual = []
                    for p in pattern:
                        for c in col_names:
                            if c.lower() == p.lower():
                                actual.append(c)
                                break
                    if len(actual) >= 2:
                        self.add_hierarchy(table["name"], hier_name, actual)

        logger.info("Inferred %d hierarchies", len(self.hierarchies))
        return self.hierarchies

    def add_rls_from_acl(self, acl_roles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Generate RLS roles from ACL mappings.

        Args:
            acl_roles: List of role dicts with 'name' and 'filters' (table→expression).
        """
        for acl_role in acl_roles:
            self.add_role(
                role_name=acl_role.get("name", "Role"),
                table_filters=acl_role.get("filters", {}),
                description=acl_role.get("description", "Auto-generated from ACL"),
            )
        return self.roles

    def infer_relationships(
        self,
        datasets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Infer relationships between *imported tables* using shared column names.

        SQL JOIN clauses reference base tables (e.g. orders/regions) that are not
        modeled as PBI tables — only the dataset result-sets become tables. The
        only reliable signal across them is shared column names.

        Power BI only allows **one active relationship** per table pair. When
        multiple columns match between two tables, we pick the best candidate
        using a priority heuristic:
          1. Columns whose name ends with ``_id`` or ``id`` (likely a key).
          2. Columns whose name ends with ``_code`` or ``code``.
          3. The first shared column alphabetically (deterministic fallback).
        """
        # Build column -> [tables] index from the registered tables
        col_to_tables: dict[str, list[str]] = {}
        for tbl in self.tables:
            for col in tbl.get("columns", []):
                if col.get("type") == "calculated":
                    continue
                col_to_tables.setdefault(col["name"], []).append(tbl["name"])

        # Group shared columns by (fact, dim) table pair
        pair_candidates: dict[tuple[str, str], list[str]] = {}
        for col_name, tables in col_to_tables.items():
            if len(tables) < 2:
                continue
            ranked = sorted(
                tables,
                key=lambda n: len(next(
                    (t["columns"] for t in self.tables if t["name"] == n), []
                )),
            )
            dim_table = ranked[0]
            for fact_table in ranked[1:]:
                pair_key = (fact_table, dim_table)
                pair_candidates.setdefault(pair_key, []).append(col_name)

        # Pick one column per pair — prefer _id / id, then _code / code
        def _col_priority(name: str) -> tuple[int, str]:
            lower = name.lower()
            if lower.endswith("_id") or lower == "id":
                return (0, lower)
            if lower.endswith("_code") or lower == "code":
                return (1, lower)
            return (2, lower)

        for (fact_table, dim_table), candidates in pair_candidates.items():
            best = sorted(candidates, key=_col_priority)[0]
            self.relationships.append({
                "name": f"rel_{fact_table}_{dim_table}_{best}",
                "fromTable": fact_table,
                "fromColumn": best,
                "toTable": dim_table,
                "toColumn": best,
                "crossFilteringBehavior": "oneDirection",
                "cardinality": "manyToOne",
                "isActive": True,
            })

        # Deactivate relationships that create ambiguous paths.
        # Power BI forbids two active paths between any pair of tables.
        self._deactivate_ambiguous_paths()

        logger.info("Inferred %d relationships from shared columns", len(self.relationships))
        return self.relationships

    def _deactivate_ambiguous_paths(self) -> None:
        """Detect and deactivate relationships that create ambiguous paths.

        An ambiguous path exists when table A can reach table B via two
        different active paths (e.g. A→B directly AND A→C→B). When
        detected, the *direct* shortcut edge is deactivated because the
        transitive path usually carries more semantic meaning (dimension
        chain).
        """
        # Build adjacency list from active relationships (undirected for
        # reachability — PBI considers paths regardless of direction).
        from collections import deque

        active = [r for r in self.relationships if r.get("isActive", True)]

        def _can_reach(src: str, dst: str, excluded_rel_name: str) -> bool:
            """BFS reachability check excluding one relationship."""
            adj: dict[str, list[str]] = {}
            for r in active:
                if r["name"] == excluded_rel_name:
                    continue
                if not r.get("isActive", True):
                    continue
                adj.setdefault(r["fromTable"], []).append(r["toTable"])
                adj.setdefault(r["toTable"], []).append(r["fromTable"])
            visited: set[str] = set()
            queue: deque[str] = deque([src])
            visited.add(src)
            while queue:
                node = queue.popleft()
                if node == dst:
                    return True
                for neighbor in adj.get(node, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            return False

        deactivated = 0
        for rel in self.relationships:
            if not rel.get("isActive", True):
                continue
            # If removing this edge still leaves a path, it's redundant
            if _can_reach(rel["fromTable"], rel["toTable"], rel["name"]):
                rel["isActive"] = False
                deactivated += 1
                logger.info(
                    "Deactivated ambiguous relationship %s (%s → %s)",
                    rel["name"], rel["fromTable"], rel["toTable"],
                )
        if deactivated:
            logger.info("Deactivated %d ambiguous relationships", deactivated)

    def generate_tmdl(self) -> dict[str, str]:
        """Generate TMDL content for each table.

        Returns dict of {filename: tmdl_content}.
        """
        files: dict[str, str] = {}

        # Model definition
        model_tmdl = 'model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tdiscourageImplicitMeasures\n'
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
                    f"\tfromColumn: {rel['fromTable']}.{rel['fromColumn']}\n"
                    f"\ttoColumn: {rel['toTable']}.{rel['toColumn']}\n"
                    f"\tcrossFilteringBehavior: {rel['crossFilteringBehavior']}\n"
                )
                if not rel.get("isActive", True):
                    rel_tmdl += "\tisActive: false\n"
            files["relationships.tmdl"] = rel_tmdl

        # Roles (RLS)
        if self.roles:
            roles_tmdl = ""
            for role in self.roles:
                roles_tmdl += f"\nrole {self._quote_name(role['name'])}\n"
                if role.get("description"):
                    roles_tmdl += f"\tdescription: {role['description']}\n"
                roles_tmdl += "\tmodelPermission: read\n"
                for tp in role.get("tablePermissions", []):
                    roles_tmdl += f"\n\ttablePermission {self._quote_name(tp['table'])}\n"
                    roles_tmdl += f"\t\tfilterExpression = {tp['filterExpression']}\n"
            files["roles.tmdl"] = roles_tmdl

        # Calculation groups
        for cg in self.calculation_groups:
            cg_tmdl = f"table {self._quote_name(cg['name'])}\n"
            cg_tmdl += "\tlineageTag: calculationGroup\n"
            cg_tmdl += f"\n\tcalculationGroup\n"
            cg_tmdl += f"\t\tprecedence: {cg.get('precedence', 0)}\n"
            for item in cg.get("items", []):
                cg_tmdl += f"\n\t\tcalculationItem {self._quote_name(item['name'])}\n"
                cg_tmdl += f"\t\t\texpression = {item['expression']}\n"
            files[f"tables/{cg['name']}.tmdl"] = cg_tmdl

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

        Handles ``row["col"]`` / ``row['col']`` / ``row.col`` →  ``[col]``
        and common JS operators that map 1:1 to DAX.  Anything that doesn't
        match is returned unchanged so the user can fix it in PBI.
        """
        import re
        if not expr:
            return expr
        out = expr
        # row["Column Name"] or row['Column Name'] — allow any chars inside quotes
        out = re.sub(r'row\[\s*"([^"]+)"\s*\]', r"[\1]", out)
        out = re.sub(r"row\[\s*'([^']+)'\s*\]", r"[\1]", out)
        out = re.sub(r"\brow\.([A-Za-z_]\w*)", r"[\1]", out)
        # JS null → BLANK()
        out = re.sub(r"\bnull\b", "BLANK()", out)
        # JS != → DAX <>
        out = out.replace("!=", "<>")
        # JS && → DAX &&, JS || → DAX || (same in DAX)
        return out

    # M type tokens for #table column type list
    _DTYPE_TO_M: dict[str, str] = {
        "string": "Text.Type",
        "int64": "Int64.Type",
        "double": "Number.Type",
        "decimal": "Decimal.Type",
        "dateTime": "DateTime.Type",
        "boolean": "Logical.Type",
    }

    @classmethod
    def _build_partition_m(cls, table: dict[str, Any]) -> str:
        """Build a single-line, self-contained M expression for a partition.

        Emits a `#table` literal with the table's typed schema and an empty
        row set so the model loads cleanly in PBI Desktop without requiring
        any external connection. Users can replace this with the real
        connector after opening the project.
        """
        cols: list[str] = []
        for col in table.get("columns", []):
            if col.get("type") == "calculated":
                continue  # calculated cols come from DAX, not the partition
            name = col.get("sourceColumn") or col["name"]
            m_type = cls._DTYPE_TO_M.get(col.get("dataType", "string"), "Text.Type")
            cols.append(f'#"{name}" = {m_type}')
        if not cols:
            return '#table({}, {})'
        type_list = ", ".join(cols)
        return f'#table(type table [{type_list}], {{}})'

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

        # Hierarchies for this table
        table_hierarchies = [h for h in self.hierarchies if h["table"] == table["name"]]
        for h in table_hierarchies:
            hname = self._quote_name(h['name'])
            lines.append(f"\thierarchy {hname}")
            if h.get("displayFolder"):
                lines.append(f"\t\tdisplayFolder: {h['displayFolder']}")
            lines.append(f"\t\tlineageTag: {h['name']}")
            lines.append("")
            for i, level in enumerate(h["levels"]):
                lname = self._quote_name(level)
                lines.append(f"\t\tlevel {lname}")
                lines.append(f"\t\t\tordinal: {i}")
                lines.append(f"\t\t\tcolumn: {lname}")
                lines.append(f"\t\t\tlineageTag: {h['name']}_{level}")
                lines.append("")

        # Partition (M query source).
        # If a real M query was provided via set_partition_m_queries(), use it
        # with triple-backtick fencing for multi-line expressions. Otherwise
        # fall back to a self-contained #table literal so the model always
        # loads in PBI Desktop.
        part_name = self._quote_name(table['name'])
        real_m = self._partition_m_queries.get(table['name'], "")
        if real_m and "\n" in real_m:
            # Multi-line M expression — use triple-backtick fence
            # try/otherwise MUST be inside the fence so TMDL parser
            # treats the entire block as one M expression.
            lines.append(f"\tpartition {part_name} = m")
            lines.append("\t\tmode: import")
            lines.append("\t\tsource =```")
            lines.append("\t\t\ttry")
            for m_line in real_m.split("\n"):
                lines.append(f"\t\t\t\t{m_line}")
            lines.append("\t\t\totherwise")
            lines.append("\t\t\t\t#table({}, {})")
            lines.append("\t\t\t```")
        elif real_m:
            # Single-line M expression
            lines.append(f"\tpartition {part_name} = m")
            lines.append("\t\tmode: import")
            lines.append(f"\t\tsource = {real_m}")
        else:
            # Fallback: empty #table literal
            m_expr = self._build_partition_m(table)
            lines.append(f"\tpartition {part_name} = m")
            lines.append("\t\tmode: import")
            lines.append(f"\t\tsource = {m_expr}")
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
