"""Fabric REST API client — workspace list/create, item CRUD, import."""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from typing import Any

logger = logging.getLogger(__name__)

_API_BASE = "https://api.fabric.microsoft.com/v1"


class FabricAPIError(Exception):
    """Raised on Fabric REST API errors."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"Fabric API {status}: {message}")
        self.status = status


class FabricClient:
    """Client for Microsoft Fabric REST APIs.

    Uses stdlib urllib only — no external HTTP library required.
    """

    def __init__(self, token_provider: Any) -> None:
        """Initialize with a TokenProvider instance from deploy.auth."""
        self._token_provider = token_provider

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        timeout: int = 30,
    ) -> dict[str, Any] | list[Any]:
        """Make an authenticated API request."""
        url = f"{_API_BASE}{path}"
        data = json.dumps(body).encode() if body else None
        token = self._token_provider.get_token()

        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            body_text = e.read().decode(errors="replace")
            # Handle 429 (throttled) — log retry-after header
            if e.code == 429:
                retry_after = e.headers.get("Retry-After", "unknown")
                logger.warning("Throttled (429) — retry after %s seconds", retry_after)
            raise FabricAPIError(e.code, body_text) from e

    # ── Workspaces ──────────────────────────────────────────────

    def list_workspaces(self) -> list[dict[str, Any]]:
        """List all accessible workspaces."""
        result = self._request("GET", "/workspaces")
        return result.get("value", []) if isinstance(result, dict) else result

    def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        """Get workspace details."""
        result = self._request("GET", f"/workspaces/{workspace_id}")
        return result if isinstance(result, dict) else {}

    def create_workspace(
        self,
        display_name: str,
        *,
        capacity_id: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        """Create a new workspace."""
        body: dict[str, Any] = {"displayName": display_name}
        if capacity_id:
            body["capacityId"] = capacity_id
        if description:
            body["description"] = description
        result = self._request("POST", "/workspaces", body)
        return result if isinstance(result, dict) else {}

    # ── Items ───────────────────────────────────────────────────

    def list_items(
        self, workspace_id: str, item_type: str = ""
    ) -> list[dict[str, Any]]:
        """List items in a workspace, optionally filtered by type."""
        path = f"/workspaces/{workspace_id}/items"
        if item_type:
            path += f"?type={item_type}"
        result = self._request("GET", path)
        return result.get("value", []) if isinstance(result, dict) else result

    def create_item(
        self,
        workspace_id: str,
        display_name: str,
        item_type: str,
        *,
        definition: dict[str, Any] | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        """Create an item in a workspace."""
        body: dict[str, Any] = {
            "displayName": display_name,
            "type": item_type,
        }
        if description:
            body["description"] = description
        if definition:
            body["definition"] = definition
        result = self._request("POST", f"/workspaces/{workspace_id}/items", body)
        return result if isinstance(result, dict) else {}

    def delete_item(self, workspace_id: str, item_id: str) -> None:
        """Delete an item from a workspace."""
        self._request("DELETE", f"/workspaces/{workspace_id}/items/{item_id}")

    def get_item(
        self, workspace_id: str, item_id: str
    ) -> dict[str, Any]:
        """Get item details."""
        result = self._request(
            "GET", f"/workspaces/{workspace_id}/items/{item_id}"
        )
        return result if isinstance(result, dict) else {}

    # ── Lakehouses ──────────────────────────────────────────────

    def create_lakehouse(
        self, workspace_id: str, display_name: str
    ) -> dict[str, Any]:
        """Create a Lakehouse in a workspace."""
        return self.create_item(workspace_id, display_name, "Lakehouse")

    def list_lakehouses(self, workspace_id: str) -> list[dict[str, Any]]:
        """List Lakehouses in a workspace."""
        return self.list_items(workspace_id, "Lakehouse")

    # ── Semantic Models ─────────────────────────────────────────

    def create_semantic_model(
        self,
        workspace_id: str,
        display_name: str,
        definition: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a semantic model in a workspace."""
        return self.create_item(
            workspace_id, display_name, "SemanticModel", definition=definition
        )

    # ── Reports ─────────────────────────────────────────────────

    def create_report(
        self,
        workspace_id: str,
        display_name: str,
        definition: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a report in a workspace."""
        return self.create_item(
            workspace_id, display_name, "Report", definition=definition
        )
