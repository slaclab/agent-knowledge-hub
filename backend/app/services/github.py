from __future__ import annotations

import base64
import re
from datetime import datetime
from typing import Optional

import httpx
from pydantic import BaseModel

from app.config import settings


class GitHubSnapshot(BaseModel):
    name: str
    description: Optional[str] = None
    stars: int = 0
    last_commit_at: Optional[datetime] = None
    license: Optional[str] = None
    readme_html: Optional[str] = None
    fetched_at: datetime


_REPO_RE = re.compile(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")


class GitHubFetchError(Exception):
    pass


class GitHubFetcher:
    def __init__(self):
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        self._headers = headers
        self._base = settings.github_api_url

    async def fetch(self, repo_url: str) -> GitHubSnapshot:
        m = _REPO_RE.match(repo_url.strip())
        if not m:
            raise GitHubFetchError(f"Not a valid public GitHub repo URL: {repo_url}")
        owner, repo = m.group(1), m.group(2)

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            repo_resp = await client.get(f"{self._base}/repos/{owner}/{repo}")
            if repo_resp.status_code == 404:
                raise GitHubFetchError("Repo not found or is private")
            if repo_resp.status_code != 200:
                raise GitHubFetchError(f"GitHub API error: {repo_resp.status_code}")
            data = repo_resp.json()

            readme_html: Optional[str] = None
            readme_resp = await client.get(
                f"{self._base}/repos/{owner}/{repo}/readme",
                headers={**self._headers, "Accept": "application/vnd.github.html+json"},
            )
            if readme_resp.status_code == 200:
                try:
                    # GitHub returns base64 content when Accept is default; html when html Accept
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

        return GitHubSnapshot(
            name=data["name"],
            description=data.get("description"),
            stars=data.get("stargazers_count", 0),
            last_commit_at=last_commit_at,
            license=license_name,
            readme_html=readme_html,
            fetched_at=datetime.utcnow(),
        )


github_fetcher = GitHubFetcher()
