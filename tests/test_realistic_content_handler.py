"""Realistic tests for content handler modules using real-world document patterns.

Tests download, rendition, and versioning with:
- Real enterprise document types (PDF, DOCX, XLSX, VSDX)
- Real version chains from Content Server (draft → review → final)
- Documentum rendition patterns (PDF + JPEG thumbnail)
- Realistic file sizes and MIME types
"""

import tempfile
import unittest
from pathlib import Path

from content_handler.renditions import RenditionHandler, Rendition
from content_handler.versioning import VersionHandler, VersionChain
from tests.fixtures import (
    REALISTIC_VERSION_DOCS,
    REALISTIC_RENDITION_DOCS_CS,
    REALISTIC_RENDITION_DOCS_DCTM,
)


class TestRealisticRenditions(unittest.TestCase):
    """Tests with real document rendition patterns."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.handler = RenditionHandler(self.tmpdir)

    def test_cs_document_renditions(self):
        """Content Server docs have primary rendition from version info."""
        renditions = self.handler.extract_rendition_list(REALISTIC_RENDITION_DOCS_CS)
        self.assertEqual(len(renditions), 3)

        # PDF rendition — Rendition uses document_id (str)
        pdf_r = next(r for r in renditions if r.document_id == "54321")
        self.assertEqual(pdf_r.rendition_type, "primary")
        self.assertEqual(pdf_r.size, 2457600)

    def test_dctm_document_renditions(self):
        """Documentum docs have PDF + JPEG thumbnail renditions."""
        renditions = self.handler.extract_rendition_list(REALISTIC_RENDITION_DOCS_DCTM)
        self.assertEqual(len(renditions), 4)  # 2 docs × 2 renditions

        # Annual report has 2 renditions
        annual_renditions = [r for r in renditions if r.document_id == "0900000180001001"]
        self.assertEqual(len(annual_renditions), 2)
        # full_format "pdf" (short form) classified as "other" by RENDITION_MAP
        # which only recognizes "application/pdf"
        formats = {r.format for r in annual_renditions}
        self.assertIn("pdf", formats)

    def test_build_manifest_real_docs(self):
        """Build OneLake manifest for real renditions."""
        renditions = self.handler.extract_rendition_list(REALISTIC_RENDITION_DOCS_CS)
        manifest = self.handler.build_rendition_manifest(renditions)
        self.assertEqual(len(manifest), 3)
        for entry in manifest:
            self.assertIn("onelake_path", entry)
            self.assertTrue(entry["onelake_path"].startswith("renditions/"))


class TestRealisticVersioning(unittest.TestCase):
    """Tests version handling with real enterprise document version chains."""

    def test_finance_report_version_chain(self):
        """Q4 Financial Report: 3 versions (draft → review → final)."""
        handler = VersionHandler()
        chains = handler.extract_version_chains(REALISTIC_VERSION_DOCS[:1])
        self.assertEqual(len(chains), 1)

        chain = chains[0]
        self.assertEqual(chain.version_count, 3)
        self.assertEqual(chain.current_version["version_number"], 3)

        # File size grows through versions
        sizes = [v["file_size"] for v in chain.versions]
        self.assertEqual(sizes, sorted(sizes))

    def test_handbook_version_chain(self):
        """Employee Handbook: 3 editions by same author."""
        handler = VersionHandler()
        chains = handler.extract_version_chains(REALISTIC_VERSION_DOCS[1:2])
        chain = chains[0]
        self.assertEqual(chain.version_count, 3)

        # All versions by same user
        authors = {v["created_by"] for v in chain.versions}
        self.assertEqual(len(authors), 1)
        self.assertEqual(authors.pop(), "legal_admin")

    def test_latest_only_strategy(self):
        """Latest-only migration: download only current version."""
        handler = VersionHandler(strategy="latest_only")
        chains = handler.extract_version_chains(REALISTIC_VERSION_DOCS)
        plan = handler.plan_version_migration(chains)

        # Should have 2 downloads (one per doc)
        downloads = [p for p in plan if p["action"] == "download"]
        self.assertEqual(len(downloads), 2)

        # Each download is the latest version
        for d in downloads:
            self.assertEqual(d["version_number"], 3)

    def test_all_versions_strategy(self):
        """All-versions migration: download every version."""
        handler = VersionHandler(strategy="all_versions")
        chains = handler.extract_version_chains(REALISTIC_VERSION_DOCS)
        plan = handler.plan_version_migration(chains)

        # 3 versions × 2 docs = 6 downloads
        self.assertEqual(len(plan), 6)

    def test_metadata_only_strategy(self):
        """Metadata-only: download latest, metadata for rest."""
        handler = VersionHandler(strategy="metadata_only")
        chains = handler.extract_version_chains(REALISTIC_VERSION_DOCS)
        plan = handler.plan_version_migration(chains)

        downloads = [p for p in plan if p["action"] == "download"]
        metadata = [p for p in plan if p["action"] == "metadata_only"]

        # 2 downloads (latest of each doc)
        self.assertEqual(len(downloads), 2)
        # 4 metadata-only (older versions)
        self.assertEqual(len(metadata), 4)

    def test_version_table_real_data(self):
        """Build version table with real metadata."""
        handler = VersionHandler()
        chains = handler.extract_version_chains(REALISTIC_VERSION_DOCS)
        rows = handler.build_version_table(chains)

        self.assertEqual(len(rows), 6)  # 3 + 3 versions

        # Only 2 should be marked as current
        current_rows = [r for r in rows if r["is_current"]]
        self.assertEqual(len(current_rows), 2)

        # Check MIME types preserved
        pdf_rows = [r for r in rows if r.get("mime_type") == "application/pdf"]
        self.assertTrue(len(pdf_rows) >= 3)


if __name__ == "__main__":
    unittest.main()
