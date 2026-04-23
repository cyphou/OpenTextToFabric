"""Tests for governance modules: security_validator, acl_mapper, classification_mapper, purview_mapper, audit."""

import tempfile
import unittest
from pathlib import Path

from governance.security_validator import (
    validate_path, validate_filename, scrub_credentials, scrub_metadata,
    validate_url, validate_json_size, SecurityError,
)
from governance.acl_mapper import ACLMapper
from governance.classification_mapper import ClassificationMapper
from governance.purview_mapper import PurviewMapper
from governance.audit import AuditTrail


class TestValidatePath(unittest.TestCase):

    def test_valid_subpath(self):
        with tempfile.TemporaryDirectory() as base:
            result = validate_path("subdir/file.txt", base)
            self.assertTrue(str(result).startswith(str(Path(base).resolve())))

    def test_traversal_attack(self):
        with tempfile.TemporaryDirectory() as base:
            with self.assertRaises(SecurityError):
                validate_path("../../etc/passwd", base)

    def test_traversal_with_backslash(self):
        with tempfile.TemporaryDirectory() as base:
            # On Windows, this should still be caught
            with self.assertRaises(SecurityError):
                validate_path("..\\..\\windows\\system32", base)


class TestValidateFilename(unittest.TestCase):

    def test_safe_filename(self):
        self.assertEqual(validate_filename("report.pdf"), "report.pdf")

    def test_strips_path_separators(self):
        result = validate_filename("../../etc/passwd")
        self.assertNotIn("/", result)
        self.assertNotIn("..", result)

    def test_null_byte_raises(self):
        with self.assertRaises(SecurityError):
            validate_filename("file\x00.txt")

    def test_empty_returns_unnamed(self):
        self.assertEqual(validate_filename(""), "unnamed")

    def test_long_filename_truncated(self):
        result = validate_filename("a" * 300 + ".pdf")
        self.assertTrue(len(result) <= 255)


class TestScrubCredentials(unittest.TestCase):

    def test_scrub_password(self):
        result = scrub_credentials("password=secret123")
        self.assertEqual(result, "[REDACTED]")

    def test_scrub_bearer_token(self):
        result = scrub_credentials("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9")
        self.assertIn("[REDACTED]", result)

    def test_no_credentials_unchanged(self):
        text = "This is a normal log message"
        self.assertEqual(scrub_credentials(text), text)


class TestScrubMetadata(unittest.TestCase):

    def test_redacts_sensitive_fields(self):
        meta = {"name": "doc.pdf", "password": "secret", "token": "abc123"}
        result = scrub_metadata(meta)
        self.assertEqual(result["name"], "doc.pdf")
        self.assertEqual(result["password"], "[REDACTED]")
        self.assertEqual(result["token"], "[REDACTED]")

    def test_nested_redaction(self):
        meta = {"config": {"api_key": "xyz"}}
        result = scrub_metadata(meta)
        self.assertEqual(result["config"]["api_key"], "[REDACTED]")


class TestValidateUrl(unittest.TestCase):

    def test_valid_https(self):
        self.assertTrue(validate_url("https://example.com/api"))

    def test_valid_http(self):
        self.assertTrue(validate_url("http://localhost:8080"))

    def test_invalid_scheme(self):
        self.assertFalse(validate_url("ftp://example.com"))

    def test_invalid_url(self):
        self.assertFalse(validate_url("not a url"))


class TestValidateJsonSize(unittest.TestCase):

    def test_within_limit(self):
        self.assertTrue(validate_json_size("small data"))

    def test_exceeds_limit(self):
        self.assertFalse(validate_json_size("x" * 100, max_bytes=50))


class TestACLMapper(unittest.TestCase):

    def setUp(self):
        self.mapper = ACLMapper(
            group_mapping={"Admins": "AdminGroup@contoso.com"},
            user_mapping={"jdoe": "john.doe@contoso.com"},
        )

    def test_map_cs_permissions(self):
        perms = [{
            "node_id": 100,
            "entries": [
                {"type": "custom", "name": "jdoe", "permissions": ["see", "see_contents"]},
            ],
        }]
        roles = self.mapper.map_cs_permissions(perms)
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0]["entra_identity"], "john.doe@contoso.com")

    def test_map_dctm_permissions(self):
        perms = [{
            "object_id": "obj123",
            "acl_entries": [
                {"r_accessor_name": "Admins", "r_accessor_permit": 3, "r_is_group": True},
            ],
        }]
        roles = self.mapper.map_dctm_permissions(perms)
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0]["entra_identity"], "AdminGroup@contoso.com")
        self.assertEqual(roles[0]["access_level"], "read")

    def test_generate_rls_dax(self):
        roles = [{"entra_identity": "john.doe@contoso.com", "access_level": "read"}]
        rls = self.mapper.generate_rls_dax(roles)
        self.assertEqual(len(rls), 1)
        self.assertIn("USERPRINCIPALNAME()", rls[0]["dax_expression"])


class TestClassificationMapper(unittest.TestCase):

    def setUp(self):
        self.mapper = ClassificationMapper()

    def test_map_confidential(self):
        self.assertEqual(self.mapper.map_category("Confidential"), "Confidential")

    def test_map_public(self):
        self.assertEqual(self.mapper.map_category("Public"), "General")

    def test_map_unknown_returns_default(self):
        self.assertEqual(self.mapper.map_category("UnknownCategory"), "General")

    def test_map_metadata(self):
        metadata = [{
            "node_id": 100,
            "categories": [{"category_name": "Secret", "attributes": {}}],
        }]
        result = self.mapper.map_metadata(metadata)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["sensitivity_label"], "Highly Confidential")


class TestPurviewMapper(unittest.TestCase):

    def setUp(self):
        self.mapper = PurviewMapper()

    def test_map_retention_policy(self):
        result = self.mapper.map_retention_policy("permanent")
        self.assertEqual(result["retention_days"], -1)
        self.assertEqual(result["purview_label"], "Retain_Forever")

    def test_map_unknown_policy(self):
        result = self.mapper.map_retention_policy("unknown_policy")
        self.assertEqual(result["retention_days"], 1095)  # default

    def test_map_dctm_lifecycles(self):
        data = [{"object_id": "obj1", "policy_id": "permanent", "current_state": 0}]
        result = self.mapper.map_dctm_lifecycles(data)
        self.assertEqual(len(result), 1)


class TestAuditTrail(unittest.TestCase):

    def setUp(self):
        self.audit = AuditTrail()

    def test_log_entry(self):
        self.audit.log("extract", source_type="content_server", source_id="100")
        self.assertEqual(self.audit.entry_count, 1)

    def test_log_extraction(self):
        self.audit.log_extraction("content_server", 50, "nodes extracted")
        self.assertEqual(self.audit.entry_count, 1)

    def test_log_error(self):
        self.audit.log_error("extract", "100", "connection failed")
        self.assertEqual(self.audit.error_count, 1)

    def test_summary(self):
        self.audit.log("extract", status="success")
        self.audit.log_error("transform", "1", "failed")
        summary = self.audit.summary()
        self.assertEqual(summary["total_entries"], 2)
        self.assertEqual(summary["errors"], 1)

    def test_export_json(self):
        self.audit.log("extract", source_type="cs")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.audit.export_json(tmpdir)
            self.assertTrue(path.exists())

    def test_export_csv(self):
        self.audit.log("extract", source_type="cs")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.audit.export_csv(tmpdir)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
