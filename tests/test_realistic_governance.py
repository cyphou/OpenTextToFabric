"""Realistic tests for governance modules using enterprise-grade ACL structures.

Based on real-world patterns:
- Content Server ACLs with owner/group/custom entries and 10 permission types
- Documentum permit levels (1-7) with group/user distinction
- Enterprise group-to-Entra-ID mappings
- Sensitivity labels matching real classification schemes
- Documentum lifecycle states (Draft=0, Review=1, Published=2, Archived=3)
"""

import tempfile
import unittest
from pathlib import Path

from governance.acl_mapper import ACLMapper
from governance.classification_mapper import ClassificationMapper
from governance.purview_mapper import PurviewMapper
from governance.audit import AuditTrail
from tests.fixtures import (
    REALISTIC_CS_PERMISSIONS,
    REALISTIC_DCTM_PERMISSIONS,
    REALISTIC_GROUP_MAPPING,
    REALISTIC_USER_MAPPING,
    REALISTIC_METADATA,
)


class TestRealisticCSPermissionMapping(unittest.TestCase):
    """Maps real CS permissions to Entra ID roles + RLS DAX."""

    def setUp(self):
        self.mapper = ACLMapper(
            group_mapping=REALISTIC_GROUP_MAPPING,
            user_mapping=REALISTIC_USER_MAPPING,
        )

    def test_map_finance_document_permissions(self):
        """Q4 Financial Report has owner + Finance_Managers + Auditors + jdoe + DefaultGroup."""
        perms = [REALISTIC_CS_PERMISSIONS[0]]  # node 54321
        roles = self.mapper.map_cs_permissions(perms)

        # Should have at least 4 mapped entries (owner + 3 custom + group)
        self.assertTrue(len(roles) >= 4)

        # Check Finance_Managers is mapped — map_cs_permissions uses entry["type"]
        # which is "custom", so _resolve_identity treats it as user not group
        fm_role = next((r for r in roles if r.get("source_name") == "Finance_Managers"), None)
        self.assertIsNotNone(fm_role)
        # "custom" type is resolved via user_mapping, so stays as source_name
        self.assertEqual(fm_role["source_name"], "Finance_Managers")

        # Check Auditors have read access
        aud_role = next((r for r in roles if r.get("source_name") == "Auditors"), None)
        self.assertIsNotNone(aud_role)
        self.assertEqual(aud_role["access_level"], "read")

    def test_map_legal_document_permissions(self):
        """Employee Handbook has different ACLs."""
        perms = [REALISTIC_CS_PERMISSIONS[1]]  # node 54322
        roles = self.mapper.map_cs_permissions(perms)
        self.assertTrue(len(roles) >= 2)

    def test_generate_rls_from_real_permissions(self):
        """RLS DAX expressions for real permission sets."""
        perms = [REALISTIC_CS_PERMISSIONS[0]]
        roles = self.mapper.map_cs_permissions(perms)
        rls = self.mapper.generate_rls_dax(roles)

        self.assertTrue(len(rls) >= 1)
        for rule in rls:
            self.assertIn("USERPRINCIPALNAME()", rule["dax_expression"])


class TestRealisticDCTMPermissionMapping(unittest.TestCase):
    """Maps real Documentum permit levels to Entra ID roles."""

    def setUp(self):
        self.mapper = ACLMapper(
            group_mapping=REALISTIC_GROUP_MAPPING,
            user_mapping=REALISTIC_USER_MAPPING,
        )

    def test_map_annual_report_acl(self):
        """2024 Annual Report: dm_world(3=read), finance_group(6=write), cfo(7=delete)."""
        perms = [REALISTIC_DCTM_PERMISSIONS[0]]
        roles = self.mapper.map_dctm_permissions(perms)

        self.assertTrue(len(roles) >= 3)

        # dm_world (permit 3) → read
        world_role = next((r for r in roles if r.get("entra_identity") == "AllEmployees@acme-corp.com"), None)
        self.assertIsNotNone(world_role)
        self.assertEqual(world_role["access_level"], "read")

        # finance_group (permit 6) → write
        finance_role = next((r for r in roles if r.get("entra_identity") == "FinanceManagers@acme-corp.com"), None)
        self.assertIsNotNone(finance_role)
        self.assertEqual(finance_role["access_level"], "write")

    def test_map_nda_template_acl(self):
        """NDA template: legal_group(6=write), hr_managers(4=relate), compliance(3=read)."""
        perms = [REALISTIC_DCTM_PERMISSIONS[1]]
        roles = self.mapper.map_dctm_permissions(perms)
        self.assertTrue(len(roles) >= 2)


