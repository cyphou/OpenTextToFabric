"""OCR client — integration with Azure AI Document Intelligence."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class OCRClient:
    """Client for Azure AI Document Intelligence (optional dependency).

    This module uses only stdlib. The azure-ai-documentintelligence package
    is imported lazily only when actually calling the Azure service.
    """

    def __init__(
        self,
        endpoint: str = "",
        key: str = "",
        model_id: str = "prebuilt-read",
    ):
        self.endpoint = endpoint
        self.key = key
        self.model_id = model_id
        self._available: bool | None = None

    @property
    def is_available(self) -> bool:
        """Check if OCR service is configured and accessible."""
        if self._available is None:
            self._available = bool(self.endpoint and self.key)
        return self._available

    def extract_text(self, file_path: str | Path) -> dict[str, Any]:
        """Extract text from a document using Azure AI Document Intelligence.

        Returns dict with extracted text, pages, and confidence.
        Falls back to empty result if service is not available.
        """
        if not self.is_available:
            logger.debug("OCR service not configured, skipping: %s", file_path)
            return {"text": "", "pages": [], "status": "skipped"}

        path = Path(file_path)
        if not path.exists():
            return {"text": "", "pages": [], "status": "file_not_found"}

        # Lazy import — only used when OCR is actually requested
        try:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from azure.core.credentials import AzureKeyCredential

            client = DocumentIntelligenceClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.key),
            )

            with open(path, "rb") as f:
                poller = client.begin_analyze_document(
                    model_id=self.model_id,
                    body=f,
                    content_type="application/octet-stream",
                )
                result = poller.result()

            pages: list[dict[str, Any]] = []
            full_text = ""

            if hasattr(result, "content"):
                full_text = result.content or ""

            if hasattr(result, "pages"):
                for page in result.pages:
                    page_data: dict[str, Any] = {
                        "page_number": getattr(page, "page_number", 0),
                        "width": getattr(page, "width", 0),
                        "height": getattr(page, "height", 0),
                        "lines": [],
                    }
                    for line in getattr(page, "lines", []):
                        page_data["lines"].append({
                            "text": getattr(line, "content", ""),
                            "confidence": getattr(line, "confidence", 0),
                        })
                    pages.append(page_data)

            logger.info("OCR extracted %d characters from %s", len(full_text), path.name)
            return {"text": full_text, "pages": pages, "status": "success"}

        except ImportError:
            logger.warning("azure-ai-documentintelligence not installed, OCR unavailable")
            self._available = False
            return {"text": "", "pages": [], "status": "dependency_missing"}
        except Exception as e:
            logger.error("OCR failed for %s: %s", file_path, e)
            return {"text": "", "pages": [], "status": f"error: {e}"}

    def process_batch(
        self,
        file_paths: list[str | Path],
        output_dir: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        """Process multiple documents for OCR."""
        results: list[dict[str, Any]] = []
        for path in file_paths:
            result = self.extract_text(path)
            result["source_file"] = str(path)
            results.append(result)

        if output_dir:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            with open(out / "ocr_results.json", "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)

        return results
