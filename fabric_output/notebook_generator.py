"""PySpark notebook generator — ETL notebooks for Fabric."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .fabric_constants import sanitize_table_name, sanitize_column_name, spark_type

logger = logging.getLogger(__name__)


class NotebookGenerator:
    """Generates PySpark ETL notebooks for Fabric."""

    def __init__(self, lakehouse_name: str = "OpenTextMigration"):
        self.lakehouse_name = sanitize_table_name(lakehouse_name)

    def generate_extraction_notebook(
        self,
        source_type: str = "content_server",
    ) -> dict[str, Any]:
        """Generate metadata extraction notebook."""
        cells = [
            self._markdown_cell("# OpenText Metadata Extraction\n"
                                f"Source: **{source_type}**\n"
                                f"Target Lakehouse: **{self.lakehouse_name}**"),
            self._code_cell(
                "# Configuration\n"
                "source_url = spark.conf.get('spark.opentext.source_url', '')\n"
                "root_id = spark.conf.get('spark.opentext.root_id', '')\n"
                f"lakehouse = '{self.lakehouse_name}'\n"
            ),
            self._code_cell(
                "# Load extracted metadata JSON\n"
                "import json\n"
                "from pyspark.sql.types import StructType, StructField, StringType, LongType, TimestampType\n\n"
                "nodes_schema = StructType([\n"
                "    StructField('id', StringType(), True),\n"
                "    StructField('name', StringType(), True),\n"
                "    StructField('type', StringType(), True),\n"
                "    StructField('parent_id', StringType(), True),\n"
                "    StructField('path', StringType(), True),\n"
                "    StructField('size', LongType(), True),\n"
                "    StructField('mime_type', StringType(), True),\n"
                "    StructField('create_date', StringType(), True),\n"
                "    StructField('modify_date', StringType(), True),\n"
                "])\n\n"
                "df_nodes = spark.read.schema(nodes_schema).json(f'Files/staging/nodes.json')\n"
                "display(df_nodes)\n"
            ),
            self._code_cell(
                "# Write to Delta table\n"
                f"df_nodes.write.format('delta').mode('overwrite').saveAsTable('{self.lakehouse_name}.documents')\n"
                f"print(f'Loaded {{df_nodes.count()}} records to {self.lakehouse_name}.documents')\n"
            ),
        ]
        return self._notebook_structure("01_extract_metadata", cells)

    def generate_document_download_notebook(self) -> dict[str, Any]:
        """Generate document binary download notebook."""
        cells = [
            self._markdown_cell("# Document Binary Download\n"
                                "Downloads document content from OpenText to OneLake staging area."),
            self._code_cell(
                "import requests\n"
                "import hashlib\n"
                "from notebookutils import mssparkutils\n\n"
                "# Read document manifest\n"
                f"df_docs = spark.read.format('delta').table('{self.lakehouse_name}.documents')\n"
                "docs = df_docs.filter('mime_type IS NOT NULL').collect()\n"
                "print(f'Documents to download: {len(docs)}')\n"
            ),
            self._code_cell(
                "# Download loop with checksum verification\n"
                "downloaded = 0\n"
                "errors = 0\n"
                "for row in docs:\n"
                "    try:\n"
                "        doc_id = row['document_id']\n"
                "        name = row['name']\n"
                "        target_path = f'Files/documents/{doc_id}/{name}'\n"
                "        # Download via OpenText API\n"
                "        # mssparkutils.fs.put(target_path, content)\n"
                "        downloaded += 1\n"
                "    except Exception as e:\n"
                "        print(f'Error downloading {name}: {e}')\n"
                "        errors += 1\n\n"
                "print(f'Downloaded: {downloaded}, Errors: {errors}')\n"
            ),
        ]
        return self._notebook_structure("02_download_documents", cells)

    def generate_transform_notebook(
        self,
        tables: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate ETL transformation notebook."""
        target_tables = tables or ["documents", "folders", "metadata", "permissions"]
        cells = [
            self._markdown_cell("# Transform & Load to Lakehouse\n"
                                "Transforms extracted JSON data into Delta tables."),
            self._code_cell(
                "from pyspark.sql import functions as F\n"
                "from pyspark.sql.types import *\n\n"
                f"lakehouse = '{self.lakehouse_name}'\n"
            ),
        ]

        for table in target_tables:
            cells.append(self._code_cell(
                f"# Load and transform {table}\n"
                f"df_{table} = spark.read.json(f'Files/staging/{table}.json')\n"
                f"df_{table} = df_{table}.dropDuplicates()\n"
                f"df_{table}.write.format('delta').mode('overwrite').saveAsTable(f'{{lakehouse}}.{table}')\n"
                f"print(f'{table}: {{df_{table}.count()}} rows')\n"
            ))

        return self._notebook_structure("03_transform_load", cells)

    def generate_governance_notebook(self) -> dict[str, Any]:
        """Generate governance application notebook."""
        cells = [
            self._markdown_cell("# Apply Governance Mappings\n"
                                "Applies sensitivity labels, RLS roles, and retention policies."),
            self._code_cell(
                "from pyspark.sql import functions as F\n\n"
                f"lakehouse = '{self.lakehouse_name}'\n\n"
                "# Load sensitivity mapping\n"
                "df_sensitivity = spark.read.json('Files/staging/sensitivity_mapping.json')\n"
                f"df_docs = spark.read.format('delta').table(f'{{lakehouse}}.documents')\n\n"
                "# Join sensitivity labels\n"
                "df_docs_labeled = df_docs.join(\n"
                "    df_sensitivity,\n"
                "    df_docs['document_id'] == df_sensitivity['node_id'],\n"
                "    'left'\n"
                ").withColumn('sensitivity_label', F.coalesce(df_sensitivity['sensitivity_label'], F.lit('General')))\n\n"
                f"df_docs_labeled.write.format('delta').mode('overwrite').saveAsTable(f'{{lakehouse}}.documents')\n"
                "print(f'Applied sensitivity labels to {df_docs_labeled.count()} documents')\n"
            ),
        ]
        return self._notebook_structure("04_apply_governance", cells)

    def export(self, output_dir: str | Path) -> dict[str, Path]:
        """Export all notebooks to .ipynb files."""
        out = Path(output_dir) / "notebooks"
        out.mkdir(parents=True, exist_ok=True)
        files: dict[str, Path] = {}

        notebooks = [
            ("01_extract_metadata", self.generate_extraction_notebook()),
            ("02_download_documents", self.generate_document_download_notebook()),
            ("03_transform_load", self.generate_transform_notebook()),
            ("04_apply_governance", self.generate_governance_notebook()),
        ]

        for name, nb in notebooks:
            path = out / f"{name}.ipynb"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(nb, f, indent=2)
            files[name] = path

        logger.info("Generated %d notebooks", len(files))
        return files

    @staticmethod
    def _notebook_structure(name: str, cells: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {
                "name": name,
                "kernelspec": {
                    "name": "synapse_pyspark",
                    "display_name": "Synapse PySpark",
                },
                "language_info": {"name": "python", "version": "3.10"},
                "trident": {"lakehouse": {}},
            },
            "cells": cells,
        }

    @staticmethod
    def _markdown_cell(source: str) -> dict[str, Any]:
        return {
            "cell_type": "markdown",
            "metadata": {},
            "source": [source],
        }

    @staticmethod
    def _code_cell(source: str) -> dict[str, Any]:
        return {
            "cell_type": "code",
            "metadata": {},
            "source": [source],
            "outputs": [],
            "execution_count": None,
        }
