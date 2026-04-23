"""Data Factory pipeline generator — ingestion pipeline JSON for Fabric."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .fabric_constants import sanitize_table_name

logger = logging.getLogger(__name__)


class PipelineGenerator:
    """Generates Data Factory pipeline definitions for Fabric."""

    def __init__(self, pipeline_name: str = "OpenText_Migration"):
        self.pipeline_name = pipeline_name

    def generate_master_pipeline(
        self,
        source_type: str = "content_server",
    ) -> dict[str, Any]:
        """Generate master orchestration pipeline with staged execution."""
        return {
            "name": self.pipeline_name,
            "properties": {
                "description": f"Master pipeline for OpenText {source_type} migration",
                "activities": [
                    self._stage_activity("Stage_1_Metadata", "Extract metadata from OpenText",
                                         "Notebook", "01_extract_metadata"),
                    self._stage_activity("Stage_2_Documents", "Download document binaries",
                                         "Notebook", "02_download_documents",
                                         depends_on=["Stage_1_Metadata"]),
                    self._stage_activity("Stage_3_Transform", "Transform and load to Lakehouse",
                                         "Notebook", "03_transform_load",
                                         depends_on=["Stage_2_Documents"]),
                    self._stage_activity("Stage_4_Governance", "Apply governance mappings",
                                         "Notebook", "04_apply_governance",
                                         depends_on=["Stage_3_Transform"]),
                ],
                "parameters": {
                    "source_url": {"type": "string", "defaultValue": ""},
                    "root_id": {"type": "string", "defaultValue": ""},
                    "output_lakehouse": {"type": "string", "defaultValue": "OpenTextMigration"},
                },
                "annotations": ["opentext-migration", source_type],
            },
        }

    def generate_ingestion_pipeline(
        self,
        table_name: str,
        source_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate a REST connector → Lakehouse copy pipeline for a single table."""
        safe_table = sanitize_table_name(table_name)
        return {
            "name": f"Ingest_{safe_table}",
            "properties": {
                "description": f"Ingest {table_name} from OpenText REST API to Lakehouse",
                "activities": [
                    {
                        "name": f"Copy_{safe_table}",
                        "type": "Copy",
                        "inputs": [{
                            "type": "RestResource",
                            "linkedService": {
                                "referenceName": "OpenText_REST",
                                "type": "LinkedServiceReference",
                            },
                            "typeProperties": {
                                "relativeUrl": source_config.get("endpoint", ""),
                                "requestMethod": "GET",
                                "paginationRules": {
                                    "QueryParameters.page": "RANGE:1:100:1",
                                },
                            },
                        }],
                        "outputs": [{
                            "type": "LakehouseTable",
                            "typeProperties": {
                                "table": safe_table,
                                "format": "delta",
                            },
                        }],
                        "typeProperties": {
                            "source": {"type": "RestSource"},
                            "sink": {"type": "LakehouseSink", "writeBehavior": "upsert"},
                        },
                    },
                ],
                "parameters": {
                    "watermark": {
                        "type": "string",
                        "defaultValue": "1970-01-01T00:00:00Z",
                    },
                },
            },
        }

    def generate_incremental_pipeline(
        self,
        table_name: str,
    ) -> dict[str, Any]:
        """Generate incremental sync pipeline with watermark logic."""
        safe_table = sanitize_table_name(table_name)
        return {
            "name": f"IncrSync_{safe_table}",
            "properties": {
                "description": f"Incremental sync for {table_name} using modification date watermark",
                "activities": [
                    {
                        "name": "Get_Watermark",
                        "type": "Lookup",
                        "typeProperties": {
                            "source": {
                                "type": "LakehouseSource",
                                "query": f"SELECT MAX(modified_date) AS last_watermark FROM {safe_table}",
                            },
                        },
                    },
                    {
                        "name": f"Copy_Incremental_{safe_table}",
                        "type": "Copy",
                        "dependsOn": [{"activity": "Get_Watermark", "dependencyConditions": ["Succeeded"]}],
                        "typeProperties": {
                            "source": {
                                "type": "RestSource",
                                "additionalColumns": {
                                    "modified_after": "@activity('Get_Watermark').output.firstRow.last_watermark",
                                },
                            },
                            "sink": {"type": "LakehouseSink", "writeBehavior": "upsert"},
                        },
                    },
                ],
            },
        }

    def export(
        self,
        output_dir: str | Path,
        source_type: str = "content_server",
        tables: list[str] | None = None,
    ) -> dict[str, Path]:
        """Export all pipeline definitions to JSON files."""
        out = Path(output_dir) / "pipelines"
        out.mkdir(parents=True, exist_ok=True)
        files: dict[str, Path] = {}

        # Master pipeline
        master = self.generate_master_pipeline(source_type)
        path = out / f"{self.pipeline_name}.json"
        self._write_json(path, master)
        files["master_pipeline"] = path

        # Per-table ingestion pipelines
        if tables:
            for table in tables:
                pipeline = self.generate_ingestion_pipeline(table, {})
                p = out / f"Ingest_{sanitize_table_name(table)}.json"
                self._write_json(p, pipeline)
                files[f"ingest_{table}"] = p

        logger.info("Generated %d pipeline definitions", len(files))
        return files

    @staticmethod
    def _stage_activity(
        name: str,
        description: str,
        activity_type: str,
        notebook_name: str,
        depends_on: list[str] | None = None,
    ) -> dict[str, Any]:
        activity: dict[str, Any] = {
            "name": name,
            "type": activity_type,
            "description": description,
            "typeProperties": {
                "notebook": {"referenceName": notebook_name, "type": "NotebookReference"},
            },
        }
        if depends_on:
            activity["dependsOn"] = [
                {"activity": dep, "dependencyConditions": ["Succeeded"]}
                for dep in depends_on
            ]
        return activity

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
