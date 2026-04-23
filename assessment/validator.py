"""Post-migration validation — compare source inventory vs generated artifacts."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MigrationValidator:
    """Validates generated artifacts against source extraction."""

    def validate(self, output_dir: str | Path) -> dict[str, Any]:
        """Run all validation checks on migration output.

        Args:
            output_dir: Path to the migration output directory.

        Returns:
            Dict with validation results per check.
        """
        out = Path(output_dir)
        checks: list[dict[str, Any]] = []

        checks.append(self._check_intermediate_jsons(out))
        checks.append(self._check_tmdl_output(out))
        checks.append(self._check_pbip_structure(out))
        checks.append(self._check_visual_count(out))
        checks.append(self._check_measure_count(out))
        checks.append(self._check_platform_files(out))
        checks.append(self._check_duplicate_columns(out))
        checks.append(self._check_ambiguous_relationships(out))
        checks.append(self._check_relationship_tables(out))

        passed = sum(1 for c in checks if c["status"] == "pass")
        failed = sum(1 for c in checks if c["status"] == "fail")
        warnings = sum(1 for c in checks if c["status"] == "warn")

        return {
            "checks": checks,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "valid": failed == 0,
        }

    def _check_intermediate_jsons(self, out: Path) -> dict[str, Any]:
        """Verify all required intermediate JSON files exist.

        Checks both the root directory and ``extraction/`` subfolder.
        """
        required = ["datasets.json", "connections.json", "visuals.json", "expressions.json"]
        # JSON files may be in root or in extraction/ subfolder
        extraction_dir = out / "extraction"
        base = extraction_dir if extraction_dir.is_dir() else out
        missing = [f for f in required if not (base / f).exists()]
        if missing:
            return {
                "check": "intermediate_jsons",
                "status": "fail",
                "detail": f"Missing: {missing}",
            }
        return {
            "check": "intermediate_jsons",
            "status": "pass",
            "detail": f"All {len(required)} intermediate files present",
        }

    def _check_tmdl_output(self, out: Path) -> dict[str, Any]:
        """Verify TMDL semantic model files exist."""
        sm_dirs = list(out.rglob("*.SemanticModel"))
        if not sm_dirs:
            return {"check": "tmdl_output", "status": "fail", "detail": "No .SemanticModel directory"}

        model_tmdl = sm_dirs[0] / "definition" / "model.tmdl"
        if not model_tmdl.exists():
            return {"check": "tmdl_output", "status": "fail", "detail": "model.tmdl not found"}

        tables_dir = sm_dirs[0] / "definition" / "tables"
        table_files = list(tables_dir.glob("*.tmdl")) if tables_dir.exists() else []
        if not table_files:
            return {"check": "tmdl_output", "status": "warn", "detail": "No table TMDL files"}

        return {
            "check": "tmdl_output",
            "status": "pass",
            "detail": f"model.tmdl + {len(table_files)} table(s)",
        }

    def _check_pbip_structure(self, out: Path) -> dict[str, Any]:
        """Verify .pbip project structure is complete."""
        pbip_files = list(out.rglob("*.pbip"))
        if not pbip_files:
            return {"check": "pbip_structure", "status": "warn", "detail": "No .pbip file found"}

        pbip_dir = pbip_files[0].parent
        report_dirs = list(pbip_dir.glob("*.Report"))
        if not report_dirs:
            return {"check": "pbip_structure", "status": "fail", "detail": "No .Report directory"}

        report_dir = report_dirs[0]
        required_files = [
            report_dir / "definition.pbir",
            report_dir / ".platform",
        ]
        missing = [str(f.name) for f in required_files if not f.exists()]
        if missing:
            return {"check": "pbip_structure", "status": "fail", "detail": f"Missing: {missing}"}

        return {"check": "pbip_structure", "status": "pass", "detail": "PBIP structure valid"}

    def _check_visual_count(self, out: Path) -> dict[str, Any]:
        """Verify visuals were generated."""
        visual_files = list(out.rglob("visual.json"))
        source_visuals = self._load_json(out / "visuals.json")
        source_count = len(source_visuals) if isinstance(source_visuals, list) else 0

        if not visual_files:
            if source_count == 0:
                return {"check": "visual_count", "status": "pass", "detail": "No visuals (none in source)"}
            return {"check": "visual_count", "status": "fail", "detail": f"0 generated vs {source_count} source"}

        return {
            "check": "visual_count",
            "status": "pass",
            "detail": f"{len(visual_files)} visual(s) generated from {source_count} source element(s)",
        }

    def _check_measure_count(self, out: Path) -> dict[str, Any]:
        """Verify measures were generated in TMDL."""
        measure_count = 0
        for tmdl_file in out.rglob("*.tmdl"):
            content = tmdl_file.read_text(encoding="utf-8")
            measure_count += content.count("\tmeasure ")

        exprs = self._load_json(out / "expressions.json")
        expr_count = len(exprs) if isinstance(exprs, list) else 0

        if measure_count == 0 and expr_count > 0:
            return {"check": "measure_count", "status": "warn",
                    "detail": f"0 measures but {expr_count} expressions extracted"}

        return {"check": "measure_count", "status": "pass",
                "detail": f"{measure_count} measure(s) from {expr_count} expression(s)"}

    def _check_platform_files(self, out: Path) -> dict[str, Any]:
        """Verify .platform files exist for Report and SemanticModel."""
        platforms = list(out.rglob(".platform"))
        if len(platforms) < 2:
            return {"check": "platform_files", "status": "warn",
                    "detail": f"Expected 2 .platform files, found {len(platforms)}"}
        return {"check": "platform_files", "status": "pass",
                "detail": f"{len(platforms)} .platform file(s)"}

    @staticmethod
    def _load_json(path: Path) -> Any:
        """Load JSON, return empty list if not found."""
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # ── TMDL-specific validation checks ──────────────────────────────

    def _check_duplicate_columns(self, out: Path) -> dict[str, Any]:
        """Check for duplicate column definitions within each table TMDL file.

        Power BI rejects TMDL when a table declares the same column (or the
        same property like ``dataType``) more than once.
        """
        import re
        duplicates: list[str] = []
        for tmdl_file in out.rglob("*.tmdl"):
            if tmdl_file.name == "model.tmdl" or tmdl_file.name == "relationships.tmdl":
                continue
            content = tmdl_file.read_text(encoding="utf-8")
            # Extract column names
            col_names = re.findall(r"^\tcolumn\s+(?:'([^']+)'|(\S+))", content, re.MULTILINE)
            names = [m[0] or m[1] for m in col_names]
            seen: set[str] = set()
            for name in names:
                if name in seen:
                    duplicates.append(f"{tmdl_file.stem}:{name}")
                seen.add(name)

        if duplicates:
            return {
                "check": "duplicate_columns",
                "status": "fail",
                "detail": f"Duplicate columns: {duplicates}",
            }
        return {
            "check": "duplicate_columns",
            "status": "pass",
            "detail": "No duplicate columns",
        }

    def _check_ambiguous_relationships(self, out: Path) -> dict[str, Any]:
        """Check for ambiguous paths — multiple relationships between same table pair.

        Power BI only allows one active relationship between any two tables.
        Multiple relationships create "ambiguous paths" errors.
        """
        import re
        rel_file = None
        for f in out.rglob("relationships.tmdl"):
            rel_file = f
            break
        if not rel_file:
            return {
                "check": "ambiguous_relationships",
                "status": "pass",
                "detail": "No relationships file (nothing to check)",
            }

        content = rel_file.read_text(encoding="utf-8")

        # Parse relationships: fromColumn lines contain table.column
        from_entries = re.findall(r"fromColumn:\s+(\S+)\.(\S+)", content)
        to_entries = re.findall(r"toColumn:\s+(\S+)\.(\S+)", content)

        pair_count: dict[tuple[str, str], int] = {}
        for (from_table, _), (to_table, _) in zip(from_entries, to_entries):
            pair = (min(from_table, to_table), max(from_table, to_table))
            pair_count[pair] = pair_count.get(pair, 0) + 1

        ambiguous = {pair: cnt for pair, cnt in pair_count.items() if cnt > 1}
        if ambiguous:
            details = [f"{a}->{b} ({cnt} rels)" for (a, b), cnt in ambiguous.items()]
            return {
                "check": "ambiguous_relationships",
                "status": "fail",
                "detail": f"Ambiguous paths: {'; '.join(details)}",
            }
        return {
            "check": "ambiguous_relationships",
            "status": "pass",
            "detail": f"{len(pair_count)} relationship pair(s), no ambiguity",
        }

    def _check_relationship_tables(self, out: Path) -> dict[str, Any]:
        """Verify all tables referenced in relationships actually exist as TMDL files."""
        import re
        rel_file = None
        for f in out.rglob("relationships.tmdl"):
            rel_file = f
            break
        if not rel_file:
            return {
                "check": "relationship_tables",
                "status": "pass",
                "detail": "No relationships file",
            }

        content = rel_file.read_text(encoding="utf-8")
        ref_tables: set[str] = set()
        for match in re.findall(r"(?:fromColumn|toColumn):\s+(\S+)\.\S+", content):
            ref_tables.add(match)

        tables_dir = rel_file.parent / "tables"
        existing = set()
        if tables_dir.exists():
            existing = {f.stem for f in tables_dir.glob("*.tmdl")}

        missing = ref_tables - existing
        if missing:
            return {
                "check": "relationship_tables",
                "status": "fail",
                "detail": f"Missing table files for: {sorted(missing)}",
            }
        return {
            "check": "relationship_tables",
            "status": "pass",
            "detail": f"All {len(ref_tables)} referenced table(s) exist",
        }
