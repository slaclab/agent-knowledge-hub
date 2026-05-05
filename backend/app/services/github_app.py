from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class GitHubAppClient:
    """Generates and caches GitHub App installation tokens, one per org.

    JWT constraints per GitHub docs:
      - iat = now() - 60s  (clock skew buffer)
      - exp = now() + 600s  (max 10 min)
      - algorithm: RS256
      - iss: App ID

    Installation tokens are cached per org slug until expires_at - 60s.
    asyncio.Lock prevents thundering-herd on concurrent token refresh.
    """

    def __init__(self):
        # keyed by org login (lowercase); value is (token, expires_at)
        self._tokens: Dict[str, tuple[str, datetime]] = {}
        self._lock: Optional[asyncio.Lock] = None
        # Cache of installation_id → org login, populated on first fetch
        self._installations: Optional[list[dict]] = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _is_configured(self) -> bool:
        return bool(settings.github_app_id and settings.github_app_private_key)

    def _token_valid(self, org: str) -> bool:
        entry = self._tokens.get(org)
        if not entry:
            return False
        _, expires_at = entry
        return datetime.now(timezone.utc) < expires_at

    async def get_token(self, owner: Optional[str] = None) -> Optional[str]:
        """Return an installation token scoped to *owner*'s org.

        If *owner* is None or no matching installation is found, falls back to
        the first installation (preserves existing behaviour for single-org setups).
        """
        if not self._is_configured():
            return None

        org_key = (owner or "").lower()

        if self._token_valid(org_key):
            return self._tokens[org_key][0]

        async with self._get_lock():
            if self._token_valid(org_key):
                return self._tokens[org_key][0]
            return await self._refresh_token(owner)

    async def invalidate(self, owner: Optional[str] = None) -> None:
        org_key = (owner or "").lower()
        self._tokens.pop(org_key, None)
        # Also clear the generic fallback key ""
        self._tokens.pop("", None)
        self._installations = None

    def _make_jwt(self) -> Optional[str]:
        try:
            import jwt
        except ImportError:
            logger.error("PyJWT not installed — cannot generate GitHub App token")
            return None

        now = int(datetime.now(timezone.utc).timestamp())
        payload = {
            "iat": now - 60,
            "exp": now + 600,
            "iss": settings.github_app_id,
        }
        try:
            return jwt.encode(payload, settings.github_app_private_key, algorithm="RS256")
        except Exception as e:
            logger.error("Failed to sign GitHub App JWT: %s", e)
            return None

    async def _fetch_installations(self, app_jwt: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.github.com/app/installations",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            if resp.status_code != 200:
                logger.error(
                    "GitHub App installations request failed: %s %s",
                    resp.status_code, resp.text[:200],
                )
                return []
            return resp.json()

    async def _get_installation_token(self, app_jwt: str, installation_id: int) -> Optional[tuple[str, datetime]]:
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            if token_resp.status_code != 201:
                logger.error(
                    "GitHub App access token request failed: %s %s",
                    token_resp.status_code, token_resp.text[:200],
                )
                return None

            data = token_resp.json()
            token = data["token"]
            raw_expires = data.get("expires_at", "")
            try:
                expires = datetime.fromisoformat(raw_expires.replace("Z", "+00:00"))
                expires_at = expires - timedelta(seconds=60)
            except (ValueError, AttributeError):
                expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            return token, expires_at

    async def _refresh_token(self, owner: Optional[str]) -> Optional[str]:
        app_jwt = self._make_jwt()
        if not app_jwt:
            return None

        installations = await self._fetch_installations(app_jwt)
        if not installations:
            logger.error(
                "GitHub App (id=%s) has no installations — install it on the target org",
                settings.github_app_id,
            )
            return None

        self._installations = installations

        # Find the installation that matches the requested owner.
        # If owner is specified but not found, return None so the caller can
        # fall back to a PAT rather than using a token scoped to the wrong org.
        target = None
        if owner:
            for inst in installations:
                login = inst.get("account", {}).get("login", "")
                if login.lower() == owner.lower():
                    target = inst
                    break
            if target is None:
                logger.warning(
                    "GitHub App has no installation for org=%s; falling back to PAT", owner
                )
                return None
        else:
            target = installations[0]

        installation_id = target.get("installation_id") or target["id"]
        org_login = target.get("account", {}).get("login", owner or "").lower()

        result = await self._get_installation_token(app_jwt, installation_id)
        if result is None:
            return None

        token, expires_at = result
        org_key = (owner or "").lower()
        self._tokens[org_key] = (token, expires_at)
        # Cache under the actual org login too (in case called with org login directly)
        if org_login and org_login != org_key:
            self._tokens[org_login] = (token, expires_at)

        logger.info(
            "GitHub App installation token refreshed (installation %s, org=%s)",
            installation_id, org_login,
        )
        return token


github_app_client = GitHubAppClient()
