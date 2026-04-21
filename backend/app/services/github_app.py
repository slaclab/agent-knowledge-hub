from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import settings


class GitHubAppClient:
    """Generates and caches GitHub App installation tokens.

    JWT constraints per GitHub docs:
      - iat = now() - 60s  (clock skew buffer)
      - exp = now() + 600s  (max 10 min)
      - algorithm: RS256
      - iss: App ID

    Installation token is cached until expires_at - 60s.
    asyncio.Lock prevents thundering-herd on concurrent token refresh.
    """

    def __init__(self):
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        # Lazy creation inside the running event loop
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _is_configured(self) -> bool:
        return bool(settings.github_app_id and settings.github_app_private_key)

    def _is_token_valid(self) -> bool:
        if not self._token or not self._token_expires_at:
            return False
        return datetime.now(timezone.utc) < self._token_expires_at

    async def get_token(self) -> Optional[str]:
        if not self._is_configured():
            return None
        if self._is_token_valid():
            return self._token
        async with self._get_lock():
            # Double-check under lock
            if self._is_token_valid():
                return self._token
            return await self._refresh_token()

    async def invalidate(self) -> None:
        self._token = None
        self._token_expires_at = None

    async def _refresh_token(self) -> Optional[str]:
        try:
            import jwt
        except ImportError:
            return None

        now = int(datetime.now(timezone.utc).timestamp())
        payload = {
            "iat": now - 60,
            "exp": now + 600,
            "iss": settings.github_app_id,
        }
        try:
            app_jwt = jwt.encode(payload, settings.github_app_private_key, algorithm="RS256")
        except Exception:
            return None

        async with httpx.AsyncClient(timeout=10) as client:
            installations_resp = await client.get(
                "https://api.github.com/app/installations",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            if installations_resp.status_code != 200:
                return None

            installations = installations_resp.json()
            if not installations:
                return None
            installation_id = installations[0]["id"]

            token_resp = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            if token_resp.status_code != 201:
                return None

            token_data = token_resp.json()
            self._token = token_data["token"]
            # Use expires_at from response minus 60s safety margin
            raw_expires = token_data.get("expires_at", "")
            try:
                expires = datetime.fromisoformat(raw_expires.replace("Z", "+00:00"))
                from datetime import timedelta
                self._token_expires_at = expires - timedelta(seconds=60)
            except (ValueError, AttributeError):
                from datetime import timedelta
                self._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

            return self._token


github_app_client = GitHubAppClient()
