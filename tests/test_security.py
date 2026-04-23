"""Tests for security — XXE defense, PII scanning, path traversal."""

import os
import tempfile
import unittest
from pathlib import Path

from security import (
    parse_xml_safe,
    validate_path,
    validate_zip_entry,
    PIIScanner,
    SecurityError,
)


class TestXXEDefense(unittest.TestCase):

    def test_safe_xml_parses(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write('<?xml version="1.0"?><root><item>hello</item></root>')
            f.flush()
            temp = f.name

        try:
            root = parse_xml_safe(temp)
            self.assertEqual(root.tag, "root")
            self.assertEqual(root.find("item").text, "hello")
        finally:
            os.unlink(temp)

    def test_xxe_entity_blocked(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(
                '<?xml version="1.0"?>'
                '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
                "<root>&xxe;</root>"
            )
            f.flush()
            temp = f.name

        try:
            with self.assertRaises(SecurityError):
                parse_xml_safe(temp)
        finally:
            os.unlink(temp)

    def test_xxe_public_entity_blocked(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(
                '<?xml version="1.0"?>'
                '<!DOCTYPE foo [<!ENTITY xxe PUBLIC "id" "http://evil.com/xxe">]>'
                "<root>&xxe;</root>"
            )
            f.flush()
            temp = f.name

        try:
            with self.assertRaises(SecurityError):
                parse_xml_safe(temp)
        finally:
            os.unlink(temp)

    def test_xxe_parameter_entity_blocked(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(
                '<?xml version="1.0"?>'
                '<!DOCTYPE foo [<!ENTITY % xxe SYSTEM "file:///x">]>'
                "<root>test</root>"
            )
            f.flush()
            temp = f.name

        try:
            with self.assertRaises(SecurityError):
                parse_xml_safe(temp)
        finally:
            os.unlink(temp)

    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            parse_xml_safe("/nonexistent/file.xml")


class TestPathValidation(unittest.TestCase):

    def test_valid_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_path("sub/file.txt", tmpdir)
            expected = Path(tmpdir).resolve() / "sub" / "file.txt"
            self.assertEqual(result, expected)

    def test_path_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(SecurityError):
                validate_path("../../etc/passwd", tmpdir)

    def test_null_byte_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(SecurityError):
                validate_path("file\x00.txt", tmpdir)


class TestZipSlipDefense(unittest.TestCase):

    def test_safe_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_zip_entry("sub/file.txt", tmpdir)
            self.assertTrue(str(result).endswith("file.txt"))

    def test_zip_slip_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(SecurityError):
                validate_zip_entry("../../../etc/passwd", tmpdir)


class TestPIIScanner(unittest.TestCase):

    def setUp(self):
        self.scanner = PIIScanner()

    def test_detects_email(self):
        findings = self.scanner.scan_text("Contact: john.doe@example.com")
        types = [f["type"] for f in findings]
        self.assertIn("email", types)

    def test_detects_ssn(self):
        findings = self.scanner.scan_text("SSN: 123-45-6789")
        types = [f["type"] for f in findings]
        self.assertIn("ssn", types)

    def test_detects_credit_card(self):
        findings = self.scanner.scan_text("Card: 4111111111111111")
        types = [f["type"] for f in findings]
        self.assertIn("credit_card", types)

    def test_no_pii(self):
        findings = self.scanner.scan_text("Hello world, this is normal text")
        self.assertEqual(len(findings), 0)

    def test_masked_output(self):
        findings = self.scanner.scan_text("SSN: 123-45-6789")
        ssn_finding = next(f for f in findings if f["type"] == "ssn")
        self.assertNotIn("6789", ssn_finding.get("masked", ""))

    def test_scan_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write('{"email": "user@example.com"}')
            f.flush()
            temp = f.name

        try:
            findings = self.scanner.scan_file(temp)
            self.assertTrue(any(f["type"] == "email" for f in findings))
        finally:
            os.unlink(temp)

    def test_scan_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "data.json").write_text('{"ssn": "123-45-6789"}')
            (Path(tmpdir) / "readme.txt").write_text("no pii here")

            findings = self.scanner.scan_directory(tmpdir)
            self.assertTrue(any(f["type"] == "ssn" for f in findings))

    def test_generate_report(self):
        findings = [
            {"type": "email", "file": "a.json"},
            {"type": "email", "file": "b.json"},
            {"type": "ssn", "file": "a.json"},
        ]
        report = self.scanner.generate_report(findings)
        self.assertEqual(report["total_findings"], 3)
        self.assertEqual(report["by_type"]["email"], 2)
        self.assertEqual(report["by_type"]["ssn"], 1)
        self.assertEqual(report["risk_level"], "medium")


if __name__ == "__main__":
    unittest.main()
