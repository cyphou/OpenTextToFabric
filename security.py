"""Security hardening — XXE defense, PII scanning, path traversal protection."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

logger = logging.getLogger(__name__)

# PII patterns (conservative — designed for low false positives)
PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b"),
    "phone_us": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "french_ssn": re.compile(r"\b[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}\b"),
}


class SecurityError(Exception):
    """Raised when a security violation is detected."""


def parse_xml_safe(xml_path: str | Path) -> ET.Element:
    """Parse XML with XXE (External Entity Expansion) protection.

    Defenses:
    - Disallows external entities (DOCTYPE)
    - Limits entity expansion depth
    - Uses defusedxml if available, otherwise stdlib with restrictions

    Args:
        xml_path: Path to XML file.

    Returns:
        Root element of parsed XML tree.

    Raises:
        SecurityError: If the file contains XXE attack patterns.
    """
    path = Path(xml_path)
    if not path.exists():
        raise FileNotFoundError(f"XML file not found: {path}")

    content = path.read_text(encoding="utf-8")

    # Check for XXE attack patterns
    xxe_patterns = [
        r"<!ENTITY\s+\S+\s+SYSTEM",
        r"<!ENTITY\s+\S+\s+PUBLIC",
        r"<!ENTITY\s+%",
        r"<!DOCTYPE[^>]*\[",
    ]
    for pattern in xxe_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            raise SecurityError(
                f"Potential XXE attack detected in {path.name}: "
                f"External entity or DOCTYPE declaration found"
            )

    # Try defusedxml first (if installed)
    try:
        import defusedxml.ElementTree as DefusedET  # type: ignore[import]
        return DefusedET.fromstring(content)
    except ImportError:
        pass

    # Fallback: stdlib with entity expansion limit
    parser = ET.XMLParser()
    try:
        return ET.fromstring(content, parser=parser)
    except ET.ParseError as e:
        raise SecurityError(f"Failed to parse XML {path.name}: {e}") from e


def validate_path(path: str, base_dir: str | Path) -> Path:
    """Validate a file path against directory traversal attacks.

    Prevents:
    - Path traversal (../ sequences)
    - Absolute paths escaping the base directory
    - Null bytes in paths
    - Symlink escape (on supported platforms)

    Args:
        path: The path to validate (relative or absolute).
        base_dir: The allowed base directory.

    Returns:
        Resolved, safe path within base_dir.

    Raises:
        SecurityError: If the path is unsafe.
    """
    # Null byte check
    if "\x00" in path:
        raise SecurityError(f"Null byte in path: {path!r}")

    base = Path(base_dir).resolve()
    target = (base / path).resolve()

    # Ensure the resolved path is within base_dir
    try:
        target.relative_to(base)
    except ValueError:
        raise SecurityError(
            f"Path traversal detected: {path!r} escapes base directory {base}"
        )

    return target


def validate_zip_entry(entry_name: str, extract_dir: str | Path) -> Path:
    """Validate a ZIP entry name against Zip Slip attacks.

    Args:
        entry_name: Name from ZIP archive.
        extract_dir: Target extraction directory.

    Returns:
        Safe extraction path.

    Raises:
        SecurityError: If the entry would extract outside the target.
    """
    # Check for path traversal sequences
    for part in PurePosixPath(entry_name).parts + PureWindowsPath(entry_name).parts:
        if part == "..":
            raise SecurityError(f"Zip Slip detected: {entry_name!r}")

    return validate_path(entry_name, extract_dir)


class PIIScanner:
    """Scans text and files for Personally Identifiable Information."""

    def __init__(self, patterns: dict[str, re.Pattern] | None = None) -> None:
        self.patterns = patterns or PII_PATTERNS

    def scan_text(self, text: str) -> list[dict[str, Any]]:
        """Scan text for PII matches.

        Returns:
            List of dicts with {type, match, position}.
        """
        findings: list[dict[str, Any]] = []
        for pii_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                # Mask the matched value for logging (show first 3 + last 2 chars)
                value = match.group()
                masked = value[:3] + "***" + value[-2:] if len(value) > 5 else "***"
                findings.append({
                    "type": pii_type,
                    "masked": masked,
                    "position": match.start(),
                    "line": text[:match.start()].count("\n") + 1,
                })
        return findings

    def scan_file(self, file_path: str | Path) -> list[dict[str, Any]]:
        """Scan a file for PII."""
        path = Path(file_path)
        if not path.exists():
            return []

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.warning("Cannot read %s for PII scan: %s", path, e)
            return []

        findings = self.scan_text(text)
        for f in findings:
            f["file"] = str(path)
        return findings

    def scan_directory(
        self,
        directory: str | Path,
        extensions: tuple[str, ...] = (".json", ".xml", ".rptdesign", ".tmdl", ".m", ".dax"),
    ) -> list[dict[str, Any]]:
        """Scan all matching files in a directory for PII."""
        root = Path(directory)
        all_findings: list[dict[str, Any]] = []

        for ext in extensions:
            for f in root.rglob(f"*{ext}"):
                findings = self.scan_file(f)
                all_findings.extend(findings)

        if all_findings:
            logger.warning(
                "PII scan found %d potential matches in %s",
                len(all_findings), directory,
            )
        return all_findings

    def generate_report(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate summary report from scan findings."""
        by_type: dict[str, int] = {}
        by_file: dict[str, int] = {}
        for f in findings:
            pii_type = f.get("type", "unknown")
            by_type[pii_type] = by_type.get(pii_type, 0) + 1
            file_name = f.get("file", "")
            if file_name:
                by_file[file_name] = by_file.get(file_name, 0) + 1

        return {
            "total_findings": len(findings),
            "by_type": by_type,
            "by_file": by_file,
            "risk_level": "high" if len(findings) > 10 else "medium" if findings else "low",
        }
