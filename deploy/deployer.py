"""Deployment orchestrator — workspace provisioning → Lakehouse → report publish."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DeploymentError(Exception):
    """Raised when deployment fails."""


class Deployer:
    """Orchestrates deployment of migration output to a Fabric workspace.

    Deployment steps:
    1. Authenticate (via deploy.auth.TokenProvider)
    2. Create or find workspace
    3. Create Lakehouse + upload tables
    4. Create Semantic Model
    5. Create Report
    """

    def __init__(
        self,
        workspace_id: str = "",
        *,
        tenant_id: str = "",
        client_id: str = "",
        client_secret: str = "",
        create_workspace: bool = False,
        workspace_name: str = "",
        capacity_id: str = "",
    ) -> None:
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.create_workspace = create_workspace
        self.workspace_name = workspace_name
        self.capacity_id = capacity_id

    def deploy(self, output_dir: str | Path) -> dict[str, Any]:
        """Deploy migration output to Fabric workspace.

        Args:
            output_dir: Path to migration output directory.

        Returns:
            Dict with deployment results per artifact.
        """
        from .auth import TokenProvider
        from .fabric_client import FabricClient
        from .onelake_client import OneLakeClient

        out = Path(output_dir)
        results: dict[str, Any] = {"steps": [], "workspace_id": "", "errors": []}

        # 1. Authenticate
        token = TokenProvider(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        client = FabricClient(token)
        onelake = OneLakeClient(token)
        results["steps"].append({"step": "auth", "status": "success"})

        # 2. Workspace
        try:
            ws_id = self._ensure_workspace(client)
            results["workspace_id"] = ws_id
            results["steps"].append({"step": "workspace", "status": "success", "id": ws_id})
        except Exception as e:
            results["steps"].append({"step": "workspace", "status": "failed", "error": str(e)})
            results["errors"].append(str(e))
            return results

        # 3. Deploy Lakehouse artifacts
        lakehouse_result = self._deploy_lakehouse(client, onelake, ws_id, out)
        results["steps"].append(lakehouse_result)

        # 4. Deploy Semantic Model (TMDL)
        sm_result = self._deploy_semantic_model(client, ws_id, out)
        results["steps"].append(sm_result)

        # 5. Deploy Report (.pbip)
        report_result = self._deploy_report(client, ws_id, out)
        results["steps"].append(report_result)

        return results

    def _ensure_workspace(self, client: Any) -> str:
        """Get or create the target workspace."""
        if self.workspace_id:
            ws = client.get_workspace(self.workspace_id)
            logger.info("Using workspace: %s (%s)", ws.get("displayName"), self.workspace_id)
            return self.workspace_id

        if self.create_workspace and self.workspace_name:
            ws = client.create_workspace(
                self.workspace_name,
                capacity_id=self.capacity_id,
            )
            ws_id = ws.get("id", "")
            logger.info("Created workspace: %s (%s)", self.workspace_name, ws_id)
            return ws_id

        raise DeploymentError(
            "No workspace_id provided. Use --workspace-id or --create-workspace"
        )

    def _deploy_lakehouse(
        self,
        client: Any,
        onelake: Any,
        workspace_id: str,
        output_dir: Path,
    ) -> dict[str, Any]:
        """Deploy Lakehouse tables."""
        step: dict[str, Any] = {"step": "lakehouse", "status": "skipped"}

        # Check for Lakehouse artifacts
        lakehouse_dir = output_dir / "lakehouse"
        if not lakehouse_dir.exists():
            return step

        try:
            # Create Lakehouse
            lh = client.create_lakehouse(workspace_id, "MigratedLakehouse")
            lh_id = lh.get("id", "")

            # Upload table schemas / DDL
            file_count = onelake.upload_directory(
                workspace_id, lh_id, "Tables", lakehouse_dir
            )

            step.update({
                "status": "success",
                "lakehouse_id": lh_id,
                "files_uploaded": file_count,
            })
        except Exception as e:
            step.update({"status": "failed", "error": str(e)})
            logger.error("Lakehouse deployment failed: %s", e)

        return step

    def _deploy_semantic_model(
        self,
        client: Any,
        workspace_id: str,
        output_dir: Path,
    ) -> dict[str, Any]:
        """Deploy TMDL semantic model."""
        step: dict[str, Any] = {"step": "semantic_model", "status": "skipped"}

        # Find .SemanticModel directory
        sm_dirs = list(output_dir.rglob("*.SemanticModel"))
        if not sm_dirs:
            return step

        sm_dir = sm_dirs[0]
        sm_name = sm_dir.stem.replace(".SemanticModel", "")

        try:
            # Read definition files
            definition = self._read_definition_files(sm_dir)
            result = client.create_semantic_model(workspace_id, sm_name, definition)
            step.update({
                "status": "success",
                "item_id": result.get("id", ""),
                "name": sm_name,
            })
        except Exception as e:
            step.update({"status": "failed", "error": str(e)})
            logger.error("Semantic model deployment failed: %s", e)

        return step

    def _deploy_report(
        self,
        client: Any,
        workspace_id: str,
        output_dir: Path,
    ) -> dict[str, Any]:
        """Deploy Power BI report."""
        step: dict[str, Any] = {"step": "report", "status": "skipped"}

        # Find .Report directory
        report_dirs = list(output_dir.rglob("*.Report"))
        if not report_dirs:
            return step

        report_dir = report_dirs[0]
        report_name = report_dir.stem.replace(".Report", "")

        try:
            definition = self._read_definition_files(report_dir)
            result = client.create_report(workspace_id, report_name, definition)
            step.update({
                "status": "success",
                "item_id": result.get("id", ""),
                "name": report_name,
            })
        except Exception as e:
            step.update({"status": "failed", "error": str(e)})
            logger.error("Report deployment failed: %s", e)

        return step

    @staticmethod
    def _read_definition_files(root: Path) -> dict[str, Any]:
        """Read all definition files into a Fabric-compatible definition dict."""
        import base64

        parts: list[dict[str, str]] = []
        for f in root.rglob("*"):
            if f.is_file() and f.name != ".platform":
                relative = f.relative_to(root).as_posix()
                content = f.read_bytes()
                parts.append({
                    "path": relative,
                    "payload": base64.b64encode(content).decode(),
                    "payloadType": "InlineBase64",
                })

        return {"parts": parts}
