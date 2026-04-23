"""Content inventory scanner — volumes, types, sizes, MIME breakdown."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ContentScanner:
    """Scans extracted content to build a migration inventory.

    Works on the intermediate JSON files produced by the extraction step
    (datasets.json, connections.json, visuals.json, reports.json).
    """

    def __init__(self) -> None:
        self.inventory: dict[str, Any] = {
            "reports": [],
            "datasets": [],
            "connections": [],
            "visuals": [],
            "summary": {},
        }

    def scan_directory(self, output_dir: str | Path) -> dict[str, Any]:
        """Scan an extraction output directory for all artifacts."""
        import json

        out = Path(output_dir)
        logger.info("Scanning directory: %s", out)

        for json_file in ("reports.json", "datasets.json", "connections.json",
                          "visuals.json", "expressions.json"):
            path = out / json_file
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                key = json_file.replace(".json", "")
                self.inventory[key] = data if isinstance(data, list) else [data]

        # Scan for BIRT report files
        for rpt in out.rglob("*.rptdesign"):
            self.inventory["reports"].append({
                "path": str(rpt),
                "name": rpt.stem,
                "size_bytes": rpt.stat().st_size,
            })

        self.inventory["summary"] = self._build_summary()
        return self.inventory

    def scan_report_file(self, report_path: str | Path) -> dict[str, Any]:
        """Scan a single BIRT report file for inventory."""
        path = Path(report_path)
        if not path.exists():
            return {"error": f"File not found: {report_path}"}

        from opentext_extract.birt_parser import BIRTParser
        parser = BIRTParser(path)
        data = parser.parse()

        entry = {
            "path": str(path),
            "name": path.stem,
            "size_bytes": path.stat().st_size,
            "data_sources": len(data.get("data_sources", [])),
            "datasets": len(data.get("datasets", [])),
            "parameters": len(data.get("parameters", [])),
            "body_elements": len(data.get("body", [])),
            "styles": len(data.get("styles", [])),
            "columns": sum(
                len(ds.get("result_columns", [])) + len(ds.get("column_hints", []))
                for ds in data.get("datasets", [])
            ),
            "computed_columns": sum(
                len(ds.get("computed_columns", []))
                for ds in data.get("datasets", [])
            ),
            "expressions": len(self._collect_expressions(data)),
        }
        return entry

    def scan_batch(self, paths: list[str | Path]) -> list[dict[str, Any]]:
        """Scan multiple report files and return inventory entries."""
        results = []
        for p in paths:
            try:
                entry = self.scan_report_file(p)
                results.append(entry)
            except Exception as e:
                results.append({"path": str(p), "error": str(e)})
                logger.warning("Failed to scan %s: %s", p, e)
        return results

    def _build_summary(self) -> dict[str, Any]:
        """Build summary statistics from inventory."""
        datasets = self.inventory.get("datasets", [])
        visuals = self.inventory.get("visuals", [])
        connections = self.inventory.get("connections", [])
        expressions = self.inventory.get("expressions", [])

        # Count visual types
        visual_types: dict[str, int] = {}
        for v in visuals:
            vtype = v.get("element_type", "unknown")
            visual_types[vtype] = visual_types.get(vtype, 0) + 1

        # Count data source types
        ds_types: dict[str, int] = {}
        for c in connections:
            ctype = c.get("type", c.get("odaDriverClass", "unknown"))
            ds_types[ctype] = ds_types.get(ctype, 0) + 1

        return {
            "total_reports": len(self.inventory.get("reports", [])),
            "total_datasets": len(datasets),
            "total_connections": len(connections),
            "total_visuals": len(visuals),
            "total_expressions": len(expressions),
            "visual_types": visual_types,
            "data_source_types": ds_types,
            "total_columns": sum(
                len(ds.get("result_columns", [])) for ds in datasets
            ),
            "total_computed_columns": sum(
                len(ds.get("computed_columns", [])) for ds in datasets
            ),
        }

    @staticmethod
    def _collect_expressions(data: dict[str, Any]) -> list[dict[str, Any]]:
        """Collect all expressions from parsed BIRT data."""
        exprs: list[dict[str, Any]] = []

        # From datasets — computed columns
        for ds in data.get("datasets", []):
            for cc in ds.get("computed_columns", []):
                if cc.get("expression"):
                    exprs.append({
                        "source": f"dataset:{ds.get('name', '')}",
                        "expression": cc["expression"],
                    })

        # From body elements
        for elem in data.get("body", []):
            for e in elem.get("expressions", []):
                if e.get("value"):
                    exprs.append({
                        "source": f"element:{elem.get('element_type', '')}:{elem.get('name', '')}",
                        "expression": e["value"],
                    })
            # Recurse into children
            for child in elem.get("children", []):
                for e in child.get("expressions", []):
                    if e.get("value"):
                        exprs.append({
                            "source": f"element:{child.get('element_type', '')}:{child.get('name', '')}",
                            "expression": e["value"],
                        })

        return exprs
