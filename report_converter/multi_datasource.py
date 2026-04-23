"""Multi-data-source detection and DirectLake/Composite model recommendation."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Connector types that can use DirectLake mode
DIRECTLAKE_CONNECTORS = frozenset({
    "oracle",  # via Lakehouse ingestion
    "sqlserver",
    "postgresql",
    "mysql",
    "odbc",
    "jdbc",
})

# Connectors that require Import or DirectQuery only
IMPORT_ONLY_CONNECTORS = frozenset({
    "csv",
    "xml",
    "json",
    "excel",
    "flat-file",
    "rest-api",
})


class DataSourceAnalyzer:
    """Analyzes data source configurations to determine optimal semantic model mode.

    Supported modes:
    - Import: All data loaded into PBI dataset (simple, best performance)
    - DirectLake: Data stays in Lakehouse, read via Parquet (Fabric-native)
    - Composite: Mix of Import + DirectQuery for multi-source scenarios
    """

    def analyze(
        self,
        connections: list[dict[str, Any]],
        datasets: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyze data sources and recommend model mode.

        Args:
            connections: List of connection dicts from extraction.
            datasets: List of dataset dicts from extraction.

        Returns:
            Analysis dict with mode, sources, and recommendations.
        """
        sources = self._classify_sources(connections)
        cross_source_joins = self._detect_cross_source_joins(datasets)

        mode = self._recommend_mode(sources, cross_source_joins)

        result: dict[str, Any] = {
            "mode": mode,
            "sources": sources,
            "total_connections": len(connections),
            "total_datasets": len(datasets),
            "cross_source_joins": cross_source_joins,
            "recommendations": self._build_recommendations(mode, sources, cross_source_joins),
        }

        logger.info(
            "Data source analysis: %d sources → %s mode",
            len(connections), mode,
        )
        return result

    def _classify_sources(
        self,
        connections: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Classify each connection by type and DirectLake eligibility."""
        sources: list[dict[str, Any]] = []

        for conn in connections:
            driver = conn.get("driver", "").lower()
            conn_type = conn.get("type", "jdbc").lower()

            # Determine the connector category
            if any(db in driver for db in ("oracle", "thin", "oci")):
                category = "oracle"
            elif any(db in driver for db in ("sqlserver", "mssql", "jtds")):
                category = "sqlserver"
            elif "postgres" in driver:
                category = "postgresql"
            elif "mysql" in driver:
                category = "mysql"
            elif conn_type in ("csv", "flat-file", "xml", "json", "excel"):
                category = conn_type
            else:
                category = "other"

            directlake_eligible = category in DIRECTLAKE_CONNECTORS
            import_only = category in IMPORT_ONLY_CONNECTORS

            sources.append({
                "name": conn.get("name", "Unknown"),
                "category": category,
                "driver": driver,
                "directlake_eligible": directlake_eligible,
                "import_only": import_only,
                "url": conn.get("url", ""),
            })

        return sources

    def _detect_cross_source_joins(
        self,
        datasets: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        """Detect datasets that reference multiple data sources."""
        joins: list[dict[str, str]] = []

        # Group datasets by their data source
        ds_by_source: dict[str, list[str]] = {}
        for ds in datasets:
            source = ds.get("data_source", "default")
            ds_name = ds.get("name", "")
            if source not in ds_by_source:
                ds_by_source[source] = []
            ds_by_source[source].append(ds_name)

        # If multiple sources, note the cross-source join potential
        source_names = list(ds_by_source.keys())
        if len(source_names) > 1:
            for i, s1 in enumerate(source_names):
                for s2 in source_names[i + 1:]:
                    joins.append({
                        "source_a": s1,
                        "source_b": s2,
                        "datasets_a": ", ".join(ds_by_source[s1]),
                        "datasets_b": ", ".join(ds_by_source[s2]),
                    })

        return joins

    def _recommend_mode(
        self,
        sources: list[dict[str, Any]],
        cross_joins: list[dict[str, str]],
    ) -> str:
        """Recommend the optimal model mode."""
        if not sources:
            return "import"

        all_directlake = all(s.get("directlake_eligible") for s in sources)
        any_import_only = any(s.get("import_only") for s in sources)

        if len(sources) == 1:
            if all_directlake:
                return "directlake"
            return "import"

        if cross_joins:
            return "composite"

        if all_directlake:
            return "directlake"

        if any_import_only:
            return "import"

        return "composite"

    @staticmethod
    def _build_recommendations(
        mode: str,
        sources: list[dict[str, Any]],
        cross_joins: list[dict[str, str]],
    ) -> list[str]:
        """Build actionable recommendations based on analysis."""
        recs: list[str] = []

        if mode == "directlake":
            recs.append("Ingest all data into Fabric Lakehouse for DirectLake mode")
            recs.append("Use Data Factory pipeline for ETL from source to Lakehouse")
            recs.append("Ensure all tables use Delta format in OneLake")
        elif mode == "composite":
            recs.append(f"Use Composite model: {len(sources)} data sources detected")
            if cross_joins:
                recs.append(
                    f"Cross-source joins found: {len(cross_joins)} — "
                    "consider consolidating into Lakehouse"
                )
            recs.append("Configure DirectQuery for large tables, Import for dimension tables")
        else:
            recs.append("Import mode: all data loaded into PBI dataset at refresh time")

        for src in sources:
            if src.get("import_only"):
                recs.append(
                    f"Source '{src['name']}' ({src['category']}) is Import-only — "
                    "data will be copied into the semantic model"
                )

        return recs
