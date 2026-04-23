"""Rendition handling — extract and manage document format variants."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Rendition:
    """Represents a single rendition of a document."""
    document_id: str
    format: str  # e.g., "application/pdf", "image/png"
    rendition_type: str  # "primary", "pdf", "thumbnail", "web_viewable"
    size: int = 0
    download_url: str = ""
    local_path: str = ""


class RenditionHandler:
    """Manages document renditions — PDF, thumbnail, web viewable variants."""

    # Common rendition types and their typical MIME types
    RENDITION_MAP: dict[str, list[str]] = {
        "pdf": ["application/pdf"],
        "thumbnail": ["image/png", "image/jpeg"],
        "web_viewable": ["text/html", "application/xhtml+xml"],
        "primary": [],  # original format
    }

    def __init__(self, staging_dir: str | Path):
        self.staging_dir = Path(staging_dir) / "renditions"
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def classify_rendition(self, mime_type: str) -> str:
        """Classify a rendition by its MIME type."""
        for rtype, mimes in self.RENDITION_MAP.items():
            if mime_type in mimes:
                return rtype
        return "other"

    def extract_rendition_list(
        self,
        documents: list[dict[str, Any]],
    ) -> list[Rendition]:
        """Extract rendition info from document metadata.

        Args:
            documents: List of document entries from documents.json.

        Returns:
            List of Rendition objects with download URLs.
        """
        renditions: list[Rendition] = []

        for doc in documents:
            doc_id = doc.get("node_id", doc.get("object_id", ""))

            # Content Server renditions (from versions)
            for version in doc.get("versions", []):
                renditions.append(Rendition(
                    document_id=str(doc_id),
                    format=version.get("mime_type", ""),
                    rendition_type="primary",
                    size=version.get("file_size", 0),
                ))

            # Documentum renditions
            for rend in doc.get("renditions", []):
                mime = rend.get("full_format", rend.get("mime_type", ""))
                renditions.append(Rendition(
                    document_id=str(doc_id),
                    format=mime,
                    rendition_type=self.classify_rendition(mime),
                    size=rend.get("r_content_size", rend.get("size", 0)),
                ))

        logger.info("Found %d renditions across %d documents", len(renditions), len(documents))
        return renditions

    def build_rendition_manifest(
        self,
        renditions: list[Rendition],
    ) -> list[dict[str, Any]]:
        """Build a manifest for OneLake storage organization."""
        manifest: list[dict[str, Any]] = []
        for r in renditions:
            manifest.append({
                "document_id": r.document_id,
                "format": r.format,
                "rendition_type": r.rendition_type,
                "size": r.size,
                "onelake_path": f"renditions/{r.rendition_type}/{r.document_id}",
            })
        return manifest
