"""Realistic tests for DocumentumClient using real-world API response structures.

Based on OpenText Documentum REST Services API patterns:
- CMIS/REST feed format with entries/content/properties
- DQL query-based operations
- ACL permit levels (1=None, 3=Read, 4=Relate, 5=Version, 6=Write, 7=Delete)
- Lifecycle state management
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from opentext_extract.documentum_client import DocumentumClient
from opentext_extract.api_client import APIError
from tests.fixtures import (
    DCTM_AUTH_RESPONSE,
    DCTM_CABINETS_RESPONSE,
    DCTM_DQL_FOLDER_CONTENTS,
    DCTM_ACL_DQL_RESPONSE,
    DCTM_LIFECYCLE_DQL_RESPONSE,
    DCTM_RENDITIONS_DQL_RESPONSE,
)


class TestRealisticDocumentumAuth(unittest.TestCase):
    """Documentum REST auth via /repositories/{repo}/currentuser."""

    def setUp(self):
        self.client = DocumentumClient(
            base_url="https://dctm.acme-corp.com/dctm-rest",
            username="dmadmin",
            password="dm@dmin2024!",
            repository="acme_repo",
            max_retries=1,
            retry_delay=0.01,
        )

    @patch.object(DocumentumClient, "get")
    def test_authenticate_returns_user_info(self, mock_get):
        """Documentum auth returns user properties on success."""
        mock_get.return_value = DCTM_AUTH_RESPONSE
        self.client.authenticate()
        self.assertTrue(self.client.is_authenticated)

    @patch.object(DocumentumClient, "get")
    def test_authenticate_401_raises(self, mock_get):
        mock_get.side_effect = APIError("Unauthorized", status_code=401)
        with self.assertRaises(APIError):
            self.client.authenticate()


class TestRealisticCabinets(unittest.TestCase):
    """Tests with real Documentum cabinet structure (dm_cabinet)."""

    def setUp(self):
        self.client = DocumentumClient(
            base_url="https://dctm.acme-corp.com/dctm-rest",
            repository="acme_repo",
            max_retries=1,
        )

    @patch.object(DocumentumClient, "get")
    def test_get_cabinets_real_format(self, mock_get):
        """Real Documentum cabinets have entries→content→properties structure."""
        mock_get.return_value = DCTM_CABINETS_RESPONSE
        cabinets = self.client.get_cabinets()

        self.assertEqual(len(cabinets), 2)

        # get_cabinets transforms to {"id":..., "name":..., "type":"dm_cabinet"}
        cab1 = cabinets[0]
        self.assertEqual(cab1["name"], "Enterprise Documents")
        self.assertEqual(cab1["type"], "dm_cabinet")
        self.assertIn("id", cab1)

        cab2 = cabinets[1]
        self.assertEqual(cab2["name"], "HR & Legal")


class TestRealisticDQLQueries(unittest.TestCase):
    """Tests with real DQL query patterns."""

    def setUp(self):
        self.client = DocumentumClient(
            base_url="https://dctm.acme-corp.com/dctm-rest",
            repository="acme_repo",
            max_retries=1,
        )

    @patch.object(DocumentumClient, "get")
    def test_query_dql_folder_contents(self, mock_get):
        """DQL: SELECT * FROM dm_document WHERE FOLDER(...)."""
        mock_get.return_value = DCTM_DQL_FOLDER_CONTENTS
        results = self.client.query_dql(
            "SELECT r_object_id, object_name, r_object_type "
            "FROM dm_sysobject WHERE FOLDER('/Enterprise Documents')"
        )

        self.assertEqual(len(results), 3)

        # Check we have documents and folders
        types = {r["r_object_type"] for r in results}
        self.assertIn("dm_document", types)
        self.assertIn("dm_folder", types)

        # Check version labels
        annual_report = next(r for r in results if r["object_name"] == "2024_Annual_Report.pdf")
        self.assertIn("CURRENT", annual_report["r_version_label"])

    @patch.object(DocumentumClient, "get")
    def test_query_dql_empty_result(self, mock_get):
        mock_get.return_value = {"entries": []}
        results = self.client.query_dql("SELECT * FROM dm_document WHERE 1=0")
        self.assertEqual(results, [])


class TestRealisticACL(unittest.TestCase):
    """Tests with real Documentum ACL permit levels.

    Documentum permit levels:
    1 = None, 2 = Browse, 3 = Read, 4 = Relate,
    5 = Version, 6 = Write, 7 = Delete (full control)
    """

    def setUp(self):
        self.client = DocumentumClient(
            base_url="https://dctm.acme-corp.com/dctm-rest",
            repository="acme_repo",
            max_retries=1,
        )

    @patch.object(DocumentumClient, "query_dql")
    def test_get_object_acl_real_structure(self, mock_dql):
        """Real ACL has dm_world (3=Read), dm_owner (7=Delete), custom groups."""
        mock_dql.return_value = [
            entry["content"]["properties"]
            for entry in DCTM_ACL_DQL_RESPONSE["entries"]
        ]

        result = self.client.get_object_acl("0900000180001001")

        self.assertEqual(result["object_id"], "0900000180001001")
        entries = result["acl_entries"]
        self.assertEqual(len(entries), 4)

        # dm_world has read (3)
        dm_world = next(e for e in entries if e["r_accessor_name"] == "dm_world")
        self.assertEqual(dm_world["r_accessor_permit"], 3)
        self.assertTrue(dm_world["r_is_group"])

        # dm_owner has delete/full control (7)
        dm_owner = next(e for e in entries if e["r_accessor_name"] == "dm_owner")
        self.assertEqual(dm_owner["r_accessor_permit"], 7)

        # finance_group has write (6)
        finance = next(e for e in entries if e["r_accessor_name"] == "finance_group")
        self.assertEqual(finance["r_accessor_permit"], 6)
        self.assertTrue(finance["r_is_group"])


class TestRealisticLifecycle(unittest.TestCase):
    """Tests lifecycle state management."""

    def setUp(self):
        self.client = DocumentumClient(
            base_url="https://dctm.acme-corp.com/dctm-rest",
            repository="acme_repo",
            max_retries=1,
        )

    @patch.object(DocumentumClient, "query_dql")
    def test_get_lifecycle_state_active(self, mock_dql):
        """Document with active lifecycle policy, state 2 = Published."""
        mock_dql.return_value = [
            entry["content"]["properties"]
            for entry in DCTM_LIFECYCLE_DQL_RESPONSE["entries"]
        ]
        state = self.client.get_lifecycle_state("0900000180001001")
        self.assertEqual(state["policy_id"], "4600000180000001")
        self.assertEqual(state["current_state"], 2)

    @patch.object(DocumentumClient, "query_dql")
    def test_get_lifecycle_state_no_lifecycle(self, mock_dql):
        """Documents without lifecycle return empty policy and state -1."""
        mock_dql.return_value = []
        state = self.client.get_lifecycle_state("0900000180001099")
        self.assertEqual(state["policy_id"], "")
        self.assertEqual(state["current_state"], -1)


class TestRealisticRenditions(unittest.TestCase):
    """Tests rendition queries (PDF + thumbnail renditions)."""

    def setUp(self):
        self.client = DocumentumClient(
            base_url="https://dctm.acme-corp.com/dctm-rest",
            repository="acme_repo",
            max_retries=1,
        )

    @patch.object(DocumentumClient, "query_dql")
    def test_get_renditions_multiple(self, mock_dql):
        """Real docs often have PDF + JPEG thumbnail renditions."""
        mock_dql.return_value = [
            entry["content"]["properties"]
            for entry in DCTM_RENDITIONS_DQL_RESPONSE["entries"]
        ]
        renditions = self.client.get_renditions("0900000180001001")
        self.assertEqual(len(renditions), 2)

        formats = {r["full_format"] for r in renditions}
        self.assertIn("pdf", formats)
        self.assertIn("jpeg", formats)


class TestRealisticExtractAll(unittest.TestCase):
    """Full extraction from realistic Documentum repository."""

    @patch.object(DocumentumClient, "get_lifecycle_state")
    @patch.object(DocumentumClient, "get_object_acl")
    @patch.object(DocumentumClient, "walk_tree")
    def test_extract_all_enterprise_repo(self, mock_walk, mock_acl, mock_lifecycle):
        """Simulates extracting from a real enterprise Documentum repository."""
        mock_walk.return_value = [
            {"id": "0900000180001001", "name": "2024_Annual_Report.pdf",
             "type": "dm_document", "size": 4500000,
             "create_date": "2024-01-15T10:00:00.000+00:00",
             "modify_date": "2024-12-01T15:30:00.000+00:00",
             "owner": "jsmith", "mime_type": "application/pdf",
             "depth": 0, "parent_id": "0c00000180000200",
             "path": "/Enterprise Documents/2024_Annual_Report.pdf"},
            {"id": "0900000180001002", "name": "Contract_Template_NDA.docx",
             "type": "dm_document", "size": 156000,
             "create_date": "2023-05-20T09:00:00.000+00:00",
             "modify_date": "2024-08-10T11:00:00.000+00:00",
             "owner": "legal_admin",
             "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "depth": 0, "parent_id": "0c00000180000200",
             "path": "/Enterprise Documents/Contract_Template_NDA.docx"},
            {"id": "0b00000180002001", "name": "Compliance",
             "type": "dm_folder", "size": 0,
             "create_date": "2020-03-01T08:00:00.000+00:00",
             "modify_date": "2024-11-30T16:00:00.000+00:00",
             "owner": "dmadmin", "mime_type": "",
             "depth": 0, "parent_id": "0c00000180000200",
             "path": "/Enterprise Documents/Compliance"},
        ]

        mock_acl.side_effect = [
            {"object_id": "0900000180001001", "acl_entries": [
                {"r_accessor_name": "dm_world", "r_accessor_permit": 3, "r_is_group": True},
                {"r_accessor_name": "finance_group", "r_accessor_permit": 6, "r_is_group": True},
            ]},
            {"object_id": "0900000180001002", "acl_entries": [
                {"r_accessor_name": "legal_group", "r_accessor_permit": 6, "r_is_group": True},
            ]},
            {"object_id": "0b00000180002001", "acl_entries": [
                {"r_accessor_name": "dm_world", "r_accessor_permit": 3, "r_is_group": True},
            ]},
        ]

        mock_lifecycle.side_effect = [
            {"object_id": "0900000180001001", "policy_id": "4600000180000001", "current_state": 2},
            {"object_id": "0900000180001002", "policy_id": "", "current_state": -1},
            {"object_id": "0b00000180002001", "policy_id": "", "current_state": -1},
        ]

        client = DocumentumClient(
            base_url="https://dctm.acme-corp.com/dctm-rest",
            repository="acme_repo",
            max_retries=1,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            files = client.extract_all(root_folder_id="0c00000180000200", output_dir=tmpdir)
            self.assertIn("nodes.json", files)
            self.assertTrue(Path(files["nodes.json"]).exists())

            with open(files["nodes.json"], encoding="utf-8") as f:
                nodes = json.load(f)
            self.assertEqual(len(nodes), 3)

            # Verify document types
            docs = [n for n in nodes if n["type"] == "dm_document"]
            folders = [n for n in nodes if n["type"] == "dm_folder"]
            self.assertEqual(len(docs), 2)
            self.assertEqual(len(folders), 1)


if __name__ == "__main__":
    unittest.main()
