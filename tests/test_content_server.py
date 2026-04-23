"""Tests for opentext_extract.content_server."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from opentext_extract.content_server import ContentServerClient


class TestContentServerClient(unittest.TestCase):

    def setUp(self):
        self.client = ContentServerClient(
            base_url="https://cs.example.com/otcs/cs.exe",
            username="admin",
            password="pass",
            max_retries=1,
            retry_delay=0.01,
        )

    @patch.object(ContentServerClient, "post")
    def test_authenticate_success(self, mock_post):
        mock_post.return_value = {"ticket": "abc123"}
        token = self.client.authenticate()
        self.assertEqual(token, "abc123")
        self.assertTrue(self.client.is_authenticated)

    @patch.object(ContentServerClient, "post")
    def test_authenticate_failure(self, mock_post):
        mock_post.return_value = {}
        from opentext_extract.api_client import APIError
        with self.assertRaises(APIError):
            self.client.authenticate()

    @patch.object(ContentServerClient, "get")
    def test_get_node(self, mock_get):
        mock_get.return_value = {"results": {"id": 100, "name": "Test"}}
        result = self.client.get_node(100)
        self.assertEqual(result["id"], 100)

    @patch.object(ContentServerClient, "get_paginated")
    def test_get_children(self, mock_paginated):
        mock_paginated.return_value = [{"id": 1}, {"id": 2}]
        result = self.client.get_children(100)
        self.assertEqual(len(result), 2)

    @patch.object(ContentServerClient, "get")
    def test_get_categories(self, mock_get):
        mock_get.return_value = {"results": [{"data": {"id": 1, "name": "Cat1", "attributes": {}}}]}
        result = self.client.get_categories(100)
        self.assertEqual(len(result), 1)

    @patch.object(ContentServerClient, "get")
    def test_get_categories_404(self, mock_get):
        from opentext_extract.api_client import APIError
        mock_get.side_effect = APIError("Not found", status_code=404)
        result = self.client.get_categories(999)
        self.assertEqual(result, [])

    @patch.object(ContentServerClient, "get")
    def test_get_permissions(self, mock_get):
        mock_get.return_value = {
            "results": {
                "data": {
                    "owner": {"permissions": ["see", "see_contents"]},
                    "group": {},
                    "public": {},
                    "custom": [],
                }
            }
        }
        result = self.client.get_permissions(100)
        self.assertIn("data", result)

    @patch.object(ContentServerClient, "get")
    def test_extract_permissions(self, mock_get):
        mock_get.return_value = {
            "results": {
                "data": {
                    "owner": {"permissions": ["see"], "right_id": 1},
                    "custom": [{"right_id": 2, "name": "group1", "permissions": ["read"]}],
                }
            }
        }
        result = self.client.extract_permissions(100)
        self.assertEqual(result["node_id"], 100)
        self.assertTrue(len(result["entries"]) >= 1)

    @patch.object(ContentServerClient, "get")
    def test_get_versions(self, mock_get):
        mock_get.return_value = {
            "data": [
                {"version_number": 1, "version_id": 10, "create_date": "2024-01-01"},
                {"version_number": 2, "version_id": 11, "create_date": "2024-02-01"},
            ]
        }
        result = self.client.get_versions(100)
        self.assertEqual(len(result), 2)

    @patch.object(ContentServerClient, "get")
    def test_get_versions_404(self, mock_get):
        from opentext_extract.api_client import APIError
        mock_get.side_effect = APIError("Not found", status_code=404)
        result = self.client.get_versions(999)
        self.assertEqual(result, [])

    @patch.object(ContentServerClient, "get_children")
    def test_walk_tree_flat(self, mock_children):
        mock_children.return_value = [
            {"data": {"properties": {"id": 10, "name": "doc1.pdf", "type": 144, "size": 1000,
                                      "create_date": "", "modify_date": "", "create_user_id": 0,
                                      "modify_user_id": 0, "mime_type": "application/pdf", "description": ""}}},
        ]
        nodes = self.client.walk_tree(100)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "doc1.pdf")

    @patch.object(ContentServerClient, "get_children")
    def test_walk_tree_max_depth(self, mock_children):
        mock_children.return_value = [
            {"data": {"properties": {"id": 10, "name": "folder", "type": 0, "size": 0,
                                      "create_date": "", "modify_date": "", "create_user_id": 0,
                                      "modify_user_id": 0, "mime_type": "", "description": ""}}},
        ]
        nodes = self.client.walk_tree(100, max_depth=0)
        # At depth 0, the children are at depth 0 themselves, and subfolder recursion
        # would be at depth 1 which exceeds max_depth=0
        self.assertEqual(len(nodes), 1)


class TestExtractAll(unittest.TestCase):

    @patch.object(ContentServerClient, "get_members")
    @patch.object(ContentServerClient, "get_versions")
    @patch.object(ContentServerClient, "extract_permissions")
    @patch.object(ContentServerClient, "extract_metadata")
    @patch.object(ContentServerClient, "walk_tree")
    def test_extract_all_creates_files(self, mock_walk, mock_meta, mock_perms, mock_vers, mock_members):
        import tempfile
        mock_walk.return_value = [
            {"id": 10, "name": "doc.pdf", "type": 144, "size": 100,
             "create_date": "", "modify_date": "", "mime_type": "application/pdf"},
        ]
        mock_meta.return_value = {"node_id": 10, "categories": []}
        mock_perms.return_value = {"node_id": 10, "entries": []}
        mock_vers.return_value = []
        mock_members.return_value = []

        client = ContentServerClient(base_url="https://cs.example.com", max_retries=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            files = client.extract_all(root_id=100, output_dir=tmpdir)
            self.assertIn("nodes.json", files)
            self.assertIn("documents.json", files)
            self.assertTrue(Path(files["nodes.json"]).exists())


if __name__ == "__main__":
    unittest.main()
