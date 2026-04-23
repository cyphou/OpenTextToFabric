"""Version history extraction and mapping."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class VersionChain:
    """Represents a document's version history chain."""

    def __init__(self, document_id: str, versions: list[dict[str, Any]]):
        self.document_id = document_id
        self.versions = sorted(versions, key=lambda v: v.get("version_number", 0))

    @property
    def current_version(self) -> dict[str, Any]:
        """Get the most recent version."""
        return self.versions[-1] if self.versions else {}

    @property
    def version_count(self) -> int:
        return len(self.versions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "version_count": self.version_count,
            "current_version": self.current_version.get("version_number", 0),
            "versions": self.versions,
        }


class VersionHandler:
    """Handles version chain extraction and mapping to OneLake strategy."""

    def __init__(self, strategy: str = "latest_only"):
        """
        Args:
            strategy: Version migration strategy.
                - "latest_only": Migrate only the latest version (default).
                - "all_versions": Migrate all versions as separate files.
                - "metadata_only": Migrate latest + version metadata table.
        """
        self.strategy = strategy

    def extract_version_chains(
        self,
        documents: list[dict[str, Any]],
    ) -> list[VersionChain]:
        """Extract version chains from document metadata."""
        chains: list[VersionChain] = []
        for doc in documents:
            doc_id = str(doc.get("node_id", doc.get("object_id", "")))
            versions = doc.get("versions", [])
            if versions:
                chains.append(VersionChain(doc_id, versions))
        logger.info("Extracted %d version chains", len(chains))
        return chains

    def plan_version_migration(
        self,
        chains: list[VersionChain],
    ) -> list[dict[str, Any]]:
        """Plan which versions to migrate based on strategy.

        Returns list of version entries to download.
        """
        plan: list[dict[str, Any]] = []

        for chain in chains:
            if self.strategy == "latest_only":
                current = chain.current_version
                if current:
                    plan.append({
                        "document_id": chain.document_id,
                        "version_number": current.get("version_number", 0),
                        "action": "download",
                    })
            elif self.strategy == "all_versions":
                for v in chain.versions:
                    plan.append({
                        "document_id": chain.document_id,
                        "version_number": v.get("version_number", 0),
                        "action": "download",
                    })
            elif self.strategy == "metadata_only":
                current = chain.current_version
                if current:
                    plan.append({
                        "document_id": chain.document_id,
                        "version_number": current.get("version_number", 0),
                        "action": "download",
                    })
                for v in chain.versions:
                    if v != chain.current_version:
                        plan.append({
                            "document_id": chain.document_id,
                            "version_number": v.get("version_number", 0),
                            "action": "metadata_only",
                        })

        logger.info("Version migration plan: %d entries (strategy: %s)", len(plan), self.strategy)
        return plan

    def build_version_table(
        self,
        chains: list[VersionChain],
    ) -> list[dict[str, Any]]:
        """Build version metadata table for Lakehouse Delta table."""
        rows: list[dict[str, Any]] = []
        for chain in chains:
            for v in chain.versions:
                rows.append({
                    "document_id": chain.document_id,
                    "version_number": v.get("version_number", 0),
                    "version_id": v.get("version_id", ""),
                    "created_by": v.get("created_by", ""),
                    "create_date": v.get("create_date", ""),
                    "file_size": v.get("file_size", 0),
                    "mime_type": v.get("mime_type", ""),
                    "description": v.get("description", ""),
                    "is_current": v == chain.current_version,
                })
        return rows
