"""Multi-tenant deployment — template substitution per tenant.

Supports deploying the same migration output to multiple Fabric
workspaces with tenant-specific configuration (connection strings,
parameters, RLS roles, workspace names).
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TenantConfig:
    """Configuration for a single tenant deployment."""

    def __init__(
        self,
        tenant_id: str,
        workspace_name: str,
        workspace_id: str = "",
        substitutions: dict[str, str] | None = None,
        rls_roles: list[str] | None = None,
        connection_overrides: dict[str, str] | None = None,
    ):
        self.tenant_id = tenant_id
        self.workspace_name = workspace_name
        self.workspace_id = workspace_id
        self.substitutions = substitutions or {}
        self.rls_roles = rls_roles or []
        self.connection_overrides = connection_overrides or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "workspace_name": self.workspace_name,
            "workspace_id": self.workspace_id,
            "substitutions": self.substitutions,
            "rls_roles": self.rls_roles,
            "connection_overrides": self.connection_overrides,
        }


class MultiTenantDeployer:
    """Deploy migration output to multiple tenant workspaces."""

    def __init__(self, template_dir: str | Path):
        self.template_dir = Path(template_dir)
        self._tenants: list[TenantConfig] = []
        self._results: list[dict[str, Any]] = []

    def add_tenant(self, tenant: TenantConfig) -> None:
        """Register a tenant for deployment."""
        self._tenants.append(tenant)

    def load_tenants(self, config_path: str | Path) -> int:
        """Load tenant configurations from a JSON file.

        Expected format:
        {
            "tenants": [
                {
                    "tenant_id": "acme",
                    "workspace_name": "ACME-Analytics",
                    "substitutions": {"{{COMPANY}}": "ACME Corp"},
                    "connection_overrides": {"source_db": "acme_prod"}
                }
            ]
        }
        """
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)

        for t in data.get("tenants", []):
            self._tenants.append(TenantConfig(
                tenant_id=t["tenant_id"],
                workspace_name=t["workspace_name"],
                workspace_id=t.get("workspace_id", ""),
                substitutions=t.get("substitutions", {}),
                rls_roles=t.get("rls_roles", []),
                connection_overrides=t.get("connection_overrides", {}),
            ))
        logger.info("Loaded %d tenant configurations", len(self._tenants))
        return len(self._tenants)

    def prepare_tenant_output(
        self,
        tenant: TenantConfig,
        output_base: str | Path,
    ) -> Path:
        """Prepare tenant-specific output by applying substitutions.

        Copies template artifacts and applies text substitutions to
        JSON, TMDL, and M query files.
        """
        output = Path(output_base) / tenant.tenant_id
        output.mkdir(parents=True, exist_ok=True)

        # Copy and substitute
        for src_file in self.template_dir.rglob("*"):
            if src_file.is_dir():
                continue
            rel = src_file.relative_to(self.template_dir)
            dst = output / rel
            dst.parent.mkdir(parents=True, exist_ok=True)

            if src_file.suffix in (".json", ".tmdl", ".m", ".pq", ".pbip", ".pbir", ".pbism"):
                content = src_file.read_text(encoding="utf-8")
                for placeholder, value in tenant.substitutions.items():
                    content = content.replace(placeholder, value)
                # Apply connection overrides
                if src_file.suffix in (".json", ".m", ".pq"):
                    for conn_key, conn_val in tenant.connection_overrides.items():
                        content = content.replace(f"{{{{CONNECTION:{conn_key}}}}}", conn_val)
                dst.write_text(content, encoding="utf-8")
            else:
                dst.write_bytes(src_file.read_bytes())

        logger.info("Prepared tenant output: %s → %s", tenant.tenant_id, output)
        return output

    def deploy_all(
        self,
        output_base: str | Path,
        deployer: Any = None,
    ) -> list[dict[str, Any]]:
        """Deploy to all registered tenants.

        Args:
            output_base: Base directory for tenant-specific outputs.
            deployer: Optional Deployer instance for actual Fabric deployment.

        Returns:
            List of deployment results per tenant.
        """
        results = []
        for tenant in self._tenants:
            try:
                tenant_dir = self.prepare_tenant_output(tenant, output_base)
                result = {
                    "tenant_id": tenant.tenant_id,
                    "workspace_name": tenant.workspace_name,
                    "output_dir": str(tenant_dir),
                    "status": "prepared",
                }

                if deployer is not None:
                    deploy_result = deployer.deploy(
                        source_dir=str(tenant_dir),
                        workspace_id=tenant.workspace_id,
                        workspace_name=tenant.workspace_name,
                    )
                    result["deploy_result"] = deploy_result
                    result["status"] = "deployed"

                results.append(result)
                logger.info("Tenant %s: %s", tenant.tenant_id, result["status"])

            except Exception as e:
                results.append({
                    "tenant_id": tenant.tenant_id,
                    "status": "failed",
                    "error": str(e),
                })
                logger.error("Tenant %s deployment failed: %s", tenant.tenant_id, e)

        self._results = results
        return results

    def summary(self) -> dict[str, Any]:
        """Return deployment summary."""
        return {
            "total_tenants": len(self._tenants),
            "deployed": sum(1 for r in self._results if r["status"] == "deployed"),
            "prepared": sum(1 for r in self._results if r["status"] == "prepared"),
            "failed": sum(1 for r in self._results if r["status"] == "failed"),
            "results": self._results,
        }


class BundleDeployer:
    """Deploy shared semantic model + thin reports as a bundle.

    This mirrors the TableauToPowerBI pattern where a shared semantic
    model is deployed once, and thin reports reference it via byPath.
    """

    def __init__(self, shared_model_dir: str | Path):
        self.shared_model_dir = Path(shared_model_dir)
        self._thin_reports: list[dict[str, Any]] = []

    def add_thin_report(
        self,
        report_name: str,
        report_dir: str | Path,
        model_reference: str = "",
    ) -> None:
        """Register a thin report that references the shared model."""
        self._thin_reports.append({
            "name": report_name,
            "dir": str(report_dir),
            "model_ref": model_reference or f"../{self.shared_model_dir.name}",
        })

    def generate_bundle(self, output_dir: str | Path) -> Path:
        """Generate a deployment bundle with shared model and thin reports."""
        out = Path(output_dir) / "bundle"
        out.mkdir(parents=True, exist_ok=True)

        # Copy shared model
        model_out = out / self.shared_model_dir.name
        if self.shared_model_dir.exists():
            import shutil
            if model_out.exists():
                shutil.rmtree(model_out)
            shutil.copytree(self.shared_model_dir, model_out)

        # Generate bundle manifest
        manifest = {
            "shared_model": str(model_out),
            "thin_reports": self._thin_reports,
            "total_reports": len(self._thin_reports),
        }
        manifest_path = out / "bundle_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        logger.info(
            "Bundle generated: 1 shared model + %d thin reports at %s",
            len(self._thin_reports), out,
        )
        return out

    def summary(self) -> dict[str, Any]:
        return {
            "shared_model": str(self.shared_model_dir),
            "thin_reports": len(self._thin_reports),
        }
