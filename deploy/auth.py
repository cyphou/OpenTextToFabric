"""Azure AD authentication — Service Principal + Managed Identity."""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from typing import Any

logger = logging.getLogger(__name__)

_FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
_LOGIN_URL = "https://login.microsoftonline.com"


class AuthError(Exception):
    """Raised when authentication fails."""


class TokenProvider:
    """Provides Azure AD access tokens for Fabric APIs.

    Supports:
    - Service Principal (client_id + client_secret + tenant_id)
    - Managed Identity (no credentials needed on Azure compute)
    - azure-identity library (if installed)
    """

    def __init__(
        self,
        tenant_id: str = "",
        client_id: str = "",
        client_secret: str = "",
        *,
        use_managed_identity: bool = False,
    ) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.use_managed_identity = use_managed_identity
        self._cached_token: str = ""
        self._token_expiry: float = 0

    def get_token(self) -> str:
        """Get a valid access token, refreshing if expired."""
        import time

        if self._cached_token and time.time() < self._token_expiry - 60:
            return self._cached_token

        if self.use_managed_identity:
            token_data = self._acquire_managed_identity()
        elif self.client_id and self.client_secret:
            token_data = self._acquire_service_principal()
        else:
            token_data = self._acquire_azure_identity()

        self._cached_token = token_data["access_token"]
        self._token_expiry = time.time() + token_data.get("expires_in", 3600)
        return self._cached_token

    def _acquire_service_principal(self) -> dict[str, Any]:
        """Acquire token via OAuth2 client credentials flow."""
        url = f"{_LOGIN_URL}/{self.tenant_id}/oauth2/v2.0/token"
        data = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": _FABRIC_SCOPE,
        }).encode()

        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            raise AuthError(f"Service principal auth failed ({e.code}): {body}") from e

    def _acquire_managed_identity(self) -> dict[str, Any]:
        """Acquire token via Azure Managed Identity endpoint."""
        url = (
            "http://169.254.169.254/metadata/identity/oauth2/token"
            f"?api-version=2019-08-01&resource={urllib.parse.quote(_FABRIC_SCOPE)}"
        )
        req = urllib.request.Request(url)
        req.add_header("Metadata", "true")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except urllib.error.URLError as e:
            raise AuthError(f"Managed identity not available: {e}") from e

    @staticmethod
    def _acquire_azure_identity() -> dict[str, Any]:
        """Acquire token via azure-identity library (if installed)."""
        try:
            from azure.identity import DefaultAzureCredential  # type: ignore[import]
        except ImportError:
            raise AuthError(
                "No credentials provided and azure-identity is not installed. "
                "Provide --tenant-id + --client-id + --client-secret, "
                "or pip install azure-identity"
            )

        credential = DefaultAzureCredential()
        token = credential.get_token(_FABRIC_SCOPE)
        return {"access_token": token.token, "expires_in": 3600}