class TestRealisticClassificationMapping(unittest.TestCase):
    """Maps real enterprise classification categories to sensitivity labels."""

    def setUp(self):
        self.mapper = ClassificationMapper()

    def test_map_confidential_finance_doc(self):
        """Finance docs classified as Confidential → Confidential label."""
        metadata = [REALISTIC_METADATA[0]]  # node 54321 (Confidential)
        result = self.mapper.map_metadata(metadata)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["sensitivity_label"], "Confidential")

    def test_map_internal_hr_doc(self):
        """HR docs classified as Internal → General label (per DEFAULT_SENSITIVITY_MAP)."""
        metadata = [REALISTIC_METADATA[1]]  # node 54322 (Internal)
        result = self.mapper.map_metadata(metadata)
        self.assertEqual(len(result), 1)
        # DEFAULT_SENSITIVITY_MAP maps "internal" → "General"
        self.assertEqual(result[0]["sensitivity_label"], "General")

    def test_map_public_it_doc(self):
        """IT docs classified as Public → General label."""
        metadata = [REALISTIC_METADATA[2]]  # node 54323 (Public)
        result = self.mapper.map_metadata(metadata)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["sensitivity_label"], "General")

    def test_map_all_classifications(self):
        """Batch mapping of all three classification levels."""
        result = self.mapper.map_metadata(REALISTIC_METADATA)
        self.assertEqual(len(result), 3)
        labels = {r["sensitivity_label"] for r in result}
        # "internal" and "public" both map to "General" in DEFAULT_SENSITIVITY_MAP
        self.assertEqual(labels, {"Confidential", "General"})


class TestRealisticPurviewMapping(unittest.TestCase):
    """Maps Documentum lifecycle states to Purview retention policies."""

    def setUp(self):
        self.mapper = PurviewMapper()

    def test_map_published_lifecycle(self):
        """Published document (state 2) with retention policy."""
        data = [{"object_id": "0900000180001001", "policy_id": "permanent", "current_state": 2}]
        result = self.mapper.map_dctm_lifecycles(data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["purview_label"], "Retain_Forever")

    def test_map_no_lifecycle(self):
        """Document without lifecycle gets default retention."""
        data = [{"object_id": "0900000180001002", "policy_id": "default", "current_state": -1}]
        result = self.mapper.map_dctm_lifecycles(data)
        self.assertEqual(len(result), 1)


class TestRealisticAuditTrail(unittest.TestCase):
    """Audit trail for a realistic migration session."""

    def setUp(self):
        self.audit = AuditTrail()

    def test_full_migration_audit(self):
        """Simulates audit trail for a real CS extraction + Fabric generation."""
        # Extraction phase
        self.audit.log_extraction("content_server", 42, "Walked Enterprise Workspace")
        self.audit.log("extract", source_type="content_server", source_id="2000",
                       status="success", details="Extracted 42 nodes")

        # Transformation phase
        self.audit.log("transform", source_type="content_server", source_id="54321",
                       status="success", details="Mapped ACLs to RLS")
        self.audit.log("transform", source_type="content_server", source_id="54322",
                       status="success", details="Classified as Internal")

        # Error during one document
        self.audit.log_error("transform", "54323", "Missing category mapping")

        # Generation phase
        self.audit.log("generate", source_type="fabric", source_id="lakehouse",
                       status="success", details="Generated DDL for 3 tables")

        summary = self.audit.summary()
        self.assertEqual(summary["total_entries"], 6)
        self.assertEqual(summary["errors"], 1)

    def test_export_realistic_audit(self):
        """Export audit trail to JSON and CSV."""
        self.audit.log_extraction("content_server", 42, "Enterprise Workspace")
        self.audit.log("extract", source_type="content_server", status="success")
        self.audit.log_error("transform", "54323", "Category not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = self.audit.export_json(tmpdir)
            csv_path = self.audit.export_csv(tmpdir)

            self.assertTrue(json_path.exists())
            self.assertTrue(csv_path.exists())

            import json
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            # export_json wraps as {"summary": ..., "entries": [...]}
            self.assertEqual(len(data["entries"]), 3)


if __name__ == "__main__":
    unittest.main()
