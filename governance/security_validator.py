"""Security validation — path traversal defense, credential scrubbing, input sanitization."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

logger = logging.getLogger(__name__)

# Patterns that indicate potential credential data
_CREDENTIAL_PATTERNS = [
    re.compile(r"password\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"secret\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"token\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"Basic\s+[A-Za-z0-9+/]+=*", re.IGNORECASE),
]

# Sensitive field names to redact from metadata
_SENSITIVE_FIELDS = frozenset({
    "password", "secret", "token", "api_key", "apikey",
    "access_key", "private_key", "credential", "auth",
    "connection_string", "connectionstring",
})


class SecurityError(Exception):
    """Raised when a security violation is detected."""


def validate_path(path: str | Path, base_dir: str | Path) -> Path:
    """Validate that a path does not escape the base directory.

    Prevents path traversal (ZIP slip, directory escape).

    Args:
        path: The path to validate.
        base_dir: The allowed base directory.

    Returns:
        Resolved absolute path.

    Raises:
        SecurityError: If path escapes base directory.
    """
    base = Path(base_dir).resolve()
    target = (base / path).resolve()

    if not str(target).startswith(str(base)):
        raise SecurityError(
            f"Path traversal detected: '{path}' resolves outside base directory '{base}'"
        )

    return target


def validate_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal.

    Args:
        filename: Raw filename from source system.

    Returns:
        Sanitized filename safe for local filesystem.

    Raises:
        SecurityError: If filename contains dangerous patterns.
    """
    # Check for null bytes
    if "\x00" in filename:
        raise SecurityError(f"Null byte in filename: {filename!r}")

    # Strip path separators
    safe = filename.replace("/", "_").replace("\\", "_")

    # Prevent .. traversal
    if ".." in safe:
        safe = safe.replace("..", "_")

    # Strip leading dots (hidden files) and spaces
    safe = safe.lstrip(". ")

    # Limit length
    if len(safe) > 255:
        ext = Path(safe).suffix
        safe = safe[:255 - len(ext)] + ext

    if not safe:
        safe = "unnamed"

    return safe


def scrub_credentials(text: str) -> str:
    """Remove credential patterns from text (for logging/exports).

    Args:
        text: Text that may contain credentials.

    Returns:
        Text with credentials replaced by [REDACTED].
    """
    result = text
    for pattern in _CREDENTIAL_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def scrub_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive fields from metadata dictionaries.

    Args:
        metadata: Metadata dict that may contain sensitive values.

    Returns:
        Copy of metadata with sensitive values replaced.
    """
    scrubbed: dict[str, Any] = {}
    for key, value in metadata.items():
        lower_key = key.lower().replace("-", "_").replace(" ", "_")
        if lower_key in _SENSITIVE_FIELDS:
            scrubbed[key] = "[REDACTED]"
        elif isinstance(value, dict):
            scrubbed[key] = scrub_metadata(value)
        elif isinstance(value, list):
            scrubbed[key] = [
                scrub_metadata(item) if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, str):
            scrubbed[key] = scrub_credentials(value)
        else:
            scrubbed[key] = value
    return scrubbed


def validate_url(url: str) -> bool:
    """Basic URL validation — ensure it uses http/https scheme."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def validate_json_size(data: str | bytes, max_bytes: int = 50 * 1024 * 1024) -> bool:
    """Check that JSON data doesn't exceed maximum size (default 50 MB).

    Prevents memory exhaustion from excessively large API responses.
    """
    size = len(data) if isinstance(data, bytes) else len(data.encode("utf-8"))
    if size > max_bytes:
        logger.warning("JSON payload exceeds limit: %d bytes > %d bytes", size, max_bytes)
        return False
    return True
