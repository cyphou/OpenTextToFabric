"""Tests for opentext_extract.documentum_client."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from opentext_extract.documentum_client import DocumentumClient


class TestDocumentumClient(unittest.TestCase):

    def setUp(self):
        self.client = DocumentumClient(
            base_url="https://dctm.example.com/dctm-rest",
            username="admin",
            password="pass",
            repository="myrepo",
            max_retries=1,
            retry_delay=0.01,
        )

    @patch.object(DocumentumClient, "get")
    def test_authenticate_success(self, mock_get):
        mock_get.return_value = {"properties": {"user_name": "admin"}}
        self.client.authenticate()
        self.assertTrue(self.client.is_authenticated)

    @patch.object(DocumentumClient, "get")
    def test_authenticate_failure(self, mock_get):
        from opentext_extract.api_client import APIError
        mock_get.side_effect = APIError("Auth failed", status_code=401)
        with self.assertRaises(APIError):
            self.client.authenticate()

    @patch.object(DocumentumClient, "get")
    def test_query_dql(self, mock_get):
        mock_get.return_value = {
            "entries": [
                {"content": {"properties": {"r_object_id": "obj1"}}},
                {"content": {"properties": {"r_object_id": "obj2"}}},
            ]
        }
        results = self.client.query_dql("SELECT r_object_id FROM dm_document")
        self.assertEqual(len(results), 2)

    @patch.object(DocumentumClient, "get")
    def test_get_cabinets(self, mock_get):
        mock_get.return_value = {
            "entries": [
                {"content": {"properties": {"r_object_id": "cab1", "object_name": "Cabinet1"}}},
            ]
        }
        cabinets = self.client.get_cabinets()
        self.assertEqual(len(cabinets), 1)
        self.assertEqual(cabinets[0]["name"], "Cabinet1")

    @patch.object(DocumentumClient, "query_dql")
    def test_get_object_acl(self, mock_dql):
        mock_dql.return_value = [
            {"r_accessor_name": "admin", "r_accessor_permit": 7, "r_is_group": False},
            {"r_accessor_name": "group1", "r_accessor_permit": 3, "r_is_group": True},
        ]
        result = self.client.get_object_acl("obj1")
        self.assertEqual(result["object_id"], "obj1")
        self.assertEqual(len(result["acl_entries"]), 2)
        self.assertTrue(result["acl_entries"][1]["r_is_group"])

    @patch.object(DocumentumClient, "query_dql")
    def test_get_lifecycle_state(self, mock_dql):
        mock_dql.return_value = [
            {"r_policy_id": "pol1", "r_current_state": 2},
        ]
        state = self.client.get_lifecycle_state("obj1")
        self.assertEqual(state["policy_id"], "pol1")
        self.assertEqual(state["current_state"], 2)

    @patch.object(DocumentumClient, "query_dql")
    def test_get_lifecycle_state_not_found(self, mock_dql):
        mock_dql.return_value = []
        state = self.client.get_lifecycle_state("obj_missing")
        self.assertEqual(state["policy_id"], "")
        self.assertEqual(state["current_state"], -1)

    @patch.object(DocumentumClient, "query_dql")
    def test_get_renditions(self, mock_dql):
        mock_dql.return_value = [
            {"full_format": "application/pdf", "r_content_size": 500},
        ]
        renditions = self.client.get_renditions("obj1")
        self.assertEqual(len(renditions), 1)
        self.assertEqual(renditions[0]["full_format"], "application/pdf")


class TestExtractAll(unittest.TestCase):

    @patch.object(DocumentumClient, "get_lifecycle_state")
    @patch.object(DocumentumClient, "get_object_acl")
    @patch.object(DocumentumClient, "walk_tree")
    def test_extract_all_creates_files(self, mock_walk, mock_acl, mock_lifecycle):
        mock_walk.return_value = [
            {"id": "obj1", "name": "doc.pdf", "type": "dm_document",
             "size": 100, "create_date": "", "modify_date": "",
             "owner": "admin", "mime_type": "application/pdf",
             "depth": 0, "parent_id": "cab1", "path": "/doc.pdf"},
        ]
        mock_acl.return_value = {"object_id": "obj1", "acl_entries": []}
        mock_lifecycle.return_value = {"object_id": "obj1", "policy_id": "", "current_state": -1}

        client = DocumentumClient(base_url="https://dctm.example.com", repository="repo", max_retries=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            files = client.extract_all(root_folder_id="cab1", output_dir=tmpdir)
            self.assertIn("nodes.json", files)
            self.assertTrue(Path(files["nodes.json"]).exists())


if __name__ == "__main__":
    unittest.main()
