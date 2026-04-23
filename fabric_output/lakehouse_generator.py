"""Lakehouse generator — Delta table DDL from OpenText metadata."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .fabric_constants import sanitize_table_name, sanitize_column_name, spark_type

logger = logging.getLogger(__name__)

# Core Lakehouse tables for document management
CORE_TABLES: dict[str, list[tuple[str, str, str]]] = {
    "documents": [
        ("document_id", "STRING", "Primary key — OT node ID or r_object_id"),
        ("name", "STRING", "Document name"),
        ("path", "STRING", "Original folder path"),
        ("mime_type", "STRING", "MIME type"),
        ("file_size", "BIGINT", "Size in bytes"),
        ("created_by", "STRING", "Creator user"),
        ("created_date", "TIMESTAMP", "Creation date"),
        ("modified_by", "STRING", "Last modifier"),
        ("modified_date", "TIMESTAMP", "Last modified date"),
        ("source_system", "STRING", "content_server or documentum"),
        ("source_id", "STRING", "Original ID in source system"),
        ("sensitivity_label", "STRING", "Purview sensitivity label"),
        ("onelake_path", "STRING", "Path in OneLake storage"),
        ("checksum_sha256", "STRING", "Content checksum"),
    ],
    "folders": [
        ("folder_id", "STRING", "Primary key"),
        ("name", "STRING", "Folder name"),
        ("parent_id", "STRING", "Parent folder ID"),
        ("path", "STRING", "Full path"),
        ("depth", "INT", "Depth in tree"),
        ("source_system", "STRING", "Source system"),
    ],
    "metadata": [
        ("node_id", "STRING", "Reference to document or folder"),
        ("category_name", "STRING", "OT category name"),
        ("attribute_name", "STRING", "Attribute name"),
        ("attribute_value", "STRING", "Attribute value"),
        ("data_type", "STRING", "Value data type"),
    ],
    "permissions": [
        ("node_id", "STRING", "Reference to document or folder"),
        ("principal_name", "STRING", "User or group name"),
        ("principal_type", "STRING", "user or group"),
        ("access_level", "STRING", "read, write, delete, admin"),
        ("entra_identity", "STRING", "Mapped Entra ID identity"),
        ("source_system", "STRING", "Source system"),
    ],
    "versions": [
        ("document_id", "STRING", "Reference to document"),
        ("version_number", "INT", "Version number"),
        ("version_id", "STRING", "Version ID in source"),
        ("created_by", "STRING", "Creator"),
        ("created_date", "TIMESTAMP", "Creation date"),
        ("file_size", "BIGINT", "Size in bytes"),
        ("mime_type", "STRING", "MIME type"),
        ("is_current", "BOOLEAN", "Is the current version"),
    ],
    "audit_log": [
        ("entry_id", "STRING", "Audit entry ID"),
        ("timestamp", "TIMESTAMP", "Event time"),
        ("action", "STRING", "Migration action"),
        ("source_type", "STRING", "Source system"),
        ("source_id", "STRING", "Source item ID"),
        ("target_path", "STRING", "Target in Fabric"),
        ("status", "STRING", "success, error, warning"),
        ("details", "STRING", "Event details"),
    ],
}


class LakehouseGenerator:
    """Generates Delta table DDL and schema definitions for Fabric Lakehouse."""

    def __init__(self, lakehouse_name: str = "OpenTextMigration"):
        self.lakehouse_name = sanitize_table_name(lakehouse_name)

    def generate_ddl(
        self,
        custom_tables: dict[str, list[tuple[str, str, str]]] | None = None,
    ) -> dict[str, str]:
        """Generate CREATE TABLE DDL for all Lakehouse tables.

        Returns dict of {table_name: ddl_string}.
        """
        tables = dict(CORE_TABLES)
        if custom_tables:
            tables.update(custom_tables)

        ddl: dict[str, str] = {}
        for table_name, columns in tables.items():
            safe_name = sanitize_table_name(table_name)
            col_defs = []
            for col_name, col_type, comment in columns:
                safe_col = sanitize_column_name(col_name)
                col_defs.append(f"    {safe_col} {col_type} COMMENT '{comment}'")

            ddl[safe_name] = (
                f"CREATE TABLE IF NOT EXISTS {self.lakehouse_name}.{safe_name} (\n"
                + ",\n".join(col_defs)
                + "\n) USING DELTA"
            )

        logger.info("Generated DDL for %d tables", len(ddl))
        return ddl

    def generate_metadata_tables(
        self,
        metadata: list[dict[str, Any]],
    ) -> dict[str, list[tuple[str, str, str]]]:
        """Generate custom tables from OT category schemas.

        Inspects metadata to discover category-specific columns and creates
        dedicated tables for rich categories.
        """
        category_schemas: dict[str, set[str]] = {}

        for entry in metadata:
            for cat in entry.get("categories", []):
                cat_name = cat.get("category_name", "unknown")
                attrs = cat.get("attributes", {})
                if attrs:
                    key = sanitize_table_name(f"cat_{cat_name}")
                    if key not in category_schemas:
                        category_schemas[key] = set()
                    category_schemas[key].update(attrs.keys())

        custom: dict[str, list[tuple[str, str, str]]] = {}
        for table_name, columns in category_schemas.items():
            col_defs: list[tuple[str, str, str]] = [
                ("node_id", "STRING", "Reference to document/folder"),
            ]
            for col in sorted(columns):
                safe_col = sanitize_column_name(col)
                col_defs.append((safe_col, "STRING", f"Category attribute: {col}"))
            custom[table_name] = col_defs

        return custom

    def generate_folder_structure(
        self,
        nodes: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        """Map OT folder tree → OneLake directory structure.

        Returns list of {source_path, onelake_path} mappings.
        """
        mappings: list[dict[str, str]] = []
        for node in nodes:
            if node.get("type") in (0, "dm_folder", "dm_cabinet"):  # folder types
                source_path = node.get("path", f"/{node.get('name', '')}")
                safe_parts = [sanitize_table_name(p) for p in source_path.strip("/").split("/") if p]
                onelake_path = "/".join(safe_parts)
                mappings.append({
                    "source_path": source_path,
                    "onelake_path": f"Files/{onelake_path}",
                    "node_id": str(node.get("id", "")),
                    "name": node.get("name", ""),
                })
        return mappings

    def export(self, output_dir: str | Path) -> dict[str, Path]:
        """Export all DDL and schema files."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        files: dict[str, Path] = {}

        ddl = self.generate_ddl()

        # Combined DDL script
        all_ddl = "\n\n".join(ddl.values())
        ddl_path = out / "lakehouse_ddl.sql"
        ddl_path.write_text(all_ddl, encoding="utf-8")
        files["lakehouse_ddl.sql"] = ddl_path

        # Schema JSON
        schema = {
            "lakehouse_name": self.lakehouse_name,
            "tables": {
                name: [{"name": c[0], "type": c[1], "comment": c[2]} for c in cols]
                for name, cols in CORE_TABLES.items()
            },
        }
        schema_path = out / "lakehouse_schema.json"
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)
        files["lakehouse_schema.json"] = schema_path

        return files
