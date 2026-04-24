"""PBIP generator — .pbip project output (PBIR v4.0 + TMDL).

Generates a complete Power BI project that can be opened directly in
Power BI Desktop.  Follows the exact PBIR v4.0 folder layout:

    {Name}/
    ├── {Name}.pbip
    ├── {Name}.Report/
    │   ├── .platform
    │   ├── definition.pbir            ← directly in .Report/
    │   └── definition/
    │       ├── version.json
    │       ├── report.json
    │       └── pages/
    │           ├── pages.json
    │           └── ReportSection/
    │               ├── page.json
    │               └── visuals/
    │                   └── {id}/visual.json
    └── {Name}.SemanticModel/
        ├── .platform
        ├── definition.pbism
        └── definition/
            ├── model.tmdl
            └── tables/…
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from fabric_output.fabric_constants import sanitize_name

logger = logging.getLogger(__name__)

# Microsoft JSON schemas (pinned versions)
_SCHEMA_PBIP = "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json"
_SCHEMA_PBIR = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json"
_SCHEMA_PLATFORM = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
_SCHEMA_PBISM = "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json"
_SCHEMA_REPORT = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/2.0.0/schema.json"
_SCHEMA_VERSION = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json"
_SCHEMA_PAGES = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json"
_SCHEMA_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
_SCHEMA_VISUAL = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json"

THEME_NAME = "CY24SU06"


class PBIPGenerator:
    """Generates .pbip Power BI project files (PBIR v4.0 format)."""

    def __init__(self, report_name: str = "MigratedReport"):
        self.report_name = report_name
        self._report_id = str(uuid.uuid4())
        self._model_id = str(uuid.uuid4())
        self._bookmarks: list[dict[str, Any]] = []

    def add_bookmark(
        self,
        name: str,
        display_name: str = "",
        page_id: str = "",
        visual_states: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        """Add a bookmark to the report.

        Args:
            name: Bookmark name.
            display_name: Display name (defaults to name).
            page_id: Target page ID.
            visual_states: Dict of {visual_name: is_visible}.
        """
        bookmark = {
            "name": name,
            "displayName": display_name or name,
            "reportId": self._report_id,
            "explorationState": {
                "version": "1",
                "activeSection": page_id or "",
                "filters": {"byExpr": [], "byColumn": []},
            },
        }
        if visual_states:
            containers = {}
            for vname, visible in visual_states.items():
                containers[vname] = {
                    "singleVisual": {"visualType": ""},
                    "visibility": 0 if visible else 1,
                }
            bookmark["explorationState"]["sections"] = {
                page_id or "page": {"visualContainers": containers}
            }
        self._bookmarks.append(bookmark)
        return bookmark

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
        model_dir = out / f"{self.report_name}.SemanticModel"
        defn_dir = report_dir / "definition"

        report_dir.mkdir(parents=True, exist_ok=True)
        defn_dir.mkdir(parents=True, exist_ok=True)
        model_dir.mkdir(parents=True, exist_ok=True)

        # Clean stale page directories from prior runs to avoid orphan
        # "Page N" tabs appearing in PBI Desktop. The pages folder is
        # rebuilt from scratch every generation. If files are locked
        # (e.g. PBI Desktop has the project open) we fall back to
        # best-effort per-file removal so the generation can still proceed.
        pages_dir = defn_dir / "pages"
        if pages_dir.exists():
            import shutil
            def _on_error(func, path, _exc):
                try:
                    Path(path).chmod(0o600)
                    func(path)
                except Exception:
                    logger.warning("Could not remove stale path: %s", path)
            try:
                shutil.rmtree(pages_dir, onerror=_on_error)
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("Stale pages cleanup partially failed: %s", e)

        files: dict[str, Path] = {}

        # 1. .pbip project file
        files[".pbip"] = self._write_pbip(out)

        # 2. Report .platform (required by PBI Desktop)
        files["report.platform"] = self._write_platform(
            report_dir, "Report", self.report_name, self._report_id,
        )

        # 3. definition.pbir — directly in .Report/ (NOT inside definition/)
        files["definition.pbir"] = self._write_pbir(
            report_dir, semantic_model_path,
        )

        # 4. SemanticModel .platform
        files["model.platform"] = self._write_platform(
            model_dir, "SemanticModel", self.report_name, self._model_id,
        )

        # 5. definition.pbism
        files["definition.pbism"] = self._write_pbism(model_dir)

        # 6. version.json
        files["version.json"] = self._write_version(defn_dir)

        # 7. report.json
        files["report.json"] = self._write_report_config(defn_dir)

        # 8. Theme
        files["theme"] = self._write_theme(report_dir)

        # 9. Pages + visuals
        pages = self._build_pages(visuals)
        page_names: list[str] = []
        for i, page in enumerate(pages):
            page_id = page["id"]
            page_names.append(page_id)
            page_dir = defn_dir / "pages" / page_id
            page_dir.mkdir(parents=True, exist_ok=True)

            page_path = page_dir / "page.json"
            self._write_json(page_path, page["config"])
            files[f"page_{i}"] = page_path

            # Visual containers
            visuals_dir = page_dir / "visuals"
            visuals_dir.mkdir(parents=True, exist_ok=True)
            for j, vis in enumerate(page["visuals"]):
                vid = vis.get("name", f"v{uuid.uuid4().hex[:12]}")
                vdir = visuals_dir / vid
                vdir.mkdir(parents=True, exist_ok=True)
                vpath = vdir / "visual.json"
                self._write_json(vpath, vis)
                files[f"visual_{i}_{j}"] = vpath

        # 10. pages.json (page ordering)
        files["pages.json"] = self._write_pages_metadata(
            defn_dir, page_names,
        )

        # 11. bookmarks.json (if any bookmarks registered)
        if self._bookmarks:
            bookmarks_path = defn_dir / "bookmarks.json"
            self._write_json(bookmarks_path, {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/bookmarks/1.0.0/schema.json",
                "bookmarks": self._bookmarks,
            })
            files["bookmarks.json"] = bookmarks_path

        logger.info(
            "Generated .pbip project: %d pages, %d visuals at %s",
            len(pages),
            sum(len(p["visuals"]) for p in pages),
            out,
        )
        return files

    # ── File writers ──────────────────────────────────────────────

    def _write_pbip(self, out: Path) -> Path:
        pbip = {
            "$schema": _SCHEMA_PBIP,
            "version": "1.0",
            "artifacts": [
                {
                    "report": {
                        "path": f"{self.report_name}.Report",
                    },
                },
            ],
            "settings": {
                "enableAutoRecovery": True,
            },
        }
        path = out / f"{self.report_name}.pbip"
        self._write_json(path, pbip)
        return path

    def _write_platform(
        self,
        parent: Path,
        artifact_type: str,
        display_name: str,
        logical_id: str,
    ) -> Path:
        platform = {
            "$schema": _SCHEMA_PLATFORM,
            "metadata": {
                "type": artifact_type,
                "displayName": display_name,
            },
            "config": {
                "version": "2.0",
                "logicalId": logical_id,
            },
        }
        path = parent / ".platform"
        self._write_json(path, platform)
        return path

    def _write_pbir(self, report_dir: Path, semantic_model_path: str) -> Path:
        """Write definition.pbir directly inside .Report/ folder."""
        pbir = {
            "$schema": _SCHEMA_PBIR,
            "version": "4.0",
            "datasetReference": {
                "byPath": {
                    "path": semantic_model_path
                    or f"../{self.report_name}.SemanticModel",
                },
            },
        }
        path = report_dir / "definition.pbir"
        self._write_json(path, pbir)
        return path

    def _write_pbism(self, model_dir: Path) -> Path:
        pbism = {
            "$schema": _SCHEMA_PBISM,
            "version": "4.0",
            "settings": {},
        }
        path = model_dir / "definition.pbism"
        self._write_json(path, pbism)
        return path

    def _write_version(self, defn_dir: Path) -> Path:
        version = {
            "$schema": _SCHEMA_VERSION,
            "version": "2.0.0",
        }
        path = defn_dir / "version.json"
        self._write_json(path, version)
        return path

    def _write_report_config(self, defn_dir: Path) -> Path:
        config = {
            "$schema": _SCHEMA_REPORT,
            "themeCollection": {
                "baseTheme": {
                    "name": THEME_NAME,
                    "reportVersionAtImport": "5.58",
                    "type": "SharedResources",
                },
            },
            "resourcePackages": [
                {
                    "name": "SharedResources",
                    "type": "SharedResources",
                    "items": [
                        {
                            "name": THEME_NAME,
                            "path": f"BaseThemes/{THEME_NAME}.json",
                            "type": "BaseTheme",
                        },
                    ],
                },
            ],
            "settings": {
                "hideVisualContainerHeader": True,
                "useStylableVisualContainerHeader": True,
                "defaultDrillFilterOtherVisuals": True,
                "allowChangeFilterTypes": True,
                "useEnhancedTooltips": True,
            },
        }
        path = defn_dir / "report.json"
        self._write_json(path, config)
        return path

    def _write_theme(self, report_dir: Path) -> Path:
        res_dir = (
            report_dir
            / "StaticResources"
            / "SharedResources"
            / "BaseThemes"
        )
        res_dir.mkdir(parents=True, exist_ok=True)
        theme = {
            "name": THEME_NAME,
            "dataColors": [
                "#118DFF", "#12239E", "#E66C37", "#6B007B",
                "#E044A7", "#744EC2", "#D9B300", "#D64550",
            ],
            "background": "#FFFFFF",
            "foreground": "#252423",
            "tableAccent": "#118DFF",
        }
        path = res_dir / f"{THEME_NAME}.json"
        self._write_json(path, theme)
        return path

    def _write_pages_metadata(
        self, defn_dir: Path, page_names: list[str],
    ) -> Path:
        metadata = {
            "$schema": _SCHEMA_PAGES,
            "pageOrder": page_names,
            "activePageName": page_names[0] if page_names else "",
        }
        pages_dir = defn_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        path = pages_dir / "pages.json"
        self._write_json(path, metadata)
        return path

    # ── Page / visual builders ────────────────────────────────────

    def _build_pages(
        self,
        visuals: list[dict[str, Any]],
        max_visuals_per_page: int = 10,
    ) -> list[dict[str, Any]]:
        if not visuals:
            return [self._build_page("ReportSection", "Page 1", [])]

        pages: list[dict[str, Any]] = []
        current: list[dict[str, Any]] = []
        page_num = 0

        y_offset = 20
        for visual in visuals:
            positioned = dict(visual)
            size = positioned.get("size", {"width": 300, "height": 200})
            pos = dict(positioned.get("position", {}))
            pos["y"] = y_offset
            positioned["position"] = pos
            y_offset += size.get("height", 200) + 20

            current.append(self._build_visual_config(positioned))
            if len(current) >= max_visuals_per_page:
                page_id = "ReportSection" if page_num == 0 else f"ReportSection{uuid.uuid4().hex[:8]}"
                pages.append(self._build_page(page_id, f"Page {page_num + 1}", current))
                current = []
                page_num += 1
                y_offset = 20

        if current or not pages:
            page_id = "ReportSection" if page_num == 0 else f"ReportSection{uuid.uuid4().hex[:8]}"
            pages.append(self._build_page(page_id, f"Page {page_num + 1}", current))

        return pages

    def _build_page(
        self, page_id: str, display_name: str, visuals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "id": page_id,
            "config": {
                "$schema": _SCHEMA_PAGE,
                "name": page_id,
                "displayName": display_name,
                "displayOption": "FitToPage",
                "width": 1280,
                "height": 720,
            },
            "visuals": visuals,
        }

    def _build_visual_config(self, visual: dict[str, Any]) -> dict[str, Any]:
        pos = visual.get("position", {"x": 0, "y": 0})
        size = visual.get("size", {"width": 300, "height": 200})
        pbi_type = visual.get("visual_type", "textbox")
        name = visual.get("name", "") or uuid.uuid4().hex[:12]

        config: dict[str, Any] = {
            "$schema": _SCHEMA_VISUAL,
            "name": name,
            "position": {
                "x": pos.get("x", 0),
                "y": pos.get("y", 0),
                "z": 0,
                "width": size.get("width", 300),
                "height": size.get("height", 200),
                "tabOrder": 0,
            },
            "visual": {
                "visualType": pbi_type,
                "drillFilterOtherVisuals": True,
                "objects": {},
            },
        }

        # Projections / query for data-bound visuals
        if "columns" in visual:
            dataset = visual.get("dataset", "")
            cols = visual.get("columns", [])
            config["visual"]["query"] = self._build_query(pbi_type, dataset, cols)

        # Chart config → query projections
        elif "chart_config" in visual:
            chart = visual["chart_config"]
            dataset = visual.get("dataset", "")
            categories = chart.get("categories", [])
            series = chart.get("series", [])
            config["visual"]["query"] = self._build_chart_query(
                pbi_type, dataset, categories, series,
            )

        # Title
        if visual.get("name"):
            config["visual"]["visualContainerObjects"] = {
                "title": [
                    {
                        "properties": {
                            "show": {"expr": {"Literal": {"Value": "true"}}},
                            "text": {"expr": {"Literal": {"Value": f"'{visual['name']}'"}}},
                        },
                    },
                ],
            }

        return config

    # ── Query builders (PBIR v4.0 queryState format) ──────────────

    # Visual type → query role mapping
    _ROLE_MAP: dict[str, list[str]] = {
        "tableEx": ["Values"],
        "pivotTable": ["Rows", "Values"],
        "card": ["Fields"],
        "multiRowCard": ["Fields"],
        "kpi": ["Indicator"],
        "slicer": ["Values"],
        "textbox": [],
        "image": [],
    }
    # Chart visuals default to Category + Y
    _CHART_CATEGORY_ROLE = "Category"
    _CHART_VALUE_ROLE = "Y"

    def _build_query(
        self,
        visual_type: str,
        entity: str,
        columns: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build a PBIR v4.0 queryState from columns."""
        roles = self._ROLE_MAP.get(visual_type, ["Values"])
        if not roles:
            return {"queryState": {}}

        # Put all columns into the first role
        role_name = roles[0]
        projections = [
            self._make_projection(entity, col.get("name", ""))
            for col in columns
            if col.get("name")
        ]

        query_state: dict[str, Any] = {}
        if projections:
            query_state[role_name] = {"projections": projections}

        return {"queryState": query_state}

    def _build_chart_query(
        self,
        visual_type: str,
        entity: str,
        categories: list[Any],
        series: list[Any],
    ) -> dict[str, Any]:
        """Build a PBIR v4.0 queryState for chart visuals."""
        query_state: dict[str, Any] = {}

        if categories:
            cat_projections = []
            for cat in categories:
                name = cat if isinstance(cat, str) else cat.get("name", "")
                if name:
                    cat_projections.append(self._make_projection(entity, name))
            if cat_projections:
                query_state[self._CHART_CATEGORY_ROLE] = {
                    "projections": cat_projections,
                }

        if series:
            val_projections = []
            for s in series:
                name = s if isinstance(s, str) else s.get("name", "")
                if name:
                    val_projections.append(self._make_projection(entity, name))
            if val_projections:
                query_state[self._CHART_VALUE_ROLE] = {
                    "projections": val_projections,
                }

        return {"queryState": query_state}

    @staticmethod
    def _make_projection(entity: str, prop: str) -> dict[str, Any]:
        """Create a single RoleProjection entry.

        Both *entity* (table) and *prop* (column) are sanitized to match
        the TMDL identifiers produced by ``TMDLGenerator``.
        """
        safe_entity = sanitize_name(entity) if entity else ""
        safe_prop = sanitize_name(prop) if prop else ""
        return {
            "field": {
                "Column": {
                    "Expression": {"SourceRef": {"Entity": safe_entity}},
                    "Property": safe_prop,
                },
            },
            "queryRef": f"{safe_entity}.{safe_prop}" if safe_entity else safe_prop,
            "nativeQueryRef": safe_prop,
        }

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
