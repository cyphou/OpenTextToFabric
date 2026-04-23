"""OpenText Documentum REST API client.

Extracts cabinets, documents, objects, ACLs, lifecycles from Documentum.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .api_client import APIClient, APIError

logger = logging.getLogger(__name__)


class DocumentumClient(APIClient):
    """Client for OpenText Documentum REST Services."""

    def __init__(self, repository: str = "docbase", **kwargs: Any):
        super().__init__(**kwargs)
        self.repository = repository
        self._repo_base = f"dctm-rest/repositories/{repository}"

    def authenticate(self) -> str:
        """Authenticate via basic auth or token exchange."""
        logger.info("Authenticating to Documentum: %s (repo: %s)", self.base_url, self.repository)
        # Documentum REST uses basic auth in headers; verify by fetching repo info
        import base64
        creds = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        self._session_headers["Authorization"] = f"Basic {creds}"
        self._token = creds  # mark as authenticated

        try:
            self.get(f"{self._repo_base}")
            logger.info("Documentum authentication successful")
        except APIError as e:
            self._token = ""
            raise APIError(f"Documentum authentication failed: {e}") from e

        return self._token

    def _get_auth_headers(self) -> dict[str, str]:
        """Override to use Basic auth for Documentum."""
        headers = dict(self._session_headers)
        return headers

    # ── Object Operations ───────────────────────────────────────

    def get_object(self, object_id: str) -> dict[str, Any]:
        """Get a single Documentum object by r_object_id."""
        resp = self.get(f"{self._repo_base}/objects/{object_id}")
        return resp.get("properties", resp)

    def query_dql(self, dql: str) -> list[dict[str, Any]]:
        """Execute a DQL query and return results."""
        resp = self.get(f"{self._repo_base}/dql", params={"dql": dql})
        entries = resp.get("entries", [])
        return [e.get("content", {}).get("properties", e) for e in entries]

    # ── Cabinet / Folder Traversal ──────────────────────────────

    def get_cabinets(self) -> list[dict[str, Any]]:
        """Get all cabinets (top-level folders)."""
        resp = self.get(f"{self._repo_base}/cabinets")
        entries = resp.get("entries", [])
        cabinets: list[dict[str, Any]] = []
        for entry in entries:
            props = entry.get("content", {}).get("properties", {})
            cabinets.append({
                "id": props.get("r_object_id", ""),
                "name": props.get("object_name", ""),
                "type": "dm_cabinet",
                "path": f"/{props.get('object_name', '')}",
                "create_date": props.get("r_creation_date", ""),
                "modify_date": props.get("r_modify_date", ""),
                "owner": props.get("owner_name", ""),
            })
        return cabinets

    def get_folder_contents(self, folder_id: str) -> list[dict[str, Any]]:
        """Get contents of a folder."""
        dql = f"SELECT r_object_id, object_name, r_object_type, r_content_size, a_content_type, r_creation_date, r_modify_date, owner_name FROM dm_sysobject WHERE FOLDER(ID('{folder_id}'))"
        results = self.query_dql(dql)
        items: list[dict[str, Any]] = []
        for r in results:
            items.append({
                "id": r.get("r_object_id", ""),
                "name": r.get("object_name", ""),
                "type": r.get("r_object_type", ""),
                "size": r.get("r_content_size", 0),
                "mime_type": r.get("a_content_type", ""),
                "create_date": r.get("r_creation_date", ""),
                "modify_date": r.get("r_modify_date", ""),
                "owner": r.get("owner_name", ""),
            })
        return items

    def walk_tree(
        self,
        folder_id: str,
        max_depth: int = -1,
        _current_depth: int = 0,
        _path: str = "",
    ) -> list[dict[str, Any]]:
        """Recursively walk a Documentum folder tree."""
        if max_depth != -1 and _current_depth > max_depth:
            return []

        nodes: list[dict[str, Any]] = []
        contents = self.get_folder_contents(folder_id)

        for item in contents:
            item["depth"] = _current_depth
            item["parent_id"] = folder_id
            item["path"] = f"{_path}/{item['name']}"
            nodes.append(item)

            if item["type"] in ("dm_folder", "dm_cabinet"):
                sub = self.walk_tree(item["id"], max_depth, _current_depth + 1, item["path"])
                nodes.extend(sub)

        return nodes

    # ── ACL / Permissions ───────────────────────────────────────

    def get_object_acl(self, object_id: str) -> dict[str, Any]:
        """Get ACL for a Documentum object."""
        try:
            dql = f"SELECT r_accessor_name, r_accessor_permit, r_accessor_xpermit, r_is_group FROM dm_acl WHERE r_object_id IN (SELECT acl_domain || '.' || acl_name FROM dm_sysobject WHERE r_object_id = '{object_id}')"
            entries = self.query_dql(dql)
            return {"object_id": object_id, "acl_entries": entries}
        except APIError:
            return {"object_id": object_id, "acl_entries": []}

    PERMIT_LEVELS = {
        1: "None",
        2: "Browse",
        3: "Read",
        4: "Relate",
        5: "Version",
        6: "Write",
        7: "Delete",
    }

    # ── Lifecycle ───────────────────────────────────────────────

    def get_lifecycle_state(self, object_id: str) -> dict[str, Any]:
        """Get lifecycle state for a Documentum object."""
        try:
            dql = f"SELECT r_policy_id, r_current_state FROM dm_sysobject WHERE r_object_id = '{object_id}'"
            results = self.query_dql(dql)
            if results:
                return {
                    "object_id": object_id,
                    "policy_id": results[0].get("r_policy_id", ""),
                    "current_state": results[0].get("r_current_state", 0),
                }
        except APIError:
            pass
        return {"object_id": object_id, "policy_id": "", "current_state": -1}

    # ── Content Download ────────────────────────────────────────

    def get_content_url(self, object_id: str) -> str:
        """Get the download URL for a document's primary content."""
        return f"{self.base_url}/{self._repo_base}/objects/{object_id}/contents/content"

    def get_renditions(self, object_id: str) -> list[dict[str, Any]]:
        """List available renditions for a document."""
        try:
            dql = f"SELECT r_object_id, full_format, r_content_size FROM dmr_content WHERE ANY parent_id = '{object_id}'"
            return self.query_dql(dql)
        except APIError:
            return []

    # ── Full Extraction Pipeline ────────────────────────────────

    def extract_all(
        self,
        root_folder_id: str | None = None,
        output_dir: str | Path = "./output",
        max_depth: int = -1,
    ) -> dict[str, Path]:
        """Run full extraction and write intermediate JSON files."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        files: dict[str, Path] = {}

        # 1. Cabinets or walk from root
        if root_folder_id:
            logger.info("Walking tree from folder %s...", root_folder_id)
            nodes = self.walk_tree(root_folder_id, max_depth)
        else:
            logger.info("Extracting cabinets...")
            cabinets = self.get_cabinets()
            nodes = list(cabinets)
            for cab in cabinets:
                sub = self.walk_tree(cab["id"], max_depth, _path=cab.get("path", ""))
                nodes.extend(sub)

        files["nodes.json"] = self._write_json(out / "nodes.json", nodes)
        logger.info("Extracted %d nodes", len(nodes))

        # 2. ACLs
        logger.info("Extracting permissions...")
        permissions: list[dict[str, Any]] = []
        for node in nodes:
            acl = self.get_object_acl(node["id"])
            if acl["acl_entries"]:
                permissions.append(acl)
        files["permissions.json"] = self._write_json(out / "permissions.json", permissions)

        # 3. Documents manifest
        doc_types = ("dm_document", "dm_sysobject")
        doc_nodes = [n for n in nodes if n.get("type") in doc_types or n.get("size", 0) > 0]
        documents: list[dict[str, Any]] = []
        for doc in doc_nodes:
            doc_entry = {
                "object_id": doc["id"],
                "name": doc["name"],
                "size": doc.get("size", 0),
                "mime_type": doc.get("mime_type", ""),
                "path": doc.get("path", ""),
                "create_date": doc.get("create_date", ""),
                "modify_date": doc.get("modify_date", ""),
                "renditions": self.get_renditions(doc["id"]),
            }
            documents.append(doc_entry)
        files["documents.json"] = self._write_json(out / "documents.json", documents)

        # 4. Lifecycles
        logger.info("Extracting lifecycle states...")
        retention: list[dict[str, Any]] = []
        for doc in doc_nodes:
            lc = self.get_lifecycle_state(doc["id"])
            if lc["policy_id"]:
                retention.append(lc)
        files["retention.json"] = self._write_json(out / "retention.json", retention)

        return files

    @staticmethod
    def _write_json(path: Path, data: Any) -> Path:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return path
