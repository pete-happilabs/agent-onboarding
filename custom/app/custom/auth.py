# ============================================================================
# FILE: app/custom/auth.py
# ============================================================================
"""
Auth Handlers - Support multiple authentication types for REST APIs.

Supported auth types:
- bearer: Bearer token in Authorization header
- api_key: API key in custom header
- basic: HTTP Basic authentication
- oauth2: OAuth2 client credentials flow
- none: No authentication
"""
from __future__ import annotations

import os
import base64
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class AuthConfig:
    """Authentication configuration from YAML."""

    type: str  # "bearer", "api_key", "basic", "oauth2", "none"

    # Bearer token
    token_env: Optional[str] = None

    # API Key
    header: Optional[str] = None
    key_env: Optional[str] = None

    # Basic auth
    username_env: Optional[str] = None
    password_env: Optional[str] = None

    # OAuth2
    token_url: Optional[str] = None
    client_id_env: Optional[str] = None
    client_secret_env: Optional[str] = None
    scope: Optional[str] = None

    # Extra headers (for APIs needing multiple auth headers)
    extra_headers: Optional[Dict[str, str]] = None


class AuthHandler:
    """
    Handle authentication for REST API calls.

    Supports bearer tokens, API keys, basic auth, and OAuth2 client credentials.
    """

    def __init__(self, config: AuthConfig):
        self.config = config
        self._oauth_token: Optional[str] = None
        self._oauth_expires: float = 0

    @classmethod
    def from_dict(cls, auth_dict: Dict[str, Any]) -> "AuthHandler":
        """Create AuthHandler from YAML dict."""
        if not auth_dict:
            return cls(AuthConfig(type="none"))

        config = AuthConfig(
            type=auth_dict.get("type", "none"),
            token_env=auth_dict.get("token_env"),
            header=auth_dict.get("header"),
            key_env=auth_dict.get("key_env"),
            username_env=auth_dict.get("username_env"),
            password_env=auth_dict.get("password_env"),
            token_url=auth_dict.get("token_url"),
            client_id_env=auth_dict.get("client_id_env"),
            client_secret_env=auth_dict.get("client_secret_env"),
            scope=auth_dict.get("scope"),
            extra_headers=auth_dict.get("extra_headers"),
        )
        return cls(config)

    def get_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for the request.

        Returns:
            Dict with auth headers to merge into request
        """
        auth_type = self.config.type.lower()
        headers: Dict[str, str] = {}

        if auth_type == "bearer":
            headers.update(self._get_bearer_headers())
        elif auth_type == "api_key":
            headers.update(self._get_api_key_headers())
        elif auth_type == "basic":
            headers.update(self._get_basic_headers())
        elif auth_type == "oauth2":
            headers.update(self._get_oauth2_headers())
        elif auth_type != "none":
            logger.warning(f"Unknown auth type: {auth_type}")

        # Merge extra headers (resolved from env vars)
        headers.update(self._resolve_extra_headers())

        return headers

    def _resolve_extra_headers(self) -> Dict[str, str]:
        """Resolve extra_headers, substituting ${ENV_VAR} patterns."""
        if not self.config.extra_headers:
            return {}

        resolved = {}
        for key, value in self.config.extra_headers.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                env_value = os.getenv(env_var)
                if env_value:
                    resolved[key] = env_value
                else:
                    logger.warning(f"Extra header env var {env_var} not set")
            else:
                resolved[key] = str(value)
        return resolved

    def _get_bearer_headers(self) -> Dict[str, str]:
        """Get Bearer token headers."""
        if not self.config.token_env:
            logger.warning("Bearer auth configured but token_env not set")
            return {}

        token = os.getenv(self.config.token_env)
        if not token:
            logger.warning(f"Bearer token env var {self.config.token_env} not set")
            return {}

        return {"Authorization": f"Bearer {token}"}

    def _get_api_key_headers(self) -> Dict[str, str]:
        """Get API key headers."""
        if not self.config.key_env:
            logger.warning("API key auth configured but key_env not set")
            return {}

        key = os.getenv(self.config.key_env)
        if not key:
            logger.warning(f"API key env var {self.config.key_env} not set")
            return {}

        header_name = self.config.header or "X-API-Key"
        return {header_name: key}

    def _get_basic_headers(self) -> Dict[str, str]:
        """Get Basic auth headers."""
        if not self.config.username_env or not self.config.password_env:
            logger.warning("Basic auth configured but username/password env not set")
            return {}

        username = os.getenv(self.config.username_env, "")
        password = os.getenv(self.config.password_env, "")

        if not username:
            logger.warning(f"Basic auth username env var {self.config.username_env} not set")
            return {}

        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    def _get_oauth2_headers(self) -> Dict[str, str]:
        """Get OAuth2 headers (client credentials flow)."""
        import time

        # Check if we have a valid cached token
        if self._oauth_token and time.time() < self._oauth_expires:
            return {"Authorization": f"Bearer {self._oauth_token}"}

        # Fetch new token
        if not self.config.token_url:
            logger.warning("OAuth2 configured but token_url not set")
            return {}

        client_id = os.getenv(self.config.client_id_env or "", "")
        client_secret = os.getenv(self.config.client_secret_env or "", "")

        if not client_id or not client_secret:
            logger.warning("OAuth2 client_id or client_secret env vars not set")
            return {}

        try:
            data = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }
            if self.config.scope:
                data["scope"] = self.config.scope

            response = httpx.post(self.config.token_url, data=data, timeout=10.0)
            response.raise_for_status()

            token_data = response.json()
            self._oauth_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)
            self._oauth_expires = time.time() + expires_in - 60  # Refresh 1 min early

            logger.debug(f"OAuth2 token obtained, expires in {expires_in}s")
            return {"Authorization": f"Bearer {self._oauth_token}"}

        except Exception as e:
            logger.error(f"Failed to obtain OAuth2 token: {e}")
            return {}
