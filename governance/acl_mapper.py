"""ACL to Fabric RLS mapping — OpenText permissions → Row-Level Security roles."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Content Server permission bit flags
CS_PERM_SEE = 0x00001
CS_PERM_SEE_CONTENTS = 0x00002
CS_PERM_MODIFY = 0x00004
CS_PERM_EDIT_ATTRIBUTES = 0x00008
CS_PERM_ADD_ITEMS = 0x00020
CS_PERM_RESERVE = 0x00040
CS_PERM_DELETE_VERSIONS = 0x00080
CS_PERM_DELETE = 0x00100
CS_PERM_EDIT_PERMISSIONS = 0x00200

# Documentum permit levels
DCTM_NONE = 1
DCTM_BROWSE = 2
DCTM_READ = 3
DCTM_RELATE = 4
DCTM_VERSION = 5
DCTM_WRITE = 6
DCTM_DELETE = 7

# Fabric RLS role template
RLS_ROLE_TEMPLATE = """
table '{table_name}'
    filter = [{column}] = USERPRINCIPALNAME()
    || [{column}] IN PATHCONTAINS(USERPRINCIPALNAME(), "{group_path}")
"""


class ACLMapper:
    """Maps OpenText ACLs to Fabric Row-Level Security roles."""

    def __init__(
        self,
        group_mapping: dict[str, str] | None = None,
        user_mapping: dict[str, str] | None = None,
    ):
        """
        Args:
            group_mapping: OT group name → Entra ID group name/ID.
            user_mapping: OT username → Entra ID UPN.
        """
        self.group_mapping = group_mapping or {}
        self.user_mapping = user_mapping or {}

    def map_cs_permissions(
        self,
        permissions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Map Content Server ACL entries to RLS role definitions.

        Args:
            permissions: List of permission entries from permissions.json.

        Returns:
            List of RLS role definitions.
        """
        roles: list[dict[str, Any]] = []
        seen: set[str] = set()

        for perm_entry in permissions:
            node_id = perm_entry.get("node_id", "")
            for entry in perm_entry.get("entries", []):
                perm_type = entry.get("type", "")
                name = entry.get("name", perm_type)
                perms = entry.get("permissions", [])

                # Determine access level
                has_read = self._cs_has_permission(perms, CS_PERM_SEE | CS_PERM_SEE_CONTENTS)

                if has_read and name not in seen:
                    entra_name = self._resolve_identity(name, perm_type)
                    roles.append({
                        "source_name": name,
                        "source_type": perm_type,
                        "entra_identity": entra_name,
                        "access_level": "read",
                        "node_ids": [node_id],
                    })
                    seen.add(name)

        logger.info("Mapped %d CS ACL entries to %d RLS roles", len(permissions), len(roles))
        return roles

    def map_dctm_permissions(
        self,
        permissions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Map Documentum ACL entries to RLS role definitions.

        Args:
            permissions: List of permission entries from permissions.json.

        Returns:
            List of RLS role definitions.
        """
        roles: list[dict[str, Any]] = []

        for perm_entry in permissions:
            object_id = perm_entry.get("object_id", "")
            for entry in perm_entry.get("acl_entries", []):
                accessor = entry.get("r_accessor_name", "")
                permit = entry.get("r_accessor_permit", 0)
                is_group = entry.get("r_is_group", False)

                if permit >= DCTM_READ:
                    access = "read"
                    if permit >= DCTM_WRITE:
                        access = "write"
                    if permit >= DCTM_DELETE:
                        access = "admin"

                    entra_name = self._resolve_identity(
                        accessor,
                        "group" if is_group else "user",
                    )
                    roles.append({
                        "source_name": accessor,
                        "source_type": "group" if is_group else "user",
                        "entra_identity": entra_name,
                        "access_level": access,
                        "object_ids": [object_id],
                        "dctm_permit": permit,
                    })

        logger.info("Mapped %d DCTM ACL entries to %d RLS roles", len(permissions), len(roles))
        return roles

    def generate_rls_dax(
        self,
        roles: list[dict[str, Any]],
        table_name: str = "Documents",
        identity_column: str = "AllowedUsers",
    ) -> list[dict[str, str]]:
        """Generate DAX filter expressions for RLS roles.

        Returns list of {role_name, dax_expression} dicts.
        """
        rls_roles: list[dict[str, str]] = []

        # Group by entra identity
        by_identity: dict[str, list[dict[str, Any]]] = {}
        for role in roles:
            identity = role.get("entra_identity", "")
            if identity:
                by_identity.setdefault(identity, []).append(role)

        for identity, entries in by_identity.items():
            role_name = f"Role_{identity.split('@')[0]}" if "@" in identity else f"Role_{identity}"
            role_name = role_name.replace(" ", "_").replace(".", "_")

            dax = f'[{identity_column}] = USERPRINCIPALNAME()'
            rls_roles.append({
                "role_name": role_name,
                "dax_expression": dax,
                "identity": identity,
                "source_entries": len(entries),
            })

        return rls_roles

    def export_mapping(self, output_dir: str | Path) -> Path:
        """Export the identity mapping configuration."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        mapping = {
            "group_mapping": self.group_mapping,
            "user_mapping": self.user_mapping,
        }
        path = out / "identity_mapping.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2)
        return path

    def _resolve_identity(self, name: str, identity_type: str) -> str:
        """Resolve an OT identity to an Entra ID identity."""
        if identity_type == "group":
            return self.group_mapping.get(name, name)
        return self.user_mapping.get(name, name)

    @staticmethod
    def _cs_has_permission(perms: list | int, mask: int) -> bool:
        """Check if Content Server permission list/bitmap includes the mask."""
        if isinstance(perms, int):
            return bool(perms & mask)
        # If perms is a list of permission names, check for read-equivalent
        if isinstance(perms, list):
            read_perms = {"see", "see_contents", "read", "modify"}
            return bool(set(p.lower() for p in perms) & read_perms)
        return False
