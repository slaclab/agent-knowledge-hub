from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from pydantic import BaseModel

from app.config import settings
from app.models.skill import VisibilityEnum


class GitHubSnapshot(BaseModel):
    name: str
    description: Optional[str] = None
    stars: int = 0
    last_commit_at: Optional[datetime] = None
    license: Optional[str] = None
    readme_html: Optional[str] = None
    fetched_at: datetime
    visibility: VisibilityEnum = VisibilityEnum.public
    forked_from_url: Optional[str] = None


_REPO_RE = re.compile(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")


def _normalize_github_url(url: Optional[str]) -> Optional[str]:
    """Normalize a GitHub repo URL: https, no trailing slash, no .git, lowercase owner/repo."""
    if not url:
        return None
    m = _REPO_RE.match(url.strip())
    if not m:
        return url
    owner, repo = m.group(1).lower(), m.group(2).lower()
    return f"https://github.com/{owner}/{repo}"


class GitHubFetchError(Exception):
    pass


class GitHubFetcher:
    def __init__(self):
        self._base = settings.github_api_url

    def _make_headers(self, token: Optional[str] = None) -> dict:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def fetch(self, repo_url: str, force_app_token: bool = False) -> GitHubSnapshot:
        m = _REPO_RE.match(repo_url.strip())
        if not m:
            raise GitHubFetchError(f"Not a valid public GitHub repo URL: {repo_url}")
        owner, repo = m.group(1), m.group(2)

        from app.services.github_app import github_app_client

        # Determine auth strategy
        app_token = await github_app_client.get_token()

        if force_app_token and app_token:
            # Skip fallback chain for known-internal skills
            return await self._fetch_with_token(owner, repo, app_token, expected_internal=True)

        # Fallback chain: try unauthenticated, then PAT, then App token
        # For known private orgs, skip straight to app token when available
        private_orgs = {o.strip().lower() for o in settings.github_private_orgs.split(",") if o.strip()}
        if owner.lower() in private_orgs and app_token:
            return await self._fetch_with_token(owner, repo, app_token, expected_internal=True)

        # Try unauthenticated (or PAT if set — PAT is for rate-limit relief on public repos)
        pat = settings.github_token
        data, status_code = await self._try_fetch_repo(owner, repo, pat)

        if status_code == 200:
            return await self._build_snapshot(owner, repo, data, pat)

        if status_code == 404:
            # Retry with App token if configured
            if app_token:
                data2, status_code2 = await self._try_fetch_repo(owner, repo, app_token)
                if status_code2 == 200:
                    return await self._build_snapshot(owner, repo, data2, app_token)
                raise GitHubFetchError(
                    "This repo couldn't be found. Check the URL. "
                    "If this is a private repo outside the slaclab GitHub organization, "
                    "private repos can only be auto-fetched for slaclab org repos."
                )
            raise GitHubFetchError(
                "This repo couldn't be found. Check the URL. "
                "If this is a private repo outside the slaclab GitHub organization, "
                "it can't be auto-fetched — you can still submit with a manual description."
            )

        raise GitHubFetchError(f"GitHub API error: {status_code}")

    async def _try_fetch_repo(self, owner: str, repo: str, token: Optional[str]) -> tuple[dict, int]:
        headers = self._make_headers(token)
        async with httpx.AsyncClient(headers=headers, timeout=10) as client:
            resp = await client.get(f"{self._base}/repos/{owner}/{repo}")
            if resp.status_code == 401 and token:
                # Invalidate cached app token if it was the app token
                from app.services.github_app import github_app_client
                await github_app_client.invalidate()
                resp = await client.get(f"{self._base}/repos/{owner}/{repo}")
            if resp.status_code == 200:
                return resp.json(), 200
            return {}, resp.status_code

    async def _build_snapshot(
        self, owner: str, repo: str, data: dict, token: Optional[str]
    ) -> GitHubSnapshot:
        headers = self._make_headers(token)
        readme_html: Optional[str] = None
        async with httpx.AsyncClient(timeout=10) as client:
            readme_resp = await client.get(
                f"{self._base}/repos/{owner}/{repo}/readme",
                headers={**headers, "Accept": "application/vnd.github.html+json"},
            )
            if readme_resp.status_code == 200:
                try:
                    readme_html = readme_resp.text
                except Exception:
                    pass

        last_commit_at: Optional[datetime] = None
        pushed = data.get("pushed_at")
        if pushed:
            try:
                last_commit_at = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
            except ValueError:
                pass

        license_name: Optional[str] = None
        lic = data.get("license")
        if lic:
            license_name = lic.get("spdx_id") or lic.get("name")

        # Visibility is determined by the GitHub API private field (ADR-P04)
        visibility = VisibilityEnum.internal if data.get("private") else VisibilityEnum.public

        forked_from_url: Optional[str] = None
        if data.get("fork"):
            parent = data.get("parent", {})
            raw_parent_url = parent.get("html_url")
            forked_from_url = _normalize_github_url(raw_parent_url)

        return GitHubSnapshot(
            name=data["name"],
            description=data.get("description"),
            stars=data.get("stargazers_count", 0),
            last_commit_at=last_commit_at,
            license=license_name,
            readme_html=readme_html,
            fetched_at=datetime.now(timezone.utc),
            visibility=visibility,
            forked_from_url=forked_from_url,
        )

    async def _fetch_with_token(
        self, owner: str, repo: str, token: str, expected_internal: bool = False
    ) -> GitHubSnapshot:
        data, status_code = await self._try_fetch_repo(owner, repo, token)
        if status_code != 200:
            raise GitHubFetchError(
                "This repo couldn't be found. Check the URL. "
                "If this is a private repo outside the slaclab GitHub organization, "
                "private repos can only be auto-fetched for slaclab org repos."
            )
        return await self._build_snapshot(owner, repo, data, token)


github_fetcher = GitHubFetcher()
