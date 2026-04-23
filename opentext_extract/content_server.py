"""OpenText Content Server REST v2 API client.

Extracts nodes, metadata, categories, permissions, workflows from Content Server.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .api_client import APIClient, APIError

logger = logging.getLogger(__name__)


class ContentServerClient(APIClient):
    """Client for OpenText Content Server REST v2 API."""

    # Content Server node types
    NODE_TYPE_FOLDER = 0
    NODE_TYPE_DOCUMENT = 144
    NODE_TYPE_URL = 140
    NODE_TYPE_SHORTCUT = 1
    NODE_TYPE_COLLECTION = 298

    def authenticate(self) -> str:
        """Authenticate via /api/v1/auth endpoint."""
        logger.info("Authenticating to Content Server: %s", self.base_url)
        data = self.post("api/v1/auth", {"username": self.username, "password": self.password})
        self._token = data.get("ticket", "")
        if not self._token:
            raise APIError("Authentication failed: no ticket returned")
        logger.info("Authentication successful")
        return self._token

    # ── Node Operations ─────────────────────────────────────────

    def get_node(self, node_id: int) -> dict[str, Any]:
        """Get a single node by ID."""
        resp = self.get(f"api/v2/nodes/{node_id}")
        return resp.get("results", resp)

    def get_children(self, node_id: int) -> list[dict[str, Any]]:
        """Get all children of a node (paginated)."""
        return self.get_paginated(
            f"api/v2/nodes/{node_id}/nodes",
            results_key="results",
        )

    def walk_tree(
        self,
        root_id: int,
        max_depth: int = -1,
        _current_depth: int = 0,
    ) -> list[dict[str, Any]]:
        """Recursively walk the node tree from a root node.

        Returns flat list of all nodes with their depth level.
        """
        if max_depth != -1 and _current_depth > max_depth:
            return []

        nodes: list[dict[str, Any]] = []
        children = self.get_children(root_id)

        for child in children:
            child_data = child.get("data", child)
            properties = child_data.get("properties", {})
            node_id = properties.get("id", 0)
            node_type = properties.get("type", -1)
            node_name = properties.get("name", "")

            node_info = {
                "id": node_id,
                "name": node_name,
                "type": node_type,
                "parent_id": root_id,
                "depth": _current_depth,
                "size": properties.get("size", 0),
                "create_date": properties.get("create_date", ""),
                "modify_date": properties.get("modify_date", ""),
                "created_by": properties.get("create_user_id", 0),
                "modified_by": properties.get("modify_user_id", 0),
                "mime_type": properties.get("mime_type", ""),
                "description": properties.get("description", ""),
            }
            nodes.append(node_info)

            # Recurse into folders
            if node_type == self.NODE_TYPE_FOLDER:
                sub_nodes = self.walk_tree(node_id, max_depth, _current_depth + 1)
                nodes.extend(sub_nodes)

        logger.debug("walk_tree(%d): found %d nodes at depth %d", root_id, len(nodes), _current_depth)
        return nodes

    # ── Metadata / Categories ───────────────────────────────────

    def get_categories(self, node_id: int) -> list[dict[str, Any]]:
        """Get categories (metadata) assigned to a node."""
        try:
            resp = self.get(f"api/v2/nodes/{node_id}/categories")
            return resp.get("results", [])
        except APIError as e:
            if e.status_code == 404:
                return []
            raise

    def extract_metadata(self, node_id: int) -> dict[str, Any]:
        """Extract all metadata for a node: categories + attributes."""
        categories = self.get_categories(node_id)
        metadata: dict[str, Any] = {
            "node_id": node_id,
            "categories": [],
        }
        for cat in categories:
            cat_data = cat.get("data", cat)
            cat_info = {
                "category_id": cat_data.get("id", 0),
                "category_name": cat_data.get("name", ""),
                "attributes": cat_data.get("attributes", {}),
            }
            metadata["categories"].append(cat_info)
        return metadata

    # ── Permissions ─────────────────────────────────────────────

    def get_permissions(self, node_id: int) -> dict[str, Any]:
        """Get permission (ACL) entries for a node."""
        try:
            resp = self.get(f"api/v2/nodes/{node_id}/permissions")
            return resp.get("results", resp)
        except APIError as e:
            if e.status_code == 404:
                return {}
            raise

    def extract_permissions(self, node_id: int) -> dict[str, Any]:
        """Extract permission data for a node into standard format."""
        raw = self.get_permissions(node_id)
        permissions_data = raw.get("data", raw)

        entries: list[dict[str, Any]] = []
        for perm_type in ("owner", "group", "public"):
            perm_block = permissions_data.get(perm_type, {})
            if perm_block:
                entries.append({
                    "type": perm_type,
                    "permissions": perm_block.get("permissions", []),
                    "right_id": perm_block.get("right_id", 0),
                })

        # Custom ACLs
        custom = permissions_data.get("custom", [])
        for c in custom:
            entries.append({
                "type": "custom",
                "right_id": c.get("right_id", 0),
                "name": c.get("name", ""),
                "permissions": c.get("permissions", []),
            })

        return {"node_id": node_id, "entries": entries}

    # ── Versions ────────────────────────────────────────────────

    def get_versions(self, node_id: int) -> list[dict[str, Any]]:
        """Get version history for a document node."""
        try:
            resp = self.get(f"api/v2/nodes/{node_id}/versions")
            data = resp.get("data", [])
            versions: list[dict[str, Any]] = []
            for v in data:
                versions.append({
                    "version_number": v.get("version_number", 0),
                    "version_id": v.get("version_id", 0),
                    "create_date": v.get("create_date", ""),
                    "created_by": v.get("owner_id", 0),
                    "file_size": v.get("file_size", 0),
                    "mime_type": v.get("mime_type", ""),
                    "description": v.get("description", ""),
                })
            return versions
        except APIError as e:
            if e.status_code == 404:
                return []
            raise

    # ── Workflows ───────────────────────────────────────────────

    def get_workflows(self) -> list[dict[str, Any]]:
        """Get workflow definitions from the server."""
        try:
            return self.get_paginated("api/v2/workflows", results_key="results")
        except APIError as e:
            logger.warning("Could not fetch workflows: %s", e)
            return []

    def get_workflow_for_node(self, node_id: int) -> dict[str, Any] | None:
        """Get active workflow for a specific node."""
        try:
            resp = self.get(f"api/v2/nodes/{node_id}/workflows")
            results = resp.get("results", [])
            return results[0] if results else None
        except APIError:
            return None

    # ── Members (Users / Groups) ────────────────────────────────

    def get_members(self) -> list[dict[str, Any]]:
        """Get all users and groups."""
        return self.get_paginated("api/v2/members", results_key="results")

    # ── Full Extraction Pipeline ────────────────────────────────

    def extract_all(
        self,
        root_id: int,
        output_dir: str | Path,
        max_depth: int = -1,
        include_versions: bool = True,
        include_workflows: bool = False,
    ) -> dict[str, Path]:
        """Run full extraction and write intermediate JSON files.

        Returns dict of {filename: path} for all generated files.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        files: dict[str, Path] = {}

        # 1. Walk node tree
        logger.info("Extracting node tree from root %d...", root_id)
        nodes = self.walk_tree(root_id, max_depth)
        files["nodes.json"] = self._write_json(out / "nodes.json", nodes)
        logger.info("Extracted %d nodes", len(nodes))

        # 2. Extract metadata for each node
        logger.info("Extracting metadata...")
        all_metadata: list[dict[str, Any]] = []
        for node in nodes:
            meta = self.extract_metadata(node["id"])
            if meta["categories"]:
                all_metadata.append(meta)
        files["metadata.json"] = self._write_json(out / "metadata.json", all_metadata)

        # 3. Extract permissions
        logger.info("Extracting permissions...")
        all_perms: list[dict[str, Any]] = []
        for node in nodes:
            perms = self.extract_permissions(node["id"])
            if perms["entries"]:
                all_perms.append(perms)
        files["permissions.json"] = self._write_json(out / "permissions.json", all_perms)

        # 4. Build documents manifest
        doc_nodes = [n for n in nodes if n["type"] == self.NODE_TYPE_DOCUMENT]
        documents: list[dict[str, Any]] = []
        for doc in doc_nodes:
            doc_entry = {
                "node_id": doc["id"],
                "name": doc["name"],
                "size": doc["size"],
                "mime_type": doc["mime_type"],
                "create_date": doc["create_date"],
                "modify_date": doc["modify_date"],
            }
            if include_versions:
                doc_entry["versions"] = self.get_versions(doc["id"])
            documents.append(doc_entry)
        files["documents.json"] = self._write_json(out / "documents.json", documents)
        logger.info("Extracted %d document entries", len(documents))

        # 5. Workflows (optional)
        if include_workflows:
            logger.info("Extracting workflows...")
            workflows = self.get_workflows()
            files["workflows.json"] = self._write_json(out / "workflows.json", workflows)

        # 6. Members
        logger.info("Extracting members (users/groups)...")
        try:
            members = self.get_members()
            files["members.json"] = self._write_json(out / "members.json", members)
        except APIError as e:
            logger.warning("Could not extract members: %s", e)

        return files

    @staticmethod
    def _write_json(path: Path, data: Any) -> Path:
        """Write data to JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.debug("Wrote %s", path)
        return path
