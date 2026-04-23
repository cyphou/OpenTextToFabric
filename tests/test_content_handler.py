"""Tests for content_handler modules: downloader, renditions, versioning."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from content_handler.downloader import DocumentDownloader, DownloadError
from content_handler.renditions import RenditionHandler, Rendition
from content_handler.versioning import VersionHandler, VersionChain


class TestDocumentDownloader(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.downloader = DocumentDownloader(self.tmpdir)

    def test_safe_filename_strips_path(self):
        result = DocumentDownloader._safe_filename("../../etc/passwd")
        self.assertNotIn("/", result)
        self.assertNotIn("..", result)

    def test_safe_filename_null_bytes(self):
        result = DocumentDownloader._safe_filename("file\x00.txt")
        self.assertNotIn("\x00", result)

    def test_safe_filename_long(self):
        result = DocumentDownloader._safe_filename("a" * 300 + ".pdf")
        self.assertTrue(len(result) <= 255)

    def test_safe_filename_empty(self):
        self.assertEqual(DocumentDownloader._safe_filename(""), "unnamed")

    def test_verify_checksum_correct(self):
        tmp = Path(self.tmpdir) / "test.bin"
        data = b"hello world"
        tmp.write_bytes(data)
        expected = hashlib.sha256(data).hexdigest()
        self.assertTrue(DocumentDownloader._verify_checksum(tmp, expected))

    def test_verify_checksum_wrong(self):
        tmp = Path(self.tmpdir) / "test.bin"
        tmp.write_bytes(b"hello")
        self.assertFalse(DocumentDownloader._verify_checksum(tmp, "wrong_hash"))

    @patch("urllib.request.urlopen")
    def test_download_success(self, mock_urlopen):
        content = b"test file content"
        mock_resp = MagicMock()
        mock_resp.read = MagicMock(side_effect=[content, b""])
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        path = self.downloader.download("https://example.com/doc", "test.pdf")
        self.assertTrue(path.exists())
        self.assertEqual(path.read_bytes(), content)

    @patch("urllib.request.urlopen")
    def test_download_size_mismatch(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read = MagicMock(side_effect=[b"short", b""])
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        with self.assertRaises(DownloadError):
            self.downloader.download("https://example.com/doc", "test.pdf", expected_size=999)

    def test_save_manifest(self):
        self.downloader._manifest = [{"filename": "test.pdf", "size": 100}]
        path = self.downloader.save_manifest()
        self.assertTrue(path.exists())

    def test_cleanup(self):
        tmp = Path(self.tmpdir) / "partial.tmp"
        tmp.write_bytes(b"partial")
        self.downloader.cleanup()
        self.assertFalse(tmp.exists())


class TestRenditionHandler(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.handler = RenditionHandler(self.tmpdir)

    def test_classify_pdf(self):
        self.assertEqual(self.handler.classify_rendition("application/pdf"), "pdf")

    def test_classify_thumbnail(self):
        self.assertEqual(self.handler.classify_rendition("image/png"), "thumbnail")

    def test_classify_unknown(self):
        self.assertEqual(self.handler.classify_rendition("application/octet-stream"), "other")

    def test_extract_rendition_list_cs(self):
        docs = [{
            "node_id": 100,
            "versions": [
                {"mime_type": "application/pdf", "file_size": 1000},
            ],
        }]
        renditions = self.handler.extract_rendition_list(docs)
        self.assertEqual(len(renditions), 1)
        self.assertEqual(renditions[0].rendition_type, "primary")

    def test_extract_rendition_list_dctm(self):
        docs = [{
            "object_id": "obj1",
            "renditions": [
                {"full_format": "application/pdf", "r_content_size": 500},
            ],
        }]
        renditions = self.handler.extract_rendition_list(docs)
        self.assertEqual(len(renditions), 1)
        self.assertEqual(renditions[0].rendition_type, "pdf")

    def test_build_rendition_manifest(self):
        renditions = [
            Rendition("doc1", "application/pdf", "pdf", 1000),
        ]
        manifest = self.handler.build_rendition_manifest(renditions)
        self.assertEqual(len(manifest), 1)
        self.assertIn("onelake_path", manifest[0])


class TestVersionChain(unittest.TestCase):

    def test_sorted_versions(self):
        versions = [{"version_number": 2}, {"version_number": 1}]
        chain = VersionChain("doc1", versions)
        self.assertEqual(chain.versions[0]["version_number"], 1)

    def test_current_version(self):
        chain = VersionChain("doc1", [{"version_number": 1}, {"version_number": 3}])
        self.assertEqual(chain.current_version["version_number"], 3)

    def test_empty_chain(self):
        chain = VersionChain("doc1", [])
        self.assertEqual(chain.current_version, {})
        self.assertEqual(chain.version_count, 0)


class TestVersionHandler(unittest.TestCase):

    def setUp(self):
        self.docs = [{
            "node_id": 100,
            "versions": [
                {"version_number": 1, "version_id": 10, "create_date": "2024-01-01", "file_size": 100, "created_by": "user1", "mime_type": "application/pdf", "description": ""},
                {"version_number": 2, "version_id": 11, "create_date": "2024-02-01", "file_size": 200, "created_by": "user2", "mime_type": "application/pdf", "description": ""},
            ],
        }]

    def test_extract_version_chains(self):
        handler = VersionHandler()
        chains = handler.extract_version_chains(self.docs)
        self.assertEqual(len(chains), 1)
        self.assertEqual(chains[0].version_count, 2)

    def test_plan_latest_only(self):
        handler = VersionHandler(strategy="latest_only")
        chains = handler.extract_version_chains(self.docs)
        plan = handler.plan_version_migration(chains)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["version_number"], 2)

    def test_plan_all_versions(self):
        handler = VersionHandler(strategy="all_versions")
        chains = handler.extract_version_chains(self.docs)
        plan = handler.plan_version_migration(chains)
        self.assertEqual(len(plan), 2)

    def test_plan_metadata_only(self):
        handler = VersionHandler(strategy="metadata_only")
        chains = handler.extract_version_chains(self.docs)
        plan = handler.plan_version_migration(chains)
        download_count = sum(1 for p in plan if p["action"] == "download")
        metadata_count = sum(1 for p in plan if p["action"] == "metadata_only")
        self.assertEqual(download_count, 1)
        self.assertEqual(metadata_count, 1)

    def test_build_version_table(self):
        handler = VersionHandler()
        chains = handler.extract_version_chains(self.docs)
        rows = handler.build_version_table(chains)
        self.assertEqual(len(rows), 2)
        current_rows = [r for r in rows if r["is_current"]]
        self.assertEqual(len(current_rows), 1)


if __name__ == "__main__":
    unittest.main()
