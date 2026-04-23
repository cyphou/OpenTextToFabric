"""Configuration model for the migration tool."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """OpenText server connection configuration."""

    url: str = ""
    username: str = ""
    password: str = ""  # resolved from env var at runtime, never persisted
    auth_type: str = "basic"  # basic, token, oauth
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    page_size: int = 100
    verify_ssl: bool = True

    def resolve_password(self, env_var: str | None = None) -> None:
        """Resolve password from environment variable."""
        if env_var:
            self.password = os.environ.get(env_var, "")
            if not self.password:
                logger.warning("Password environment variable '%s' is empty or not set", env_var)


@dataclass
class ScopeConfig:
    """Content scope configuration — what to migrate."""

    root_path: str = "/"
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    max_depth: int = -1  # -1 = unlimited
    include_versions: bool = True
    include_renditions: bool = True
    include_workflows: bool = False


@dataclass
class OutputConfig:
    """Output configuration."""

    output_dir: str = "./output"
    output_format: str = "both"  # fabric, pbip, both
    overwrite: bool = False
    json_indent: int = 2


@dataclass
class MigrationConfig:
    """Top-level migration configuration."""

    source_type: str = "content-server"
    server: ServerConfig = field(default_factory=ServerConfig)
    scope: ScopeConfig = field(default_factory=ScopeConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    input_path: str = ""
    assess_only: bool = False
    batch: bool = False
    deploy: bool = False
    workspace_id: str = ""
    tenant_id: str = ""

    @classmethod
    def from_args(cls, args: Any) -> MigrationConfig:
        """Create configuration from parsed CLI arguments."""
        config = cls()
        config.source_type = args.source_type
        config.server.url = args.server_url or ""
        config.server.username = args.username or ""
        config.server.resolve_password(args.password_env)
        config.scope.root_path = args.scope or "/"
        config.output.output_dir = args.output_dir
        config.output.output_format = args.output_format
        config.input_path = getattr(args, "input", "") or ""
        config.assess_only = args.assess_only
        config.batch = args.batch
        config.deploy = args.deploy
        config.workspace_id = args.workspace_id or ""
        config.tenant_id = args.tenant_id or ""
        return config

    @classmethod
    def from_file(cls, path: str | Path) -> MigrationConfig:
        """Load configuration from a JSON file."""
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)

        config = cls()
        if "source_type" in data:
            config.source_type = data["source_type"]
        if "server" in data:
            srv = data["server"]
            config.server.url = srv.get("url", "")
            config.server.username = srv.get("username", "")
            config.server.auth_type = srv.get("auth_type", "basic")
            config.server.timeout = srv.get("timeout", 30)
            config.server.max_retries = srv.get("max_retries", 3)
            config.server.page_size = srv.get("page_size", 100)
            config.server.verify_ssl = srv.get("verify_ssl", True)
            if "password_env" in srv:
                config.server.resolve_password(srv["password_env"])
        if "scope" in data:
            sc = data["scope"]
            config.scope.root_path = sc.get("root_path", "/")
            config.scope.include_patterns = sc.get("include_patterns", [])
            config.scope.exclude_patterns = sc.get("exclude_patterns", [])
            config.scope.max_depth = sc.get("max_depth", -1)
            config.scope.include_versions = sc.get("include_versions", True)
            config.scope.include_renditions = sc.get("include_renditions", True)
        if "output" in data:
            out = data["output"]
            config.output.output_dir = out.get("output_dir", "./output")
            config.output.output_format = out.get("output_format", "both")
        return config

    def validate(self) -> list[str]:
        """Validate configuration, return list of errors."""
        errors: list[str] = []
        if self.source_type in ("content-server", "documentum"):
            if not self.server.url:
                errors.append("Server URL is required for source type '%s'" % self.source_type)
        if self.source_type == "birt":
            if not self.input_path:
                errors.append("Input path (--input) is required for BIRT source type")
        if self.deploy:
            if not self.workspace_id:
                errors.append("Workspace ID (--workspace-id) is required for deployment")
            if not self.tenant_id:
                errors.append("Tenant ID (--tenant-id) is required for deployment")
        return errors
