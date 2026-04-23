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
        """Verify all required intermediate JSON files exist."""
        required = ["datasets.json", "connections.json", "visuals.json", "expressions.json"]
        missing = [f for f in required if not (out / f).exists()]
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
