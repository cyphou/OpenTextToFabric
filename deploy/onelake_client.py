"""OneLake / ADLS Gen2 file upload client."""

from __future__ import annotations

import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ONELAKE_BASE = "https://onelake.dfs.fabric.microsoft.com"
_CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB


class OneLakeError(Exception):
    """Raised on OneLake API errors."""


class OneLakeClient:
    """Client for OneLake (ADLS Gen2) file operations.

    Supports creating directories and uploading files to OneLake
    using the DFS (Data Lake Storage) REST API.
    """

    def __init__(self, token_provider: Any) -> None:
        self._token_provider = token_provider

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> bytes:
        """Make an authenticated DFS request."""
        token = self._token_provider.get_token()
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            raise OneLakeError(f"OneLake {method} {e.code}: {body}") from e

    def create_directory(
        self,
        workspace_id: str,
        item_id: str,
        path: str,
    ) -> None:
        """Create a directory in a Lakehouse.

        Args:
            workspace_id: Fabric workspace GUID.
            item_id: Lakehouse item GUID.
            path: Directory path (e.g. 'Tables/my_table').
        """
        url = (
            f"{_ONELAKE_BASE}/{workspace_id}/{item_id}/{path}"
            "?resource=directory"
        )
        self._request("PUT", url)
        logger.debug("Created directory: %s/%s/%s", workspace_id, item_id, path)

    def upload_file(
        self,
        workspace_id: str,
        item_id: str,
        remote_path: str,
        local_path: str | Path,
    ) -> None:
        """Upload a local file to OneLake.

        Uses create + append + flush for files > 4MB,
        single PUT for smaller files.
        """
        local = Path(local_path)
        size = local.stat().st_size

        if size <= _CHUNK_SIZE:
            self._upload_small(workspace_id, item_id, remote_path, local)
        else:
            self._upload_chunked(workspace_id, item_id, remote_path, local, size)

        logger.info("Uploaded %s (%d bytes) → %s", local.name, size, remote_path)

    def upload_directory(
        self,
        workspace_id: str,
        item_id: str,
        remote_prefix: str,
        local_dir: str | Path,
    ) -> int:
        """Upload all files in a local directory to OneLake.

        Returns:
            Number of files uploaded.
        """
        local = Path(local_dir)
        count = 0
        for f in local.rglob("*"):
            if f.is_file():
                relative = f.relative_to(local).as_posix()
                remote = f"{remote_prefix}/{relative}" if remote_prefix else relative
                self.upload_file(workspace_id, item_id, remote, f)
                count += 1
        return count

    def _upload_small(
        self,
        workspace_id: str,
        item_id: str,
        remote_path: str,
        local: Path,
    ) -> None:
        """Upload a small file in a single request."""
        data = local.read_bytes()
        # Create the file
        url = (
            f"{_ONELAKE_BASE}/{workspace_id}/{item_id}/{remote_path}"
            "?resource=file"
        )
        self._request("PUT", url)

        # Append data
        url = (
            f"{_ONELAKE_BASE}/{workspace_id}/{item_id}/{remote_path}"
            f"?action=append&position=0"
        )
        self._request("PATCH", url, data=data, headers={
            "Content-Length": str(len(data)),
        })

        # Flush
        url = (
            f"{_ONELAKE_BASE}/{workspace_id}/{item_id}/{remote_path}"
            f"?action=flush&position={len(data)}"
        )
        self._request("PATCH", url)

    def _upload_chunked(
        self,
        workspace_id: str,
        item_id: str,
        remote_path: str,
        local: Path,
        total_size: int,
    ) -> None:
        """Upload a large file in chunks."""
        # Create the file
        url = (
            f"{_ONELAKE_BASE}/{workspace_id}/{item_id}/{remote_path}"
            "?resource=file"
        )
        self._request("PUT", url)

        # Append chunks
        position = 0
        with open(local, "rb") as f:
            while True:
                chunk = f.read(_CHUNK_SIZE)
                if not chunk:
                    break
                url = (
                    f"{_ONELAKE_BASE}/{workspace_id}/{item_id}/{remote_path}"
                    f"?action=append&position={position}"
                )
                self._request("PATCH", url, data=chunk, headers={
                    "Content-Length": str(len(chunk)),
                })
                position += len(chunk)

        # Flush
        url = (
            f"{_ONELAKE_BASE}/{workspace_id}/{item_id}/{remote_path}"
            f"?action=flush&position={total_size}"
        )
        self._request("PATCH", url)
