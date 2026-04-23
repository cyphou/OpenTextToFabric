"""Tests for deploy.deployer — Deployer orchestrator."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from deploy.deployer import Deployer, DeploymentError


class TestDeployer(unittest.TestCase):

    def test_init(self):
        d = Deployer(workspace_id="ws1", tenant_id="t", client_id="c")
        self.assertEqual(d.workspace_id, "ws1")
        self.assertEqual(d.tenant_id, "t")

    def test_ensure_workspace_no_id(self):
        d = Deployer()
        mock_client = MagicMock()
        with self.assertRaises(DeploymentError):
            d._ensure_workspace(mock_client)

    def test_ensure_workspace_with_id(self):
        d = Deployer(workspace_id="ws123")
        mock_client = MagicMock()
        mock_client.get_workspace.return_value = {"displayName": "Test"}
        result = d._ensure_workspace(mock_client)
        self.assertEqual(result, "ws123")

    def test_ensure_workspace_create(self):
        d = Deployer(create_workspace=True, workspace_name="New WS")
        mock_client = MagicMock()
        mock_client.create_workspace.return_value = {"id": "new-id"}
        result = d._ensure_workspace(mock_client)
        self.assertEqual(result, "new-id")

    def test_read_definition_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "model.tmdl").write_text("model content")
            (root / "sub").mkdir()
            (root / "sub" / "table.tmdl").write_text("table content")
            (root / ".platform").write_text("skip me")

            result = Deployer._read_definition_files(root)
            parts = result["parts"]
            paths = [p["path"] for p in parts]
            self.assertIn("model.tmdl", paths)
            self.assertIn("sub/table.tmdl", paths)
            self.assertNotIn(".platform", paths)

    def test_deploy_lakehouse_skipped(self):
        d = Deployer(workspace_id="ws1")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = d._deploy_lakehouse(MagicMock(), MagicMock(), "ws1", Path(tmpdir))
            self.assertEqual(result["status"], "skipped")

    def test_deploy_semantic_model_skipped(self):
        d = Deployer(workspace_id="ws1")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = d._deploy_semantic_model(MagicMock(), "ws1", Path(tmpdir))
            self.assertEqual(result["status"], "skipped")

    def test_deploy_report_skipped(self):
        d = Deployer(workspace_id="ws1")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = d._deploy_report(MagicMock(), "ws1", Path(tmpdir))
            self.assertEqual(result["status"], "skipped")

    def test_deploy_full(self):
        # This tests the full deploy flow with mocked dependencies
        mock_client = MagicMock()
        mock_client.get_workspace.return_value = {"displayName": "Test"}

        # Patch at the source modules since deployer uses local imports
        with patch("deploy.auth.TokenProvider", return_value=MagicMock()), \
             patch("deploy.fabric_client.FabricClient", return_value=mock_client), \
             patch("deploy.onelake_client.OneLakeClient", return_value=MagicMock()):
            d = Deployer(workspace_id="ws1")
            with tempfile.TemporaryDirectory() as tmpdir:
                result = d.deploy(tmpdir)
                self.assertEqual(result["workspace_id"], "ws1")
                self.assertTrue(any(s["step"] == "auth" for s in result["steps"]))


if __name__ == "__main__":
    unittest.main()
