"""PBIP generator — .pbip project output (PBIR v4.0 + TMDL)."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PBIPGenerator:
    """Generates .pbip Power BI project files (PBIR v4.0 format)."""

    def __init__(self, report_name: str = "MigratedReport"):
        self.report_name = report_name
        self._report_id = str(uuid.uuid4())

    def generate(
        self,
        visuals: list[dict[str, Any]],
        semantic_model_path: str = "",
        output_dir: str | Path = "./output",
    ) -> dict[str, Path]:
        """Generate complete .pbip project structure.

        Args:
            visuals: List of mapped PBI visual configs from VisualMapper.
            semantic_model_path: Path to the semantic model (.tmdl folder).
            output_dir: Root output directory.

        Returns:
            Dict of generated file paths.
        """
        out = Path(output_dir) / self.report_name
        report_dir = out / f"{self.report_name}.Report"
        report_dir.mkdir(parents=True, exist_ok=True)
        files: dict[str, Path] = {}

        # 1. .pbip file
        files[".pbip"] = self._write_pbip(out)

        # 2. Report definition.pbir
        files["definition.pbir"] = self._write_pbir(report_dir, semantic_model_path)

        # 3. Report pages
        pages = self._build_pages(visuals)
        for i, page in enumerate(pages):
            page_dir = report_dir / "definition" / "pages" / page["name"]
            page_dir.mkdir(parents=True, exist_ok=True)

            page_path = page_dir / "page.json"
            self._write_json(page_path, page["config"])
            files[f"page_{i}"] = page_path

            # Visual containers within the page
            visuals_dir = page_dir / "visuals"
            visuals_dir.mkdir(parents=True, exist_ok=True)
            for j, visual in enumerate(page["visuals"]):
                visual_dir = visuals_dir / visual.get("name", f"visual_{j}")
                visual_dir.mkdir(parents=True, exist_ok=True)
                visual_path = visual_dir / "visual.json"
                self._write_json(visual_path, visual)
                files[f"visual_{i}_{j}"] = visual_path

        # 4. Report config
        files["report.json"] = self._write_report_config(report_dir)

        # 5. Static resources
        files["StaticResources"] = self._write_static_resources(report_dir)

        logger.info("Generated .pbip project with %d pages at %s", len(pages), out)
        return files

    def _write_pbip(self, out: Path) -> Path:
        """Write the .pbip project file."""
        pbip = {
            "version": "1.0",
            "artifacts": [
                {
                    "report": {
                        "path": f"{self.report_name}.Report",
                    },
                },
            ],
        }
        path = out / f"{self.report_name}.pbip"
        self._write_json(path, pbip)
        return path

    def _write_pbir(self, report_dir: Path, semantic_model_path: str) -> Path:
        """Write the PBIR definition file."""
        definition_dir = report_dir / "definition"
        definition_dir.mkdir(parents=True, exist_ok=True)

        pbir = {
            "version": "4.0",
            "datasetReference": {
                "byPath": {
                    "path": semantic_model_path or f"../{self.report_name}.SemanticModel",
                },
            },
        }
        path = definition_dir / "definition.pbir"
        self._write_json(path, pbir)
        return path

    def _build_pages(
        self,
        visuals: list[dict[str, Any]],
        max_visuals_per_page: int = 10,
    ) -> list[dict[str, Any]]:
        """Organize visuals into report pages with layout."""
        if not visuals:
            return [self._build_empty_page("Page 1")]

        pages: list[dict[str, Any]] = []
        current_visuals: list[dict[str, Any]] = []
        page_num = 1

        y_offset = 20
        for visual in visuals:
            # Position visual
            positioned = dict(visual)
            pos = positioned.get("position", {})
            size = positioned.get("size", {"width": 300, "height": 200})
            pos["y"] = y_offset
            positioned["position"] = pos
            y_offset += size.get("height", 200) + 20  # 20px gap

            # Generate a visual container config
            visual_config = self._build_visual_config(positioned)
            current_visuals.append(visual_config)

            if len(current_visuals) >= max_visuals_per_page:
                pages.append(self._build_page(f"Page {page_num}", current_visuals))
                current_visuals = []
                page_num += 1
                y_offset = 20

        if current_visuals:
            pages.append(self._build_page(f"Page {page_num}", current_visuals))

        return pages

    def _build_page(self, name: str, visuals: list[dict[str, Any]]) -> dict[str, Any]:
        """Build a single page definition."""
        return {
            "name": name.replace(" ", ""),
            "config": {
                "name": name,
                "displayName": name,
                "displayOption": 1,
                "width": 1280,
                "height": 720,
            },
            "visuals": visuals,
        }

    def _build_empty_page(self, name: str) -> dict[str, Any]:
        return self._build_page(name, [])

    def _build_visual_config(self, visual: dict[str, Any]) -> dict[str, Any]:
        """Build PBI visual container configuration."""
        pos = visual.get("position", {"x": 0, "y": 0})
        size = visual.get("size", {"width": 300, "height": 200})
        pbi_type = visual.get("visual_type", "textbox")
        name = visual.get("name", "") or str(uuid.uuid4())[:8]

        config: dict[str, Any] = {
            "name": name,
            "visual_type": pbi_type,
            "position": {
                "x": pos.get("x", 0),
                "y": pos.get("y", 0),
                "width": size.get("width", 300),
                "height": size.get("height", 200),
            },
            "config": {
                "singleVisual": {
                    "visualType": pbi_type,
                    "projections": {},
                },
            },
        }

        # Add column projections for tables
        if "columns" in visual:
            config["config"]["singleVisual"]["projections"]["Values"] = [
                {"queryRef": col.get("name", "")} for col in visual["columns"]
            ]

        # Add style
        if visual.get("style"):
            config["config"]["singleVisual"]["vcObjects"] = {
                "general": [{"properties": visual["style"]}],
            }

        return config

    def _write_report_config(self, report_dir: Path) -> Path:
        """Write report-level configuration."""
        config = {
            "version": "4.0",
            "themeCollection": {
                "baseTheme": {
                    "name": "CY24SU06",
                    "reportVersionAtImport": "5.54",
                    "type": 2,
                },
            },
            "activeSectionIndex": 0,
        }
        path = report_dir / "definition" / "report.json"
        self._write_json(path, config)
        return path

    def _write_static_resources(self, report_dir: Path) -> Path:
        """Create static resources directory with default theme."""
        res_dir = report_dir / "StaticResources" / "SharedResources" / "BaseThemes"
        res_dir.mkdir(parents=True, exist_ok=True)
        theme = {
            "name": "CY24SU06",
            "dataColors": [
                "#118DFF", "#12239E", "#E66C37", "#6B007B",
                "#E044A7", "#744EC2", "#D9B300", "#D64550",
            ],
            "background": "#FFFFFF",
            "foreground": "#252423",
            "tableAccent": "#118DFF",
        }
        path = res_dir / "CY24SU06.json"
        self._write_json(path, theme)
        return path

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
