"""Artifact healer — auto-fix DAX, TMDL, M queries, and PBIR to ensure PBI Desktop opens cleanly.

Runs after PBIP generation and before final validation. Each repair is
recorded in a RecoveryReport for audit. The healer is deterministic
(no LLM) and conservative: it only fixes issues that are known to
prevent PBI Desktop from loading.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from .recovery_report import RecoveryReport

logger = logging.getLogger(__name__)


class ArtifactHealer:
    """Scans a generated .pbip project and applies auto-fixes.

    Fix categories:
      1. **DAX** — balanced parentheses, BIRT function leaks, unresolved
         row[] references, empty expressions, circular self-references.
      2. **TMDL** — duplicate columns, orphan measures, missing lineageTag,
         partition M wrapping, data-type normalisation.
      3. **M queries** — balanced brackets/parens, let/in structure,
         placeholder cleanup.
      4. **PBIR** — missing required keys, broken visual references,
         zero-size visuals.
    """

    # BIRT function patterns that leak into DAX (should have been converted)
    BIRT_LEAK_PATTERNS: list[tuple[str, str]] = [
        (r"\bTotal\.sum\(([^)]+)\)", r"SUM(\1)"),
        (r"\bTotal\.count\(\)", "COUNTROWS()"),
        (r"\bTotal\.count\(([^)]+)\)", r"COUNT(\1)"),
        (r"\bTotal\.ave\(([^)]+)\)", r"AVERAGE(\1)"),
        (r"\bTotal\.max\(([^)]+)\)", r"MAX(\1)"),
        (r"\bTotal\.min\(([^)]+)\)", r"MIN(\1)"),
        (r"\bTotal\.countDistinct\(([^)]+)\)", r"DISTINCTCOUNT(\1)"),
        (r"\bTotal\.variance\(([^)]+)\)", r"VAR.S(\1)"),
        (r"\bTotal\.stdDev\(([^)]+)\)", r"STDEV.S(\1)"),
        (r"\bTotal\.median\(([^)]+)\)", r"MEDIAN(\1)"),
        (r"\bBirtStr\.toUpper\(([^)]+)\)", r"UPPER(\1)"),
        (r"\bBirtStr\.toLower\(([^)]+)\)", r"LOWER(\1)"),
        (r"\bBirtStr\.trim\(([^)]+)\)", r"TRIM(\1)"),
        (r"\bBirtStr\.length\(([^)]+)\)", r"LEN(\1)"),
        (r"\bBirtStr\.left\(([^,]+),\s*(\d+)\)", r"LEFT(\1, \2)"),
        (r"\bBirtStr\.right\(([^,]+),\s*(\d+)\)", r"RIGHT(\1, \2)"),
        (r"\bBirtStr\.concat\(([^,]+),\s*([^)]+)\)", r"\1 & \2"),
        (r"\bBirtDateTime\.now\(\)", "NOW()"),
        (r"\bBirtDateTime\.today\(\)", "TODAY()"),
        (r"\bBirtDateTime\.year\(([^)]+)\)", r"YEAR(\1)"),
        (r"\bBirtDateTime\.month\(([^)]+)\)", r"MONTH(\1)"),
        (r"\bBirtDateTime\.day\(([^)]+)\)", r"DAY(\1)"),
    ]

    # BIRT row reference patterns that should become [Column]
    ROW_REF_PATTERNS: list[tuple[str, str]] = [
        (r'row\[\s*"([^"]+)"\s*\]', r"[\1]"),
        (r"row\[\s*'([^']+)'\s*\]", r"[\1]"),
        (r'dataSetRow\[\s*"([^"]+)"\s*\]', r"[\1]"),
        (r"dataSetRow\[\s*'([^']+)'\s*\]", r"[\1]"),
        (r"\brow\.([A-Za-z_]\w*)", r"[\1]"),
    ]

    # Valid TMDL data types
    VALID_TMDL_TYPES = {
        "string", "int64", "double", "decimal", "dateTime",
        "boolean", "binary", "unknown",
    }

    # Type normalisation map
    TYPE_NORMALISE: dict[str, str] = {
        "integer": "int64",
        "int": "int64",
        "long": "int64",
        "bigint": "int64",
        "float": "double",
        "number": "double",
        "numeric": "double",
        "real": "double",
        "date": "dateTime",
        "timestamp": "dateTime",
        "datetime": "dateTime",
        "bool": "boolean",
        "bit": "boolean",
        "varchar": "string",
        "nvarchar": "string",
        "text": "string",
        "char": "string",
        "nchar": "string",
        "clob": "string",
        "blob": "binary",
        "varbinary": "binary",
        "image": "binary",
    }

    def __init__(self) -> None:
        self.report = RecoveryReport()

    def heal_project(self, project_dir: str | Path) -> RecoveryReport:
        """Heal an entire .pbip project directory.

        Args:
            project_dir: Root of the .pbip project (contains .pbip file).

        Returns:
            RecoveryReport with all healing actions recorded.
        """
        root = Path(project_dir)

        # Collect known TMDL column names per table for visual validation
        self._tmdl_columns: dict[str, set[str]] = {}

        # Find semantic model directory
        sm_dirs = list(root.rglob("*.SemanticModel"))
        if sm_dirs:
            defn_dir = sm_dirs[0] / "definition"
            if defn_dir.exists():
                self._heal_tmdl_files(defn_dir)
                self._collect_tmdl_columns(defn_dir)

        # Find report directory
        report_dirs = list(root.rglob("*.Report"))
        if report_dirs:
            self._heal_pbir_files(report_dirs[0])

        self.report.print_summary()
        return self.report

    def _collect_tmdl_columns(self, defn_dir: Path) -> None:
        """Build a lookup of TMDL column names per table for visual validation."""
        tables_dir = defn_dir / "tables"
        if not tables_dir.exists():
            return
        for tmdl_file in tables_dir.glob("*.tmdl"):
            table_name = tmdl_file.stem
            cols: set[str] = set()
            for line in tmdl_file.read_text(encoding="utf-8").splitlines():
                m = re.match(r"^\tcolumn\s+(?:'([^']+)'|(\S+))", line)
                if m:
                    cols.add(m.group(1) or m.group(2))
            self._tmdl_columns[table_name] = cols

    # ── DAX Healing ──────────────────────────────────────────────────

    def heal_dax(self, formula: str, measure_name: str = "") -> str:
        """Apply all DAX healing rules to a formula.

        Returns the healed formula (may be unchanged if no issues found).
        """
        if not formula or not formula.strip():
            return formula

        original = formula
        formula = self._fix_birt_leaks(formula, measure_name)
        formula = self._fix_row_references(formula, measure_name)
        formula = self._fix_js_residuals(formula, measure_name)
        formula = self._fix_balanced_parens(formula, measure_name)
        formula = self._fix_line_comments(formula, measure_name)
        formula = self._fix_self_reference(formula, measure_name)
        return formula

    def _fix_birt_leaks(self, formula: str, name: str) -> str:
        """Replace BIRT function calls that leaked through conversion."""
        result = formula
        for pattern, replacement in self.BIRT_LEAK_PATTERNS:
            new = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
            if new != result:
                self.report.record(
                    "dax", "birt_leak",
                    description=f"BIRT function leak in '{name}'",
                    action=f"Replaced BIRT pattern with DAX equivalent",
                    item_name=name,
                    original_value=result,
                    repaired_value=new,
                )
                result = new
        return result

    def _fix_row_references(self, formula: str, name: str) -> str:
        """Replace row['col'] / dataSetRow["col"] with [col]."""
        result = formula
        for pattern, replacement in self.ROW_REF_PATTERNS:
            new = re.sub(pattern, replacement, result)
            if new != result:
                self.report.record(
                    "dax", "row_reference",
                    description=f"BIRT row reference in '{name}'",
                    action="Converted row['col'] to [col]",
                    item_name=name,
                    original_value=result,
                    repaired_value=new,
                )
                result = new
        return result

    def _fix_balanced_parens(self, formula: str, name: str) -> str:
        """Append missing closing parentheses if unbalanced."""
        open_count = formula.count("(")
        close_count = formula.count(")")
        diff = open_count - close_count
        if diff > 0:
            fixed = formula + ")" * diff
            self.report.record(
                "dax", "balanced_parens",
                description=f"Unbalanced parentheses in '{name}' ({diff} missing)",
                action=f"Appended {diff} closing paren(s)",
                item_name=name,
                original_value=formula,
                repaired_value=fixed,
            )
            return fixed
        return formula

    def _fix_line_comments(self, formula: str, name: str) -> str:
        """Remove JavaScript-style line comments (// ...) that break DAX.

        DAX uses -- for line comments, not //.
        """
        if "//" not in formula:
            return formula
        # Don't touch URLs (http:// https://)
        lines = formula.split("\n")
        fixed_lines: list[str] = []
        changed = False
        for line in lines:
            # Skip if it's a URL
            if re.search(r"https?://", line):
                fixed_lines.append(line)
                continue
            if "//" in line:
                # Replace // comment with -- comment
                new_line = re.sub(r"//(.*)$", r"-- \1", line)
                if new_line != line:
                    changed = True
                fixed_lines.append(new_line)
            else:
                fixed_lines.append(line)

        if changed:
            fixed = "\n".join(fixed_lines)
            self.report.record(
                "dax", "line_comment",
                description=f"JavaScript-style comments in '{name}'",
                action="Converted // comments to -- comments",
                item_name=name,
                original_value=formula,
                repaired_value=fixed,
            )
            return fixed
        return formula

    def _fix_self_reference(self, formula: str, name: str) -> str:
        """Detect measures that only reference themselves → wrap in error message.

        A measure like `[Revenue] / 100` where the measure IS named Revenue
        creates an infinite loop. We replace with a placeholder.
        """
        if not name:
            return formula
        refs = re.findall(r"\[([^\]]+)\]", formula)
        if refs and all(r == name for r in refs):
            # All column references point to the measure itself
            fixed = f'"{name}: self-reference removed"'
            self.report.record(
                "dax", "self_reference",
                description=f"Circular self-reference in measure '{name}'",
                action="Replaced with placeholder string",
                severity="warning",
                follow_up=True,
                item_name=name,
                original_value=formula,
                repaired_value=fixed,
            )
            return fixed
        return formula

    # ── JavaScript residual healing ──

    # Patterns for JS constructs that may leak into DAX
    _JS_RESIDUAL_PATTERNS: list[tuple[str, str, str]] = [
        (r"\bnull\b", "BLANK()", "null literal"),
        (r"\bundefined\b", "BLANK()", "undefined literal"),
        (r"\bnew\s+Date\(\)", "NOW()", "new Date()"),
        (r"\btypeof\b", "TYPE(", "typeof operator"),
    ]

    def _fix_js_residuals(self, formula: str, name: str) -> str:
        """Replace residual JavaScript constructs that slipped through conversion."""
        result = formula
        for pattern, replacement, desc in self._JS_RESIDUAL_PATTERNS:
            new = re.sub(pattern, replacement, result)
            if new != result:
                self.report.record(
                    "dax", "js_residual",
                    description=f"JavaScript '{desc}' in '{name}'",
                    action=f"Replaced {desc} with DAX equivalent",
                    item_name=name,
                    original_value=result,
                    repaired_value=new,
                )
                result = new
        return result

    # ── TMDL Healing ─────────────────────────────────────────────────

    def _heal_tmdl_files(self, definition_dir: Path) -> None:
        """Scan and heal all TMDL files in a semantic model definition directory."""
        # Heal model.tmdl
        model_file = definition_dir / "model.tmdl"
        if model_file.exists():
            self._heal_model_tmdl(model_file)

        # Heal table files
        tables_dir = definition_dir / "tables"
        if tables_dir.exists():
            for tmdl_file in sorted(tables_dir.glob("*.tmdl")):
                self._heal_table_tmdl(tmdl_file)

        # Heal relationships
        rel_file = definition_dir / "relationships.tmdl"
        if rel_file.exists():
            self._heal_relationships_tmdl(rel_file, tables_dir)

    def _heal_model_tmdl(self, path: Path) -> None:
        """Ensure model.tmdl has required properties."""
        content = path.read_text(encoding="utf-8")
        original = content
        changed = False

        # Must start with 'model Model'
        if not content.strip().startswith("model "):
            content = "model Model\n" + content
            changed = True

        # Must have culture
        if "culture:" not in content:
            content = content.rstrip() + "\n\tculture: en-US\n"
            changed = True

        # Must have defaultPowerBIDataSourceVersion
        if "defaultPowerBIDataSourceVersion" not in content:
            content = content.rstrip() + "\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
            changed = True

        if changed:
            path.write_text(content, encoding="utf-8")
            self.report.record(
                "tmdl", "model_header",
                description="model.tmdl missing required properties",
                action="Added missing model header properties",
                file_path=str(path),
                original_value=original,
                repaired_value=content,
            )

    def _heal_table_tmdl(self, path: Path) -> None:
        """Heal a single table TMDL file."""
        content = path.read_text(encoding="utf-8")
        original = content

        content = self._fix_duplicate_columns_tmdl(content, path)
        content = self._fix_data_types_tmdl(content, path)
        content = self._fix_dax_in_tmdl(content, path)
        content = self._fix_partition_m(content, path)
        content = self._fix_missing_lineage_tags(content, path)
        content = self._fix_column_summarize_by(content, path)

        if content != original:
            path.write_text(content, encoding="utf-8")

    def _fix_duplicate_columns_tmdl(self, content: str, path: Path) -> str:
        """Remove duplicate column definitions (keep first occurrence)."""
        lines = content.split("\n")
        seen_columns: set[str] = set()
        result_lines: list[str] = []
        skip_until_next = False
        removed: list[str] = []

        i = 0
        while i < len(lines):
            line = lines[i]
            col_match = re.match(r"^\tcolumn\s+(?:'([^']+)'|(\S+))", line)
            if col_match:
                col_name = col_match.group(1) or col_match.group(2)
                if col_name in seen_columns:
                    # Skip this column and its properties
                    removed.append(col_name)
                    i += 1
                    while i < len(lines) and lines[i].startswith("\t\t"):
                        i += 1
                    # Skip trailing blank line
                    if i < len(lines) and lines[i].strip() == "":
                        i += 1
                    continue
                seen_columns.add(col_name)
            result_lines.append(line)
            i += 1

        if removed:
            new_content = "\n".join(result_lines)
            self.report.record(
                "tmdl", "duplicate_column",
                description=f"Duplicate columns in {path.name}: {removed}",
                action=f"Removed {len(removed)} duplicate column(s)",
                severity="warning",
                item_name=path.stem,
                file_path=str(path),
            )
            return new_content
        return content

    def _fix_data_types_tmdl(self, content: str, path: Path) -> str:
        """Normalise non-standard data types to valid TMDL types."""
        def _replace_type(match: re.Match) -> str:
            dtype = match.group(1).strip()
            if dtype in self.VALID_TMDL_TYPES:
                return match.group(0)
            normalised = self.TYPE_NORMALISE.get(dtype.lower())
            if normalised:
                self.report.record(
                    "tmdl", "data_type",
                    description=f"Non-standard type '{dtype}' in {path.name}",
                    action=f"Normalised to '{normalised}'",
                    item_name=path.stem,
                    file_path=str(path),
                    original_value=dtype,
                    repaired_value=normalised,
                )
                return f"\t\tdataType: {normalised}"
            # Unknown type → default to string
            self.report.record(
                "tmdl", "data_type",
                description=f"Unknown type '{dtype}' in {path.name}",
                action="Defaulted to 'string'",
                severity="warning",
                follow_up=True,
                item_name=path.stem,
                file_path=str(path),
                original_value=dtype,
                repaired_value="string",
            )
            return "\t\tdataType: string"

        return re.sub(r"^\t\tdataType:\s*(.+)$", _replace_type, content, flags=re.MULTILINE)

    def _fix_dax_in_tmdl(self, content: str, path: Path) -> str:
        """Heal DAX expressions embedded in TMDL (measures and calculated columns)."""
        lines = content.split("\n")
        result: list[str] = []
        i = 0
        changed = False

        while i < len(lines):
            line = lines[i]

            # Match measure or calculated column with inline expression
            m_measure = re.match(r"^(\tmeasure\s+(?:'[^']+?'|\S+))\s*=\s*(.+)$", line)
            m_calc = re.match(r"^(\tcolumn\s+(?:'[^']+?'|\S+))\s*=\s*(.+)$", line)

            if m_measure:
                prefix, expr = m_measure.group(1), m_measure.group(2)
                # Extract measure name
                name_match = re.search(r"measure\s+(?:'([^']+)'|(\S+))", prefix)
                mname = (name_match.group(1) or name_match.group(2)) if name_match else ""
                # Skip multi-line fenced expressions
                if expr.strip() != "```":
                    healed = self.heal_dax(expr, mname)
                    if healed != expr:
                        changed = True
                    result.append(f"{prefix} = {healed}")
                    i += 1
                    continue

            elif m_calc:
                prefix, expr = m_calc.group(1), m_calc.group(2)
                name_match = re.search(r"column\s+(?:'([^']+)'|(\S+))", prefix)
                cname = (name_match.group(1) or name_match.group(2)) if name_match else ""
                if expr.strip() != "```":
                    healed = self.heal_dax(expr, cname)
                    if healed != expr:
                        changed = True
                    result.append(f"{prefix} = {healed}")
                    i += 1
                    continue

            result.append(line)
            i += 1

        if changed:
            return "\n".join(result)
        return content

    def _fix_partition_m(self, content: str, path: Path) -> str:
        """Ensure partition M expressions are valid.

        Wraps source expressions in try/otherwise fallback so the model
        loads even if the source is unreachable.
        """
        # Find source = <expr> lines
        def _wrap_source(match: re.Match) -> str:
            expr = match.group(1).strip()
            # Already wrapped, safe #table literal, or backtick-fenced block
            if expr.startswith("try") or expr.startswith("#table") or expr.startswith("```"):
                return match.group(0)
            # Wrap in try/otherwise #table fallback
            wrapped = f"try {expr} otherwise #table({{}}, {{}})"
            self.report.record(
                "m_query", "partition_wrap",
                description=f"Partition source in {path.name} not guarded",
                action="Wrapped in try/otherwise #table fallback",
                item_name=path.stem,
                file_path=str(path),
                original_value=expr,
                repaired_value=wrapped,
            )
            return f"\t\tsource = {wrapped}"

        return re.sub(r"^\t\tsource\s*=\s*(.+)$", _wrap_source, content, flags=re.MULTILINE)

    def _fix_missing_lineage_tags(self, content: str, path: Path) -> str:
        """Ensure all columns have lineageTag (required by PBI Desktop)."""
        lines = content.split("\n")
        result: list[str] = []
        i = 0
        added = 0

        while i < len(lines):
            result.append(lines[i])
            col_match = re.match(r"^\tcolumn\s+(?:'([^']+)'|(\S+))", lines[i])
            if col_match:
                col_name = col_match.group(1) or col_match.group(2)
                # Collect property lines
                props_start = i + 1
                has_lineage = False
                j = props_start
                while j < len(lines) and (lines[j].startswith("\t\t") or lines[j].strip() == ""):
                    if "lineageTag:" in lines[j]:
                        has_lineage = True
                    if lines[j].strip() == "":
                        break
                    j += 1
                # If no lineageTag, insert before the blank line
                if not has_lineage:
                    # Add properties until we hit the empty line
                    while i + 1 < len(lines) and lines[i + 1].startswith("\t\t"):
                        i += 1
                        result.append(lines[i])
                    result.append(f"\t\tlineageTag: {col_name}")
                    added += 1
                    i += 1
                    continue
            i += 1

        if added:
            self.report.record(
                "tmdl", "lineage_tag",
                description=f"Missing lineageTag in {path.name}",
                action=f"Added {added} lineageTag(s)",
                item_name=path.stem,
                file_path=str(path),
            )
            return "\n".join(result)
        return content

    def _fix_column_summarize_by(self, content: str, path: Path) -> str:
        """Ensure all columns have summarizeBy: none.

        PBI Desktop defaults to Sum for numeric columns which can cause
        unexpected aggregation. We explicitly set none.
        """
        lines = content.split("\n")
        result: list[str] = []
        i = 0
        added = 0

        while i < len(lines):
            result.append(lines[i])
            col_match = re.match(r"^\tcolumn\s+", lines[i])
            if col_match:
                j = i + 1
                has_summarize = False
                while j < len(lines) and lines[j].startswith("\t\t"):
                    if "summarizeBy:" in lines[j]:
                        has_summarize = True
                    j += 1
                if not has_summarize:
                    while i + 1 < len(lines) and lines[i + 1].startswith("\t\t"):
                        i += 1
                        result.append(lines[i])
                    result.append("\t\tsummarizeBy: none")
                    added += 1
                    i += 1
                    continue
            i += 1

        if added:
            self.report.record(
                "tmdl", "summarize_by",
                description=f"Missing summarizeBy in {path.name}",
                action=f"Added summarizeBy: none to {added} column(s)",
                item_name=path.stem,
                file_path=str(path),
            )
            return "\n".join(result)
        return content

    def _heal_relationships_tmdl(self, path: Path, tables_dir: Path | None) -> None:
        """Heal relationships.tmdl — remove relationships referencing missing tables."""
        content = path.read_text(encoding="utf-8")

        # Get existing table names
        existing_tables: set[str] = set()
        if tables_dir and tables_dir.exists():
            existing_tables = {f.stem for f in tables_dir.glob("*.tmdl")}

        if not existing_tables:
            return

        # Parse relationship blocks
        blocks = re.split(r"(?=\nrelationship )", content)
        valid_blocks: list[str] = []
        removed: list[str] = []

        for block in blocks:
            if not block.strip():
                continue
            # Extract referenced tables
            from_tables = re.findall(r"fromColumn:\s+(\S+)\.\S+", block)
            to_tables = re.findall(r"toColumn:\s+(\S+)\.\S+", block)
            ref_tables = set(from_tables + to_tables)
            missing = ref_tables - existing_tables
            if missing:
                rel_match = re.search(r"relationship\s+(\S+)", block)
                rel_name = rel_match.group(1) if rel_match else "unknown"
                removed.append(rel_name)
                self.report.record(
                    "tmdl", "orphan_relationship",
                    description=f"Relationship '{rel_name}' references missing tables: {missing}",
                    action="Removed orphan relationship",
                    severity="warning",
                    item_name=rel_name,
                    file_path=str(path),
                )
            else:
                valid_blocks.append(block)

        if removed:
            path.write_text("\n".join(valid_blocks), encoding="utf-8")

    # ── M Query Healing ──────────────────────────────────────────────

    def heal_m_expression(self, expr: str, name: str = "") -> str:
        """Heal an M (Power Query) expression."""
        if not expr or not expr.strip():
            return expr

        expr = self._fix_m_balanced_brackets(expr, name)
        expr = self._fix_m_let_in(expr, name)
        expr = self._fix_m_placeholder(expr, name)
        return expr

    def _fix_m_balanced_brackets(self, expr: str, name: str) -> str:
        """Fix unbalanced brackets/parens in M expressions."""
        for open_ch, close_ch, label in [("(", ")", "parens"), ("{", "}", "braces"), ("[", "]", "brackets")]:
            diff = expr.count(open_ch) - expr.count(close_ch)
            if diff > 0:
                fixed = expr + close_ch * diff
                self.report.record(
                    "m_query", f"balanced_{label}",
                    description=f"Unbalanced {label} in M expression '{name}'",
                    action=f"Appended {diff} closing {label}",
                    item_name=name,
                    original_value=expr,
                    repaired_value=fixed,
                )
                expr = fixed
        return expr

    def _fix_m_let_in(self, expr: str, name: str) -> str:
        """Ensure let/in blocks are balanced."""
        let_count = len(re.findall(r"\blet\b", expr, re.IGNORECASE))
        in_count = len(re.findall(r"\bin\b", expr, re.IGNORECASE))
        if let_count > in_count:
            # Missing 'in' — append with a Source reference
            diff = let_count - in_count
            for _ in range(diff):
                expr = expr.rstrip().rstrip(",") + "\nin\n    Source"
            self.report.record(
                "m_query", "let_in_balance",
                description=f"Missing 'in' clause in M expression '{name}'",
                action=f"Appended {diff} 'in Source' block(s)",
                item_name=name,
                original_value=expr,
                repaired_value=expr,
            )
        return expr

    def _fix_m_placeholder(self, expr: str, name: str) -> str:
        """Remove {prev} placeholders left from template generation."""
        if "{prev}" in expr:
            fixed = expr.replace("{prev}", "Source")
            self.report.record(
                "m_query", "placeholder",
                description=f"Template placeholder in M expression '{name}'",
                action="Replaced {prev} with Source",
                item_name=name,
                original_value=expr,
                repaired_value=fixed,
            )
            return fixed
        return expr

    # ── PBIR Healing ─────────────────────────────────────────────────

    def _heal_pbir_files(self, report_dir: Path) -> None:
        """Heal PBIR report files."""
        # Heal definition.pbir
        pbir = report_dir / "definition.pbir"
        if pbir.exists():
            self._heal_definition_pbir(pbir)

        # Heal report.json
        report_json = report_dir / "definition" / "report.json"
        if report_json.exists():
            self._heal_report_json(report_json)

        # Heal visual.json files
        for visual_file in report_dir.rglob("visual.json"):
            self._heal_visual_json(visual_file)

    def _heal_definition_pbir(self, path: Path) -> None:
        """Ensure definition.pbir has required keys."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.report.record(
                "pbir", "invalid_json",
                description=f"Invalid JSON in {path.name}",
                action="Cannot heal — file must be regenerated",
                severity="error",
                follow_up=True,
                file_path=str(path),
            )
            return

        changed = False

        if "$schema" not in data:
            data["$schema"] = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pbir/1.0.0/schema.json"
            changed = True

        if "version" not in data:
            data["version"] = "4.0"
            changed = True

        if "datasetReference" not in data:
            # Try to find the semantic model
            sm_dirs = list(path.parent.parent.rglob("*.SemanticModel"))
            if sm_dirs:
                data["datasetReference"] = {
                    "byPath": {
                        "path": sm_dirs[0].name,
                    },
                }
                changed = True

        if changed:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.report.record(
                "pbir", "definition_keys",
                description="definition.pbir missing required keys",
                action="Added missing keys ($schema, version, datasetReference)",
                file_path=str(path),
            )

    def _heal_report_json(self, path: Path) -> None:
        """Ensure report.json has minimum required structure."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.report.record(
                "pbir", "invalid_json",
                description=f"Invalid JSON in {path.name}",
                action="Cannot heal — file must be regenerated",
                severity="error",
                follow_up=True,
                file_path=str(path),
            )
            return

        changed = False

        if "$schema" not in data:
            data["$schema"] = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.2.0/schema.json"
            changed = True

        if "themeCollection" not in data:
            data["themeCollection"] = {
                "baseTheme": {
                    "name": "CY24SU06",
                    "reportVersionAtImport": "5.53",
                    "type": "SharedResources",
                },
            }
            changed = True

        if changed:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.report.record(
                "pbir", "report_structure",
                description="report.json missing required properties",
                action="Added missing schema/theme properties",
                file_path=str(path),
            )

    def _heal_visual_json(self, path: Path) -> None:
        """Heal individual visual.json files."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.report.record(
                "pbir", "invalid_json",
                description=f"Invalid JSON in {path.relative_to(path.parent.parent.parent)}",
                action="Cannot heal — file must be regenerated",
                severity="error",
                follow_up=True,
                file_path=str(path),
            )
            return

        changed = False

        # Ensure visual has a type
        visual = data.get("visual", data)
        if "visualType" not in visual:
            visual["visualType"] = "tableEx"
            changed = True
            self.report.record(
                "pbir", "missing_visual_type",
                description=f"Visual missing visualType in {path.parent.name}",
                action="Defaulted to tableEx (table)",
                severity="warning",
                follow_up=True,
                file_path=str(path),
            )

        # Fix zero-size visuals (PBI Desktop ignores them)
        position = visual.get("position", data.get("position"))
        if position:
            if position.get("width", 0) <= 0:
                position["width"] = 300
                changed = True
            if position.get("height", 0) <= 0:
                position["height"] = 200
                changed = True
            if changed and "position" not in visual:
                data["position"] = position

        # Validate visual field references against TMDL columns
        if self._tmdl_columns:
            if self._heal_visual_field_refs(data, path):
                changed = True

        if changed:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _heal_visual_field_refs(self, data: dict, path: Path) -> bool:
        """Remove visual field projections that reference non-existent columns."""
        visual = data.get("visual", data)
        query_state = visual.get("query", {}).get("queryState", {})
        if not query_state:
            return False

        changed = False
        for role_name in list(query_state.keys()):
            role = query_state[role_name]
            projections = role.get("projections", [])
            valid: list[dict] = []
            removed: list[str] = []
            for proj in projections:
                col_info = proj.get("field", {}).get("Column", {})
                entity = col_info.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
                prop = col_info.get("Property", "")
                known_cols = self._tmdl_columns.get(entity, set())
                if known_cols and prop and prop not in known_cols:
                    removed.append(f"{entity}.{prop}")
                else:
                    valid.append(proj)
            if removed:
                role["projections"] = valid
                changed = True
                self.report.record(
                    "pbir", "invalid_field_ref",
                    description=f"Visual {path.parent.name}: removed invalid fields {removed}",
                    action=f"Removed {len(removed)} non-existent column reference(s)",
                    severity="warning",
                    item_name=path.parent.name,
                    file_path=str(path),
                )
            # Remove empty roles
            if not role.get("projections"):
                del query_state[role_name]
        return changed

    # ── Convenience ──────────────────────────────────────────────────

    def heal_and_validate(self, project_dir: str | Path) -> dict[str, Any]:
        """Heal then validate — returns combined results.

        Returns dict with 'healing' (RecoveryReport summary) and
        'validation' (MigrationValidator results).
        """
        report = self.heal_project(project_dir)

        from .validator import MigrationValidator
        validator = MigrationValidator()
        validation = validator.validate(project_dir)

        return {
            "healing": report.get_summary(),
            "validation": validation,
        }
