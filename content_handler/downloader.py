"""Document binary downloader with chunked transfer and resume support."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB chunks


class DownloadError(Exception):
    """Raised when a download fails."""


class DocumentDownloader:
    """Handles chunked document downloads with resume and checksum verification."""

    def __init__(
        self,
        staging_dir: str | Path,
        headers: dict[str, str] | None = None,
        timeout: int = 60,
        verify_ssl: bool = True,
    ):
        self.staging_dir = Path(staging_dir)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.headers = headers or {}
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        self._manifest: list[dict[str, Any]] = []

    def download(
        self,
        url: str,
        filename: str,
        expected_size: int = 0,
        expected_checksum: str = "",
        subfolder: str = "",
    ) -> Path:
        """Download a single document to the staging area.

        Args:
            url: Download URL.
            filename: Target filename.
            expected_size: Expected file size for validation (0 = skip).
            expected_checksum: Expected SHA-256 hex digest (empty = skip).
            subfolder: Optional subfolder within staging area.

        Returns:
            Path to the downloaded file.
        """
        target_dir = self.staging_dir / subfolder if subfolder else self.staging_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / self._safe_filename(filename)

        # Resume support: skip if already downloaded and verified
        if target.exists() and expected_size > 0 and target.stat().st_size == expected_size:
            if not expected_checksum or self._verify_checksum(target, expected_checksum):
                logger.debug("Skipping already downloaded: %s", filename)
                return target

        logger.info("Downloading: %s", filename)
        try:
            req = urllib.request.Request(url, headers=self.headers)
            context = None
            if not self.verify_ssl:
                import ssl
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(req, timeout=self.timeout, context=context) as resp:
                tmp = target.with_suffix(".tmp")
                hasher = hashlib.sha256()
                total = 0
                with open(tmp, "wb") as f:
                    while True:
                        chunk = resp.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        hasher.update(chunk)
                        total += len(chunk)

                # Validate size
                if expected_size > 0 and total != expected_size:
                    tmp.unlink(missing_ok=True)
                    raise DownloadError(
                        f"Size mismatch for {filename}: expected {expected_size}, got {total}"
                    )

                # Validate checksum
                actual_checksum = hasher.hexdigest()
                if expected_checksum and actual_checksum != expected_checksum:
                    tmp.unlink(missing_ok=True)
                    raise DownloadError(
                        f"Checksum mismatch for {filename}: expected {expected_checksum}, got {actual_checksum}"
                    )

                # Atomic move
                shutil.move(str(tmp), str(target))
                logger.info("Downloaded: %s (%d bytes)", filename, total)

                self._manifest.append({
                    "filename": filename,
                    "path": str(target),
                    "size": total,
                    "checksum_sha256": actual_checksum,
                    "subfolder": subfolder,
                })

                return target

        except urllib.error.HTTPError as e:
            raise DownloadError(f"HTTP {e.code} downloading {filename}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise DownloadError(f"Connection error downloading {filename}: {e.reason}") from e

    def download_batch(
        self,
        items: list[dict[str, Any]],
        url_key: str = "url",
        name_key: str = "name",
    ) -> list[Path]:
        """Download multiple documents.

        Args:
            items: List of dicts with url, name, size, checksum fields.
            url_key: Key for the download URL in each item.
            name_key: Key for the filename in each item.

        Returns:
            List of paths to downloaded files.
        """
        paths: list[Path] = []
        total = len(items)
        for i, item in enumerate(items, 1):
            logger.info("Downloading %d/%d: %s", i, total, item.get(name_key, "unknown"))
            try:
                path = self.download(
                    url=item[url_key],
                    filename=item.get(name_key, f"doc_{i}"),
                    expected_size=item.get("size", 0),
                    expected_checksum=item.get("checksum", ""),
                    subfolder=item.get("subfolder", ""),
                )
                paths.append(path)
            except DownloadError as e:
                logger.error("Failed to download %s: %s", item.get(name_key, "unknown"), e)
        return paths

    def save_manifest(self, path: Path | None = None) -> Path:
        """Save download manifest to JSON."""
        target = path or (self.staging_dir / "download_manifest.json")
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self._manifest, f, indent=2)
        return target

    def cleanup(self) -> None:
        """Remove temporary files (.tmp) from staging area."""
        for tmp in self.staging_dir.rglob("*.tmp"):
            tmp.unlink(missing_ok=True)
            logger.debug("Cleaned up: %s", tmp)

    @staticmethod
    def _verify_checksum(path: Path, expected: str) -> bool:
        """Verify SHA-256 checksum of a file."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(_CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest() == expected

    @staticmethod
    def _safe_filename(name: str) -> str:
        """Sanitize filename — prevent path traversal."""
        # Strip directory separators and null bytes
        safe = name.replace("/", "_").replace("\\", "_").replace("\x00", "")
        # Prevent .. traversal
        safe = safe.replace("..", "_")
        # Limit length
        if len(safe) > 255:
            ext = Path(safe).suffix
            safe = safe[:255 - len(ext)] + ext
        return safe or "unnamed"
