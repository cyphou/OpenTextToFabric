"""Tests for deploy.multi_tenant — multi-tenant deployment and bundle deployer."""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from deploy.multi_tenant import (
    BundleDeployer,
    MultiTenantDeployer,
    TenantConfig,
)


class TestTenantConfig(unittest.TestCase):
    def test_creation(self):
        tc = TenantConfig(
            tenant_id="t1",
            workspace_name="Acme Analytics",
            workspace_id="ws1",
            substitutions={"{{DB}}": "acme_db"},
        )
        self.assertEqual(tc.tenant_id, "t1")
        self.assertEqual(tc.workspace_name, "Acme Analytics")
        self.assertEqual(tc.workspace_id, "ws1")
        self.assertEqual(tc.substitutions["{{DB}}"], "acme_db")

    def test_default_fields(self):
        tc = TenantConfig(tenant_id="t2", workspace_name="Beta")
        self.assertEqual(tc.workspace_id, "")
        self.assertEqual(tc.substitutions, {})
        self.assertEqual(tc.rls_roles, [])
        self.assertEqual(tc.connection_overrides, {})

    def test_to_dict(self):
        tc = TenantConfig(tenant_id="t3", workspace_name="Gamma", workspace_id="ws3")
        d = tc.to_dict()
        self.assertEqual(d["tenant_id"], "t3")
        self.assertEqual(d["workspace_name"], "Gamma")


class TestMultiTenantDeployer(unittest.TestCase):
    def test_load_tenants_from_json(self):
        with tempfile.TemporaryDirectory() as td:
            config_path = os.path.join(td, "tenants.json")
            with open(config_path, "w") as f:
                json.dump({
                    "tenants": [
                        {"tenant_id": "t1", "workspace_name": "A"},
                        {"tenant_id": "t2", "workspace_name": "B", "substitutions": {"{{K}}": "V"}},
                    ]
                }, f)

            template_dir = os.path.join(td, "template")
            os.makedirs(template_dir)
            deployer = MultiTenantDeployer(template_dir)
            count = deployer.load_tenants(config_path)
            self.assertEqual(count, 2)

    def test_prepare_tenant_output(self):
        with tempfile.TemporaryDirectory() as td:
            # Create template directory with a tmdl file containing placeholder
            template_dir = os.path.join(td, "template")
            os.makedirs(template_dir)
            tmdl = os.path.join(template_dir, "model.tmdl")
            with open(tmdl, "w") as f:
                f.write('Source = Sql.Database("{{DB_SERVER}}", "{{DB_NAME}}")')

            deployer = MultiTenantDeployer(template_dir)
            tenant = TenantConfig(
                tenant_id="t1",
                workspace_name="Test",
                substitutions={"{{DB_SERVER}}": "prod.sql.com", "{{DB_NAME}}": "sales_db"},
            )
            out_dir = os.path.join(td, "output")
            result = deployer.prepare_tenant_output(tenant, out_dir)
            out_file = result / "model.tmdl"
            self.assertTrue(out_file.exists())
            content = out_file.read_text()
            self.assertIn("prod.sql.com", content)
            self.assertIn("sales_db", content)
            self.assertNotIn("{{DB_SERVER}}", content)

    def test_add_tenant(self):
        with tempfile.TemporaryDirectory() as td:
            deployer = MultiTenantDeployer(td)
            deployer.add_tenant(TenantConfig(tenant_id="t1", workspace_name="A"))
            deployer.add_tenant(TenantConfig(tenant_id="t2", workspace_name="B"))
            self.assertEqual(len(deployer._tenants), 2)

    def test_deploy_all_prepared(self):
        with tempfile.TemporaryDirectory() as td:
            template_dir = os.path.join(td, "template")
            os.makedirs(template_dir)
            with open(os.path.join(template_dir, "data.json"), "w") as f:
                f.write("{}")

            deployer = MultiTenantDeployer(template_dir)
            deployer.add_tenant(TenantConfig(tenant_id="t1", workspace_name="A"))
            deployer.add_tenant(TenantConfig(tenant_id="t2", workspace_name="B"))

            out_dir = os.path.join(td, "output")
            results = deployer.deploy_all(out_dir)
            self.assertEqual(len(results), 2)
            self.assertTrue(all(r["status"] == "prepared" for r in results))

    def test_summary(self):
        with tempfile.TemporaryDirectory() as td:
            deployer = MultiTenantDeployer(td)
            s = deployer.summary()
            self.assertEqual(s["total_tenants"], 0)


class TestBundleDeployer(unittest.TestCase):
    def test_init_and_add_reports(self):
        with tempfile.TemporaryDirectory() as td:
            model_dir = os.path.join(td, "SharedModel")
            os.makedirs(model_dir)
            bd = BundleDeployer(model_dir)
            bd.add_thin_report("Report1", "/reports/r1")
            bd.add_thin_report("Report2", "/reports/r2")
            s = bd.summary()
            self.assertEqual(s["thin_reports"], 2)

    def test_generate_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            model_dir = os.path.join(td, "SharedModel")
            os.makedirs(model_dir)
            with open(os.path.join(model_dir, "model.tmdl"), "w") as f:
                f.write("table T\n")

            bd = BundleDeployer(model_dir)
            bd.add_thin_report("R1", "/path/to/r1")
            out = bd.generate_bundle(os.path.join(td, "output"))
            self.assertTrue(out.exists())
            manifest = out / "bundle_manifest.json"
            self.assertTrue(manifest.exists())
            data = json.loads(manifest.read_text())
            self.assertEqual(data["total_reports"], 1)


if __name__ == "__main__":
    unittest.main()
