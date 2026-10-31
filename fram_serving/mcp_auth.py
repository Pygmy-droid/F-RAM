
from __future__ import annotations

import os
import secrets
from typing import Optional

from mcp.server.auth.provider import AccessToken, TokenVerifier


class StaticTokenVerifier(TokenVerifier):
    """Simple bearer-token verifier backed by environment configuration."""

    def __init__(self, env_var: str = "MCP_BEARER") -> None:
        self._env_var = env_var

    def _expected(self) -> Optional[str]:
        token = os.getenv(self._env_var)
        if token:
            return token.strip()
        return None

    async def verify_token(self, token: str) -> AccessToken | None:
        expected = self._expected()
        if not expected:
            # Authentication disabled when no expected token is configured.
            return AccessToken(token=token, client_id="public", scopes=[])

        candidate = token.strip()
        if candidate and secrets.compare_digest(candidate, expected):
            return AccessToken(token=candidate, client_id="static", scopes=[])

        raise PermissionError("invalid bearer token")


token_verifier = StaticTokenVerifier()
