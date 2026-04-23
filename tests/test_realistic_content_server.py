"""Realistic tests for ContentServerClient using real-world API response structures.

Based on OpenText Content Server REST API v2 patterns observed from:
- StackOverflow community examples (CS REST API)
- Official Swagger docs (type codes, endpoint structure)
- Real enterprise deployment patterns (hierarchical folders, categories)
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from opentext_extract.content_server import ContentServerClient
from opentext_extract.api_client import APIError
from tests.fixtures import (
    CS_AUTH_RESPONSE,
    CS_NODE_FOLDER_RESPONSE,
    CS_NODE_DOCUMENT_RESPONSE,
    CS_CHILDREN_RESPONSE,
    CS_CATEGORIES_RESPONSE,
    CS_PERMISSIONS_RESPONSE,
    CS_VERSIONS_RESPONSE,
    CS_WORKFLOW_RESPONSE,
    CS_MEMBERS_RESPONSE,
)


class TestRealisticAuthentication(unittest.TestCase):
    """Tests authentication using real-world OTCSTicket patterns."""

    def setUp(self):
        self.client = ContentServerClient(
            base_url="https://otcs.acme-corp.com/otcs/cs.exe",
            username="jsmith",
            password="P@ssw0rd!2024",
            max_retries=2,
            retry_delay=0.01,
        )

    @patch.object(ContentServerClient, "post")
    def test_authenticate_returns_real_ticket(self, mock_post):
        """Real CS tickets are base64-like strings."""
        mock_post.return_value = CS_AUTH_RESPONSE
        ticket = self.client.authenticate()
        self.assertEqual(ticket, CS_AUTH_RESPONSE["ticket"])
        self.assertTrue(self.client.is_authenticated)
        # Verify POST was called to the auth endpoint
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn("api/v1/auth", str(call_args))

    @patch.object(ContentServerClient, "post")
    def test_authenticate_bad_password(self, mock_post):
        """Real CS returns empty ticket on bad credentials."""
        mock_post.return_value = {}
        with self.assertRaises(APIError) as ctx:
            self.client.authenticate()
        self.assertIn("failed", str(ctx.exception).lower())


class TestRealisticNodeOperations(unittest.TestCase):
    """Tests node CRUD with real response shapes."""

    def setUp(self):
        self.client = ContentServerClient(
            base_url="https://otcs.acme-corp.com/otcs/cs.exe",
            max_retries=1,
            retry_delay=0.01,
        )
        self.client._token = "real-ticket-token"

    @patch.object(ContentServerClient, "get")
    def test_get_enterprise_workspace_folder(self, mock_get):
        """Type 0 = Folder, the root Enterprise Workspace."""
        mock_get.return_value = CS_NODE_FOLDER_RESPONSE
        result = self.client.get_node(2000)
        # After get_node calls resp.get("results", resp), we get the inner dict
        props = result.get("data", result).get("properties", result)
        self.assertEqual(props["id"], 2000)
        self.assertEqual(props["type"], 0)
        self.assertEqual(props["type_name"], "Folder")
        self.assertTrue(props["container"])
        self.assertEqual(props["container_size"], 42)

    @patch.object(ContentServerClient, "get")
    def test_get_document_node(self, mock_get):
        """Type 144 = Document, a real PDF node."""
        mock_get.return_value = CS_NODE_DOCUMENT_RESPONSE
        result = self.client.get_node(54321)
        props = result.get("data", result).get("properties", result)
        self.assertEqual(props["type"], 144)
        self.assertEqual(props["type_name"], "Document")
        self.assertEqual(props["mime_type"], "application/pdf")
        self.assertEqual(props["size"], 2457600)
        self.assertFalse(props["container"])

    @patch.object(ContentServerClient, "get_paginated")
    def test_get_children_mixed_types(self, mock_paginated):
        """Enterprise Workspace has folders and documents mixed."""
        # Flatten the children response
        children = [item for item in CS_CHILDREN_RESPONSE["results"]]
        mock_paginated.return_value = children

        result = self.client.get_children(2000)
        self.assertEqual(len(result), 5)

        # Check we have both folders and documents
        types = {item["data"]["properties"]["type"] for item in result}
        self.assertIn(0, types)    # folders
        self.assertIn(144, types)  # documents

        # Check specific items
        names = [item["data"]["properties"]["name"] for item in result]
        self.assertIn("Finance", names)
        self.assertIn("Q4_2024_Financial_Report.pdf", names)


class TestRealisticCategories(unittest.TestCase):
    """Tests with real-world enterprise categories (classifications, project metadata)."""

    def setUp(self):
        self.client = ContentServerClient(
            base_url="https://otcs.acme-corp.com/otcs/cs.exe",
            max_retries=1,
        )

    @patch.object(ContentServerClient, "get")
    def test_get_categories_real(self, mock_get):
        """Real CS categories include classification level, retention, department."""
        mock_get.return_value = CS_CATEGORIES_RESPONSE
        result = self.client.get_categories(54321)
        self.assertEqual(len(result), 2)

        # Document Classification category
        doc_class = result[0]["data"]
        self.assertEqual(doc_class["name"], "Document Classification")
        self.assertEqual(doc_class["attributes"]["classification_level"], "Confidential")
        self.assertEqual(doc_class["attributes"]["retention_years"], "7")

        # Project Metadata category
        proj_meta = result[1]["data"]
        self.assertEqual(proj_meta["name"], "Project Metadata")
        self.assertEqual(proj_meta["attributes"]["project_code"], "PRJ-2024-Q4")

    @patch.object(ContentServerClient, "get")
    def test_get_categories_404_returns_empty(self, mock_get):
        """Nodes without categories return 404 from CS API."""
        mock_get.side_effect = APIError("Not found", status_code=404)
        result = self.client.get_categories(99999)
        self.assertEqual(result, [])


class TestRealisticPermissions(unittest.TestCase):
    """Tests with real-world ACL structures: owner/group/public/custom."""

    def setUp(self):
        self.client = ContentServerClient(
            base_url="https://otcs.acme-corp.com/otcs/cs.exe",
            max_retries=1,
        )

    @patch.object(ContentServerClient, "get")
    def test_get_permissions_full_acl(self, mock_get):
        """Real CS permissions have owner/group/public/custom sections."""
        mock_get.return_value = CS_PERMISSIONS_RESPONSE
        result = self.client.get_permissions(54321)

        data = result["data"]
        # Owner has full control (10 permissions)
        self.assertEqual(len(data["owner"]["permissions"]), 10)
        self.assertIn("edit_permissions", data["owner"]["permissions"])

        # Custom entries include groups and individual users
        self.assertEqual(len(data["custom"]), 3)
        finance_mgrs = data["custom"][0]
        self.assertEqual(finance_mgrs["name"], "Finance_Managers")
        self.assertEqual(finance_mgrs["type"], "group")
        self.assertIn("modify", finance_mgrs["permissions"])

        # Auditors have read-only
        auditors = data["custom"][1]
        self.assertEqual(auditors["name"], "Auditors")
        self.assertEqual(set(auditors["permissions"]), {"see", "see_contents"})

    @patch.object(ContentServerClient, "get")
    def test_extract_permissions_maps_correctly(self, mock_get):
        """extract_permissions normalizes into node_id + entries format."""
        mock_get.return_value = CS_PERMISSIONS_RESPONSE
        result = self.client.extract_permissions(54321)
        self.assertEqual(result["node_id"], 54321)
        self.assertTrue(len(result["entries"]) >= 1)


class TestRealisticVersions(unittest.TestCase):
    """Tests with real version chains (draft → review → final)."""

    def setUp(self):
        self.client = ContentServerClient(
            base_url="https://otcs.acme-corp.com/otcs/cs.exe",
            max_retries=1,
        )

    @patch.object(ContentServerClient, "get")
    def test_get_versions_real_chain(self, mock_get):
        """Real docs have version chains: 1 → 2 → 3."""
        mock_get.return_value = CS_VERSIONS_RESPONSE
        result = self.client.get_versions(54321)
        self.assertEqual(len(result), 3)

        # get_versions transforms to simplified dicts with version_number (int)
        self.assertEqual(result[0]["version_number"], 1)
        self.assertEqual(result[1]["version_number"], 2)
        self.assertEqual(result[2]["version_number"], 3)

        # Final version is largest
        self.assertGreater(result[2]["file_size"], result[0]["file_size"])

    @patch.object(ContentServerClient, "get")
    def test_get_versions_404_returns_empty(self, mock_get):
        """Deleted nodes return 404 for versions."""
        mock_get.side_effect = APIError("Not found", status_code=404)
        result = self.client.get_versions(99999)
        self.assertEqual(result, [])


class TestRealisticWalkTree(unittest.TestCase):
    """Tests walking a real enterprise folder hierarchy."""

    def setUp(self):
        self.client = ContentServerClient(
            base_url="https://otcs.acme-corp.com/otcs/cs.exe",
            max_retries=1,
        )

    @patch.object(ContentServerClient, "get_children")
    def test_walk_tree_enterprise_structure(self, mock_children):
        """Simulates walking: Enterprise → Finance → docs, HR → docs."""
        # First call (root): returns Finance folder + HR folder + a doc
        root_children = [
            {"data": {"properties": {"id": 3001, "name": "Finance", "type": 0,
                                      "size": 0, "create_date": "2019-05-10T10:00:00Z",
                                      "modify_date": "2024-12-01", "create_user_id": 1000,
                                      "modify_user_id": 1001, "mime_type": "", "description": ""}}},
            {"data": {"properties": {"id": 3002, "name": "HR Policies", "type": 0,
                                      "size": 0, "create_date": "2020-01-15", "modify_date": "2024-06-30",
                                      "create_user_id": 1000, "modify_user_id": 1003,
                                      "mime_type": "", "description": ""}}},
            {"data": {"properties": {"id": 54321, "name": "Q4_2024_Financial_Report.pdf", "type": 144,
                                      "size": 2457600, "create_date": "2024-10-01", "modify_date": "2024-12-15",
                                      "create_user_id": 1001, "modify_user_id": 1002,
                                      "mime_type": "application/pdf", "description": "Quarterly report"}}},
        ]
        # Finance folder children
        finance_children = [
            {"data": {"properties": {"id": 54324, "name": "Budget_Template_2025.xlsx", "type": 144,
                                      "size": 350000, "create_date": "2024-01-01", "modify_date": "2024-11-01",
                                      "create_user_id": 1001, "modify_user_id": 1001,
                                      "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                      "description": "Budget template"}}},
        ]
        # HR folder children (empty)
        hr_children = []

        mock_children.side_effect = [root_children, finance_children, hr_children]

        nodes = self.client.walk_tree(2000)
        # Should have: Finance folder, HR folder, PDF doc, Budget doc
        self.assertEqual(len(nodes), 4)
        names = {n["name"] for n in nodes}
        self.assertIn("Q4_2024_Financial_Report.pdf", names)
        self.assertIn("Budget_Template_2025.xlsx", names)


class TestRealisticExtractAll(unittest.TestCase):
    """Full extraction with realistic data shapes."""

    @patch.object(ContentServerClient, "get_members")
    @patch.object(ContentServerClient, "get_versions")
    @patch.object(ContentServerClient, "extract_permissions")
    @patch.object(ContentServerClient, "extract_metadata")
    @patch.object(ContentServerClient, "walk_tree")
    def test_extract_all_enterprise_data(self, mock_walk, mock_meta, mock_perms, mock_vers, mock_members):
        """Full extraction from a realistic Enterprise Workspace."""
        mock_walk.return_value = [
            {"id": 3001, "name": "Finance", "type": 0, "size": 0,
             "create_date": "2019-05-10", "modify_date": "2024-12-01",
             "mime_type": ""},
            {"id": 54321, "name": "Q4_2024_Financial_Report.pdf", "type": 144,
             "size": 2457600, "create_date": "2024-10-01", "modify_date": "2024-12-15",
             "mime_type": "application/pdf"},
            {"id": 54322, "name": "Employee_Handbook_v3.docx", "type": 144,
             "size": 1843200, "create_date": "2023-06-15", "modify_date": "2024-09-01",
             "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ]

        mock_meta.return_value = {"node_id": 54321, "categories": [
            {"category_name": "Document Classification", "attributes": {
                "classification_level": "Confidential", "retention_years": "7"}},
        ]}
        mock_perms.return_value = {"node_id": 54321, "entries": [
            {"type": "owner", "name": "jsmith", "permissions": ["see", "modify", "delete"]},
            {"type": "custom", "name": "Finance_Managers", "permissions": ["see", "modify"]},
        ]}
        mock_vers.return_value = CS_VERSIONS_RESPONSE["data"]
        mock_members.return_value = CS_MEMBERS_RESPONSE

        client = ContentServerClient(
            base_url="https://otcs.acme-corp.com/otcs/cs.exe",
            max_retries=1,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            files = client.extract_all(root_id=2000, output_dir=tmpdir)

            # Verify all output files created
            self.assertIn("nodes.json", files)
            self.assertIn("documents.json", files)
            self.assertTrue(Path(files["nodes.json"]).exists())

            # Verify nodes.json content
            with open(files["nodes.json"], encoding="utf-8") as f:
                nodes = json.load(f)
            self.assertEqual(len(nodes), 3)

            # Verify documents.json has only document entries (type 144 nodes)
            with open(files["documents.json"], encoding="utf-8") as f:
                docs = json.load(f)
            self.assertEqual(len(docs), 2)
            # extract_all filters by type=144 for docs, entries have node_id + name
            for doc in docs:
                self.assertIn("node_id", doc)
                self.assertIn("name", doc)


if __name__ == "__main__":
    unittest.main()
