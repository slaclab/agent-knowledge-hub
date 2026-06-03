from __future__ import annotations

import asyncio
import base64
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

import httpx
import logging
from cachetools import TTLCache
from pydantic import BaseModel

from app.config import settings
from app.models.skill import VisibilityEnum
from app.services.scanner import (  # noqa: E402
    FileManifestEntry,
    GitHubRef,
    LocalRef,
    RawScanResult,
    SourceRef,
    SourceScanner,
    _MAX_MANIFEST,
    _TEXT_EXTENSIONS,
    scanner_registry,
)

# Re-export for backward compatibility — existing imports from github.py still work
__all__ = [
    "GitHubRef",
    "RawScanResult",
    "SourceRef",
    "build_file_manifest",
]


def build_file_manifest(
    contents_data: List[Dict[str, Any]],
) -> tuple[List[FileManifestEntry], bool]:
    """Build a FileManifest from a GitHub Contents API directory listing.

    Returns (entries, truncated). Only the first _MAX_MANIFEST items are kept.
    Uses item["name"] (basename) as the path, not item["path"] (repo-root-relative).
    """
    entries: List[FileManifestEntry] = []
    truncated = False
    for item in contents_data:
        if len(entries) >= _MAX_MANIFEST:
            truncated = True
            break
        name = item.get("name", "")
        item_type = item.get("type", "file")
        size = item.get("size") or 0
        is_dir = item_type == "dir"
        if is_dir:
            entries.append(FileManifestEntry(path=name, size_bytes=0, is_text=False, is_dir=True))
        else:
            ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
            is_text = ext in _TEXT_EXTENSIONS
            entries.append(FileManifestEntry(path=name, size_bytes=int(size), is_text=is_text, is_dir=False))
    return entries, truncated

logger = logging.getLogger(__name__)


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
    # version pinning (#017)
    head_sha: Optional[str] = None   # HEAD commit SHA of the default branch
    head_tag: Optional[str] = None   # tag name at head_sha, if any (display only)


_REPO_RE = re.compile(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")
# Matches any github.com URL and captures owner/repo from the first two path segments
_REPO_PREFIX_RE = re.compile(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:[/?#]|$)")


def _normalize_github_url(url: Optional[str]) -> Optional[str]:
    """Normalize a GitHub repo URL: https, no trailing slash, no .git, lowercase owner/repo."""
    if not url:
        return None
    m = _REPO_RE.match(url.strip())
    if not m:
        return url
    owner, repo = m.group(1).lower(), m.group(2).lower()
    return f"https://github.com/{owner}/{repo}"


def extract_repo_root_url(url: str) -> Optional[str]:
    """Extract and normalize the repo root from any github.com URL (including subdirectory URLs)."""
    m = _REPO_PREFIX_RE.match(url.strip())
    if not m:
        return None
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
        m = _REPO_PREFIX_RE.match(repo_url.strip())
        if not m:
            raise GitHubFetchError(f"Not a valid public GitHub repo URL: {repo_url}")
        owner, repo = m.group(1), m.group(2)

        from app.services.github_app import github_app_client

        # Determine auth strategy — request token scoped to owner's org
        app_token = await github_app_client.get_token(owner=owner)

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
                from app.services.github_app import github_app_client
                await github_app_client.invalidate(owner=owner)
                resp = await client.get(f"{self._base}/repos/{owner}/{repo}")
            if resp.status_code == 200:
                return resp.json(), 200
            return {}, resp.status_code

    async def _build_snapshot(
        self, owner: str, repo: str, data: dict, token: Optional[str]
    ) -> GitHubSnapshot:
        headers = self._make_headers(token)
        default_branch = data.get("default_branch", "main")

        readme_html: Optional[str] = None
        head_sha: Optional[str] = None
        head_tag: Optional[str] = None

        async with httpx.AsyncClient(timeout=10) as client:
            # Fetch README and HEAD SHA in parallel
            readme_task = client.get(
                f"{self._base}/repos/{owner}/{repo}/readme",
                headers={**headers, "Accept": "application/vnd.github.html+json"},
            )
            sha_task = client.get(
                f"{self._base}/repos/{owner}/{repo}/git/ref/heads/{default_branch}",
                headers=headers,
            )
            readme_resp, sha_resp = await asyncio.gather(readme_task, sha_task)

            if readme_resp.status_code == 200:
                try:
                    readme_html = readme_resp.text
                except Exception:
                    pass

            if sha_resp.status_code == 200:
                try:
                    head_sha = sha_resp.json()["object"]["sha"]
                except Exception:
                    pass

            # Tag lookup: find the first tag pointing to head_sha (best-effort)
            if head_sha:
                try:
                    tags_resp = await client.get(
                        f"{self._base}/repos/{owner}/{repo}/tags?per_page=10",
                        headers=headers,
                    )
                    if tags_resp.status_code == 200:
                        for tag in tags_resp.json():
                            if tag.get("commit", {}).get("sha") == head_sha:
                                head_tag = tag.get("name")
                                break
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

        # GHEC "internal" repos return private=false but visibility="internal"
        _vis = data.get("visibility", "public")
        visibility = VisibilityEnum.internal if (_vis == "internal" or data.get("private")) else VisibilityEnum.public

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
            head_sha=head_sha,
            head_tag=head_tag,
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


# GitHubRef is imported from scanner.py above.


# ---------------------------------------------------------------------------
# GitHubURLParser
# ---------------------------------------------------------------------------

_TREE_RE = re.compile(
    r"https?://github\.com/([^/]+)/([^/]+)/tree/([^/]+)(?:/(.+?))?/?$"
)
_BLOB_RE = re.compile(
    r"https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)"
)
_ROOT_RE = re.compile(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?[/?#]?$")


class GitHubURLParser:
    """Parse any GitHub URL into owner/repo/branch/path components.

    Limitation: branch names containing '/' are not supported — the first
    path segment after /tree/ is always treated as the branch name.
    """

    def parse(self, url: str) -> GitHubRef:
        url = url.strip()
        # Strip query params and fragments for matching
        clean = re.split(r"[?#]", url)[0].rstrip("/")
        # Remove .git suffix
        if clean.endswith(".git"):
            clean = clean[:-4]

        if "github.com" not in clean.lower():
            raise ValueError(f"Not a GitHub URL: {url}")

        m = _TREE_RE.match(url.strip())
        if m:
            owner = m.group(1).lower()
            repo = m.group(2).lower()
            branch = m.group(3)
            raw_path = m.group(4) or ""
            path = "/" + unquote(raw_path) if raw_path else "/"
            return GitHubRef(owner=owner, repo=repo, branch=branch, path=path)

        mb = _BLOB_RE.match(url.strip())
        if mb:
            owner = mb.group(1).lower()
            repo = mb.group(2).lower()
            branch = mb.group(3)
            file_path = unquote(mb.group(4))
            # Point at the parent directory so the scanner fetches the directory listing
            parent = file_path.rsplit("/", 1)[0] if "/" in file_path else ""
            path = "/" + parent if parent else "/"
            return GitHubRef(owner=owner, repo=repo, branch=branch, path=path)

        m2 = _ROOT_RE.match(clean)
        if m2:
            owner = m2.group(1).lower()
            repo = m2.group(2).lower()
            return GitHubRef(owner=owner, repo=repo, branch=None, path="/")

        raise ValueError(f"Could not parse GitHub URL: {url}")


github_url_parser = GitHubURLParser()


# RawScanResult is imported from scanner.py above.

_SKILL_FILES = {"SKILL.md", "skill.md", "CLAUDE.md", "README.md", "package.json", "pyproject.toml", "plugin.json"}


# ---------------------------------------------------------------------------
# SkillScanSnapshot — richer than GitHubSnapshot, returned by /api/github-scan
# ---------------------------------------------------------------------------

class SkillScanSnapshot(BaseModel):
    ref: SourceRef
    name: Optional[str] = None
    description: Optional[str] = None
    compatible_platforms: List[str] = []
    version: Optional[str] = None
    license: Optional[str] = None
    readme_html: Optional[str] = None
    stars: int = 0
    last_commit_at: Optional[datetime] = None
    visibility: VisibilityEnum = VisibilityEnum.public
    forked_from_url: Optional[str] = None
    fetched_at: datetime
    no_skill_files: bool = False
    existing_slug: Optional[str] = None  # set if (repo_url, skill_path) already registered
    # plugin.json fields
    agent_count: int = 0
    agent_names: List[str] = []
    has_mcp_server: bool = False
    has_scripts: bool = False
    plugin_author: Optional[str] = None
    keywords: List[str] = []
    # file manifest
    file_manifest: List[FileManifestEntry] = []
    manifest_truncated: bool = False


# ---------------------------------------------------------------------------
# GitHubScanner
# ---------------------------------------------------------------------------

_scan_cache: TTLCache = TTLCache(maxsize=256, ttl=60)


class GitHubScanner(SourceScanner):
    def __init__(self):
        self._base = settings.github_api_url

    def _make_headers(self, token: Optional[str] = None) -> dict:
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        return h

    async def _get_token(self, owner: Optional[str] = None) -> Optional[str]:
        from app.services.github_app import github_app_client
        return await github_app_client.get_token(owner=owner)

    async def _best_token(self, owner: str) -> Optional[str]:
        pat = settings.github_token
        private_orgs = {o.strip().lower() for o in settings.github_private_orgs.split(",") if o.strip()}
        if owner.lower() in private_orgs:
            app_token = await self._get_token(owner=owner)
            chosen = app_token or pat
            logger.debug(
                "[TOKEN] owner=%s private_org=True app_token=%s pat=%s → using=%s",
                owner, "set" if app_token else "None", "set" if pat else "None",
                "app_token" if app_token else ("pat" if pat else "None"),
            )
            return chosen
        logger.debug(
            "[TOKEN] owner=%s private_org=False pat=%s → using=pat",
            owner, "set" if pat else "None",
        )
        return pat

    async def _api_get(self, path: str, token: Optional[str], accept: str = "application/vnd.github+json", owner: Optional[str] = None) -> tuple[Any, int]:
        headers = self._make_headers(token)
        headers["Accept"] = accept
        url = f"{self._base}{path}"
        logger.debug("[API] GET %s token=%s", path, "set" if token else "None")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 401 and token:
                logger.warning("[API] 401 on %s — invalidating app token and retrying", path)
                from app.services.github_app import github_app_client
                await github_app_client.invalidate(owner=owner)
                resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                logger.debug("[API] GET %s → 200 OK", path)
                return resp.json(), 200
            logger.warning("[API] GET %s → %d (token=%s)", path, resp.status_code, "set" if token else "None")
            return None, resp.status_code

    async def scan(self, ref: GitHubRef, cache_key: Optional[str] = None) -> RawScanResult:
        if cache_key and cache_key in _scan_cache:
            logger.debug("[SCAN] cache hit key=%s", cache_key)
            return _scan_cache[cache_key]

        token = await self._best_token(ref.owner)
        owner, repo = ref.owner, ref.repo
        branch = ref.branch
        path = ref.path.lstrip("/")

        logger.info("[SCAN] start owner=%s repo=%s path=%r branch=%r cache_key=%s",
                    owner, repo, path, branch, cache_key)

        # Parallel: repo metadata + directory contents
        repo_task = self._api_get(f"/repos/{owner}/{repo}", token, owner=owner)
        dir_path = path if path else ""
        contents_url = f"/repos/{owner}/{repo}/contents/{dir_path}"
        if branch:
            contents_url += f"?ref={branch}"
        contents_task = self._api_get(contents_url, token, owner=owner)

        repo_data, repo_status = await repo_task
        contents_data, contents_status = await contents_task

        if repo_status == 403:
            raise GitHubFetchError("GitHub rate limit reached. Wait a moment and try again.")
        if repo_status == 404:
            raise GitHubFetchError(
                "Repo not found. Check the URL — if this is a private or internal repo, "
                "the catalog's GitHub App may need to be installed on that org."
            )
        if repo_status != 200:
            raise GitHubFetchError(f"GitHub API error: {repo_status}")
        if contents_status == 403:
            raise GitHubFetchError("GitHub rate limit reached. Wait a moment and try again.")
        if contents_status == 404:
            raise GitHubFetchError(f"Path '{ref.path}' not found in this repo.")
        if contents_status != 200:
            raise GitHubFetchError(f"GitHub API error fetching directory: {contents_status}")

        # Resolve branch from repo default if not specified
        if not branch:
            branch = repo_data.get("default_branch", "main")
            logger.debug("[SCAN] resolved default branch → %s", branch)

        repo_visibility = repo_data.get("visibility", "unknown")
        logger.info("[SCAN] repo visibility=%s private=%s", repo_visibility, repo_data.get("private"))

        # Fetch recognised files in parallel
        recognised: List[dict] = []
        all_files_entries: List[FileManifestEntry] = []
        manifest_truncated_flag: bool = False
        if isinstance(contents_data, list):
            all_names = [f.get("name") for f in contents_data]
            logger.debug("[SCAN] dir listing %d items: %s", len(all_names), all_names)
            recognised = [f for f in contents_data if f.get("type") == "file" and f.get("name") in _SKILL_FILES]
            logger.info("[SCAN] recognised files in dir: %s", [f["name"] for f in recognised])
            all_files_entries, manifest_truncated_flag = build_file_manifest(contents_data)
            logger.debug("[SCAN] file manifest: %d entries, truncated=%s", len(all_files_entries), manifest_truncated_flag)
        else:
            logger.warning("[SCAN] contents_data is not a list (got %s) — path may not be a directory",
                           type(contents_data).__name__)

        # Use the GitHub Contents API (not download_url / raw.githubusercontent.com) so
        # auth works consistently for internal/private GHEC repos.
        file_tasks = {
            item["name"]: asyncio.create_task(self._fetch_text(
                f"/repos/{owner}/{repo}/contents/{item['path']}" + (f"?ref={branch}" if branch else ""),
                token,
            ))
            for item in recognised
        }
        files: Dict[str, str] = {}
        for fname, task in file_tasks.items():
            content = await task
            if content is not None:
                files[fname] = content
                logger.debug("[SCAN] fetched %s → %d chars", fname, len(content))
            else:
                logger.warning("[SCAN] fetched %s → None (empty or unreadable)", fname)

        logger.info("[SCAN] after dir fetch files=%s", list(files.keys()))

        # .claude-plugin/plugin.json fallback when plugin.json not found directly
        if "plugin.json" not in files:
            plugin_dir = f"{path}/.claude-plugin" if path else ".claude-plugin"
            alt_url = f"/repos/{owner}/{repo}/contents/{plugin_dir}/plugin.json"
            if branch:
                alt_url += f"?ref={branch}"
            logger.debug("[SCAN] no plugin.json in root, trying fallback %s", alt_url)
            alt_content = await self._fetch_text(alt_url, token)
            if alt_content:
                files["plugin.json"] = alt_content
                logger.info("[SCAN] plugin.json loaded from .claude-plugin fallback (%d chars)", len(alt_content))
            else:
                logger.debug("[SCAN] .claude-plugin/plugin.json fallback → None")
        else:
            logger.debug("[SCAN] plugin.json already present, skipping .claude-plugin fallback")

        # If plugin.json declares skills as a directory, look for SKILL.md inside it.
        # Handles patterns like "skills": "./skills" where SKILL.md lives in a subdir.
        has_skill_md = any(k in files for k in ("SKILL.md", "skill.md", "CLAUDE.md"))
        if "plugin.json" in files and not has_skill_md:
            logger.info("[SCAN] plugin.json present but no SKILL.md yet — checking plugin.json skills field")
            try:
                plugin_data = json.loads(files["plugin.json"])
                skills_val = plugin_data.get("skills")
                logger.debug("[SCAN] plugin.json skills=%r (type=%s)", skills_val, type(skills_val).__name__)
                if isinstance(skills_val, str):
                    # Resolve path: strip leading "./" or "/"
                    skills_rel = skills_val
                    if skills_rel.startswith("./"):
                        skills_rel = skills_rel[2:]
                    skills_rel = skills_rel.strip("/")
                    skills_abs = f"{path}/{skills_rel}" if path and skills_rel else (path or skills_rel)
                    skills_url = f"/repos/{owner}/{repo}/contents/{skills_abs}"
                    if branch:
                        skills_url += f"?ref={branch}"
                    logger.info("[SCAN] skills dir lookup: resolved path=%r url=%s", skills_abs, skills_url)
                    skills_listing, skills_status = await self._api_get(skills_url, token, owner=owner)
                    if skills_status == 200 and isinstance(skills_listing, list):
                        skills_names = [f.get("name") for f in skills_listing]
                        logger.debug("[SCAN] skills dir listing (%d items): %s", len(skills_names), skills_names)
                        direct = next(
                            (f for f in skills_listing if f.get("type") == "file" and f.get("name") in ("SKILL.md", "skill.md", "CLAUDE.md")),
                            None,
                        )
                        if direct:
                            logger.info("[SCAN] found %s directly in skills dir", direct["name"])
                            content = await self._fetch_text(
                                f"/repos/{owner}/{repo}/contents/{direct['path']}" + (f"?ref={branch}" if branch else ""),
                                token,
                            )
                            if content:
                                files[direct["name"]] = content
                                logger.info("[SCAN] fetched %s from skills dir → %d chars", direct["name"], len(content))
                            else:
                                logger.warning("[SCAN] %s in skills dir returned None content", direct["name"])
                        else:
                            subdirs = [f for f in skills_listing if f.get("type") == "dir"]
                            logger.info("[SCAN] no direct SKILL.md in skills dir, checking %d subdirs: %s",
                                        len(subdirs), [d["name"] for d in subdirs[:5]])
                            for subdir in subdirs[:5]:
                                sub_url = f"/repos/{owner}/{repo}/contents/{subdir['path']}"
                                if branch:
                                    sub_url += f"?ref={branch}"
                                logger.debug("[SCAN] checking subdir %s", subdir["path"])
                                sub_listing, sub_status = await self._api_get(sub_url, token, owner=owner)
                                if sub_status == 200 and isinstance(sub_listing, list):
                                    sub_names = [f.get("name") for f in sub_listing]
                                    logger.debug("[SCAN] subdir %s listing: %s", subdir["name"], sub_names)
                                    skill_file = next(
                                        (f for f in sub_listing if f.get("type") == "file" and f.get("name") in ("SKILL.md", "skill.md", "CLAUDE.md")),
                                        None,
                                    )
                                    if skill_file:
                                        logger.info("[SCAN] found %s in subdir %s", skill_file["name"], subdir["name"])
                                        content = await self._fetch_text(
                                            f"/repos/{owner}/{repo}/contents/{skill_file['path']}" + (f"?ref={branch}" if branch else ""),
                                            token,
                                        )
                                        if content:
                                            files[skill_file["name"]] = content
                                            logger.info("[SCAN] fetched %s from subdir %s → %d chars",
                                                        skill_file["name"], subdir["name"], len(content))
                                        else:
                                            logger.warning("[SCAN] %s in subdir %s returned None content",
                                                           skill_file["name"], subdir["name"])
                                        break
                                    else:
                                        logger.debug("[SCAN] subdir %s has no SKILL.md", subdir["name"])
                                else:
                                    logger.warning("[SCAN] subdir %s listing failed status=%d", subdir["name"], sub_status)
                    else:
                        logger.warning("[SCAN] skills dir %r → status=%d or not a list", skills_abs, skills_status)
                elif isinstance(skills_val, list):
                    logger.info("[SCAN] plugin.json skills is a list (file paths) — no subdir traversal needed")
                else:
                    logger.debug("[SCAN] plugin.json has no 'skills' field or value is %r", skills_val)
            except Exception as exc:
                logger.warning("[SCAN] SKILL.md subdir lookup failed: %s", exc, exc_info=True)
        elif has_skill_md:
            logger.debug("[SCAN] SKILL.md already found, skipping plugin.json subdir lookup")
        else:
            logger.debug("[SCAN] no plugin.json present, skipping subdir lookup")

        # Repo-root README (only needed when we're in a subdirectory)
        root_readme: Optional[str] = None
        if path:
            logger.debug("[SCAN] fetching repo-root README (path is subdir)")
            root_readme = await self._fetch_text(
                f"/repos/{owner}/{repo}/contents/README.md" + (f"?ref={branch}" if branch else ""),
                token,
            )
            logger.info("[SCAN] root_readme=%s", f"{len(root_readme)} chars" if root_readme else "None")

        logger.info("[SCAN] complete — files=%s root_readme=%s no_skill_files=%s",
                    list(files.keys()),
                    "set" if root_readme else "None",
                    len(files) == 0)

        result = RawScanResult(
            ref=GitHubRef(owner=ref.owner, repo=ref.repo, branch=branch, path=ref.path),
            repo_meta=repo_data,
            files=files,
            root_readme=root_readme,
            no_skill_files=len(files) == 0,
            all_files=all_files_entries,
            manifest_truncated=manifest_truncated_flag,
        )
        if cache_key:
            _scan_cache[cache_key] = result
        return result

    async def _fetch_file_content(self, item: dict, token: Optional[str]) -> Optional[str]:
        # Prefer direct download_url to avoid extra base64 dance
        dl = item.get("download_url")
        if dl:
            headers = self._make_headers(token)
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(dl, headers=headers)
                if resp.status_code == 200:
                    return resp.text
        # Fallback: base64 content in the item itself
        content_b64 = item.get("content", "")
        if content_b64:
            try:
                return base64.b64decode(content_b64.replace("\n", "")).decode("utf-8", errors="replace")
            except Exception:
                pass
        return None

    async def _fetch_text(self, path: str, token: Optional[str]) -> Optional[str]:
        data, status = await self._api_get(path, token)
        if status != 200 or not data:
            logger.debug("[FETCH] %s → status=%d, returning None", path, status)
            return None
        file_type = data.get("type") if isinstance(data, dict) else "list"
        content_b64 = data.get("content", "") if isinstance(data, dict) else ""
        if not content_b64:
            logger.debug("[FETCH] %s → type=%s no content field (symlink or dir?), returning None", path, file_type)
            return None
        try:
            text = base64.b64decode(content_b64.replace("\n", "")).decode("utf-8", errors="replace")
            logger.debug("[FETCH] %s → type=%s decoded %d chars", path, file_type, len(text))
            return text
        except Exception as exc:
            logger.warning("[FETCH] %s → base64 decode failed: %s", path, exc)
            return None

    async def fetch_file_content(
        self,
        owner: str,
        repo: str,
        branch: Optional[str],
        skill_path: str,
        filename: str,
        cache_key: Optional[str] = None,
    ) -> Optional[str]:
        """Fetch the text content of a single file from GitHub.

        Public API used by the file content endpoint. Wraps _best_token + _fetch_text.
        Returns None if the file is binary or unavailable.
        """
        from app.services.github import _file_content_cache
        if cache_key and cache_key in _file_content_cache:
            logger.debug("[FILE_FETCH] cache hit key=%s", cache_key)
            return _file_content_cache[cache_key]

        token = await self._best_token(owner)
        dir_prefix = skill_path.strip("/")
        file_api_path = f"/repos/{owner}/{repo}/contents/{dir_prefix + '/' if dir_prefix else ''}{filename}"
        if branch:
            file_api_path += f"?ref={branch}"

        content = await self._fetch_text(file_api_path, token)
        if cache_key and content is not None:
            _file_content_cache[cache_key] = content
        return content

    async def discover(self, ref: GitHubRef, cache_key: Optional[str] = None) -> tuple[List[RawScanResult], bool, bool]:
        """Recursively find skill directories (containing skill.md or CLAUDE.md).

        Returns (results, tree_truncated, capped).
        """
        if cache_key and cache_key in _scan_cache:
            logger.debug("[DISCOVER] cache hit key=%s", cache_key)
            return _scan_cache[cache_key]

        token = await self._best_token(ref.owner)
        owner, repo = ref.owner, ref.repo
        branch = ref.branch

        logger.info("[DISCOVER] start owner=%s repo=%s path=%r branch=%r", owner, repo, ref.path, branch)

        # Resolve default branch if needed
        if not branch:
            repo_data, status = await self._api_get(f"/repos/{owner}/{repo}", token, owner=owner)
            if status != 200:
                raise GitHubFetchError("Repo not found.")
            branch = repo_data.get("default_branch", "main")
            logger.debug("[DISCOVER] resolved default branch → %s", branch)

        tree_data, tree_status = await self._api_get(
            f"/repos/{owner}/{repo}/git/trees/{branch}?recursive=1", token, owner=owner
        )
        if tree_status != 200:
            raise GitHubFetchError(f"Could not retrieve repo tree: {tree_status}")

        truncated = bool(tree_data.get("truncated"))
        tree_items = tree_data.get("tree", [])
        logger.info("[DISCOVER] tree has %d items truncated=%s", len(tree_items), truncated)

        # Find directories that contain skill.md, CLAUDE.md, or plugin.json
        base = ref.path.strip("/")  # "" for root, "engineering" for subdir
        _plugin_subdir_re = re.compile(r"(^|\/)\.[\w-]+-plugin$")
        plugin_json_dirs: set[str] = set()
        skill_md_dirs: set[str] = set()
        for item in tree_items:
            if item.get("type") == "blob":
                ipath = item.get("path", "")
                fname = ipath.rsplit("/", 1)[-1] if "/" in ipath else ipath
                if fname in ("SKILL.md", "skill.md", "CLAUDE.md", "plugin.json"):
                    dirpath = ipath.rsplit("/", 1)[0] if "/" in ipath else "/"
                    orig_dirpath = dirpath
                    # .<name>-plugin/plugin.json (e.g. .claude-plugin, .codex-plugin) → use parent
                    if fname == "plugin.json" and _plugin_subdir_re.search(dirpath):
                        dirpath = dirpath.rsplit("/", 1)[0] if "/" in dirpath else "/"
                        logger.debug("[DISCOVER] plugin subdir strip: %s → %s", orig_dirpath, dirpath)
                    if base and not dirpath.startswith(base):
                        logger.debug("[DISCOVER] skip %s (not under base %r)", ipath, base)
                        continue
                    if fname == "plugin.json":
                        plugin_json_dirs.add(dirpath)
                    else:
                        skill_md_dirs.add(dirpath)

        logger.info("[DISCOVER] plugin_json_dirs=%s skill_md_dirs=%s", sorted(plugin_json_dirs), sorted(skill_md_dirs))

        # Drop SKILL.md-only dirs that are subdirectories of a plugin.json dir
        # (e.g. skills/foo/SKILL.md inside a plugin that already has plugin.json at root)
        pruned_skill_md = {
            d for d in skill_md_dirs
            if not any(
                d != p and d.startswith(p.rstrip("/") + "/")
                for p in plugin_json_dirs
            )
        }
        pruned = skill_md_dirs - pruned_skill_md
        if pruned:
            logger.info("[DISCOVER] pruned nested skill_md dirs: %s", sorted(pruned))
        skill_file_dirs = plugin_json_dirs | pruned_skill_md
        logger.info("[DISCOVER] final skill_file_dirs (%d): %s", len(skill_file_dirs), sorted(skill_file_dirs))

        capped = len(skill_file_dirs) > 20
        dirs_to_scan = list(skill_file_dirs)[:20]
        if capped:
            logger.warning("[DISCOVER] capped at 20 dirs, skipping %d", len(skill_file_dirs) - 20)

        # Parallel scans (up to 20)
        scan_tasks = [
            self.scan(GitHubRef(owner=owner, repo=repo, branch=branch, path="/" + d if d != "/" else "/"))
            for d in dirs_to_scan
        ]
        results = await asyncio.gather(*scan_tasks, return_exceptions=True)
        errors = [r for r in results if isinstance(r, Exception)]
        valid = [r for r in results if isinstance(r, RawScanResult)]
        if errors:
            logger.warning("[DISCOVER] %d scan tasks failed: %s", len(errors), errors)
        logger.info("[DISCOVER] complete — %d valid scan results", len(valid))

        out = (valid, truncated, capped)
        if cache_key:
            _scan_cache[cache_key] = out
        return out


github_scanner = GitHubScanner()
scanner_registry.register("github", github_scanner)

# 5-minute TTL cache for file content, keyed by (slug, path)
_file_content_cache: TTLCache = TTLCache(maxsize=1024, ttl=300)


# ---------------------------------------------------------------------------
# MetadataExtractor
# ---------------------------------------------------------------------------

class MetadataExtractor:
    """Pure transformation: RawScanResult → SkillScanSnapshot. No I/O."""

    def extract(self, result: RawScanResult) -> SkillScanSnapshot:
        files = result.files
        repo = result.repo_meta
        ref = result.ref

        plugin = self._parse_plugin_json(files.get("plugin.json", ""))
        name = self._extract_name(files, repo, ref, plugin)
        description = self._extract_description(files, repo, plugin)
        platforms = self._extract_platforms(files, plugin)
        version = self._extract_version(files, plugin)
        keywords = self._extract_keywords(files, plugin)
        license_name = self._extract_license(repo)
        readme_html = self._extract_readme_html(files, result.root_readme)

        last_commit_at: Optional[datetime] = None
        pushed = repo.get("pushed_at")
        if pushed:
            try:
                last_commit_at = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
            except ValueError:
                pass

        _vis = repo.get("visibility", "public")
        visibility = VisibilityEnum.internal if (_vis == "internal" or repo.get("private")) else VisibilityEnum.public

        forked_from_url: Optional[str] = None
        if repo.get("fork"):
            parent = repo.get("parent", {})
            raw = parent.get("html_url")
            forked_from_url = _normalize_github_url(raw)

        return SkillScanSnapshot(
            ref=ref,
            name=name,
            description=description,
            compatible_platforms=platforms,
            version=version,
            license=license_name,
            readme_html=readme_html,
            stars=repo.get("stargazers_count", 0),
            last_commit_at=last_commit_at,
            visibility=visibility,
            forked_from_url=forked_from_url,
            fetched_at=datetime.now(timezone.utc),
            no_skill_files=result.no_skill_files,
            agent_count=plugin.get("agent_count", 0),
            agent_names=plugin.get("agent_names", []),
            has_mcp_server=plugin.get("has_mcp_server", False),
            has_scripts=plugin.get("has_scripts", False),
            plugin_author=plugin.get("plugin_author"),
            keywords=keywords,
            file_manifest=result.all_files,
            manifest_truncated=result.manifest_truncated,
        )

    def _frontmatter(self, content: str) -> tuple[dict, str]:
        try:
            import frontmatter
            post = frontmatter.loads(content)
            return dict(post.metadata), post.content
        except Exception:
            return {}, content

    _GENERIC_NAMES = {"skill", "skills", "your-skill-name", "your_skill_name", "skill-name", "plugin", "tool"}

    def _parse_plugin_json(self, content: str) -> dict:
        if not content:
            return {}
        try:
            data = json.loads(content)
        except Exception:
            return {}

        agents = data.get("agents", [])
        if not isinstance(agents, list):
            agents = []
        agent_names = []
        for a in agents:
            if isinstance(a, dict):
                n = a.get("name", "")
            else:
                n = str(a)
            if n:
                agent_names.append(n)

        mcp_servers = data.get("mcp-servers", [])
        has_mcp = isinstance(mcp_servers, list) and len(mcp_servers) > 0

        scripts = data.get("scripts", {})
        has_scripts = isinstance(scripts, dict) and bool(scripts)

        author = data.get("author")
        plugin_author: Optional[str] = None
        if isinstance(author, str):
            plugin_author = author or None
        elif isinstance(author, dict):
            plugin_author = author.get("name") or None

        platforms = data.get("platforms", [])
        if not isinstance(platforms, list):
            platforms = []

        keywords = data.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = []

        version = data.get("version")

        return {
            "agent_count": len(agents),
            "agent_names": agent_names,
            "has_mcp_server": has_mcp,
            "has_scripts": has_scripts,
            "plugin_author": plugin_author,
            "platforms": [str(p) for p in platforms if p],
            "keywords": [str(k) for k in keywords if k],
            "version": str(version) if version else None,
            "name": str(data["name"]) if data.get("name") else None,
            "description": str(data["description"]) if data.get("description") else None,
        }

    def _extract_keywords(self, files: dict, plugin: dict) -> List[str]:
        seen: set[str] = set()
        result: List[str] = []
        for kw in plugin.get("keywords", []):
            k = kw.strip().lower()
            if k and k not in seen:
                seen.add(k)
                result.append(k)
        for fname in ("SKILL.md", "skill.md", "CLAUDE.md"):
            if fname in files:
                meta, _ = self._frontmatter(files[fname])
                for kw in meta.get("keywords", []) or []:
                    k = str(kw).strip().lower()
                    if k and k not in seen:
                        seen.add(k)
                        result.append(k)
        return result

    def _extract_name(self, files: dict, repo: dict, ref: SourceRef, plugin: dict = {}) -> Optional[str]:
        for fname in ("SKILL.md", "skill.md", "CLAUDE.md"):
            if fname in files:
                meta, _ = self._frontmatter(files[fname])
                candidate = str(meta["name"]) if meta.get("name") else None
                if candidate and candidate.lower() not in self._GENERIC_NAMES:
                    return candidate
        if plugin.get("name") and plugin["name"].lower() not in self._GENERIC_NAMES:
            return plugin["name"]
        if "package.json" in files:
            try:
                data = json.loads(files["package.json"])
                if data.get("name"):
                    return str(data["name"])
            except Exception:
                pass
        if "pyproject.toml" in files:
            name = self._toml_get(files["pyproject.toml"], "project", "name")
            if name:
                return str(name)
        path = ref.path.strip("/")
        if path:
            return path.rsplit("/", 1)[-1]
        return repo.get("name")

    def _extract_description(self, files: dict, repo: dict, plugin: dict = {}) -> Optional[str]:
        for fname in ("SKILL.md", "skill.md", "CLAUDE.md"):
            if fname in files:
                meta, content = self._frontmatter(files[fname])
                if meta.get("description"):
                    return str(meta["description"])
        if plugin.get("description"):
            return plugin["description"]
        if "README.md" in files:
            para = self._first_paragraph(files["README.md"])
            if para:
                return para
        return repo.get("description")

    def _extract_platforms(self, files: dict, plugin: dict = {}) -> List[str]:
        # plugin.json platforms field takes highest priority
        if plugin.get("platforms"):
            return plugin["platforms"]
        for fname in ("SKILL.md", "skill.md", "CLAUDE.md"):
            if fname in files:
                meta, _ = self._frontmatter(files[fname])
                if meta.get("platforms"):
                    return [str(p) for p in meta["platforms"]]
        platforms: List[str] = []
        if "CLAUDE.md" in files or "SKILL.md" in files or "skill.md" in files:
            platforms.append("claude-code")
        if "package.json" in files:
            try:
                data = json.loads(files["package.json"])
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                if any("openai" in k for k in deps):
                    platforms.append("openai")
                if any("langchain" in k for k in deps):
                    platforms.append("langchain")
            except Exception:
                pass
        return platforms

    def _extract_version(self, files: dict, plugin: dict = {}) -> Optional[str]:
        for fname in ("SKILL.md", "skill.md", "CLAUDE.md"):
            if fname in files:
                meta, _ = self._frontmatter(files[fname])
                if meta.get("version"):
                    return str(meta["version"])
        if plugin.get("version"):
            return plugin["version"]
        if "package.json" in files:
            try:
                data = json.loads(files["package.json"])
                if data.get("version"):
                    return str(data["version"])
            except Exception:
                pass
        v = self._toml_get(files.get("pyproject.toml", ""), "project", "version")
        if v:
            return str(v)
        return None

    def _extract_license(self, repo: dict) -> Optional[str]:
        lic = repo.get("license")
        if lic:
            return lic.get("spdx_id") or lic.get("name")
        return None

    def _extract_readme_html(self, files: dict, root_readme: Optional[str]) -> Optional[str]:
        # We store raw markdown here; rendering is deferred (consistent with existing pattern)
        if "README.md" in files:
            return files["README.md"]
        if root_readme:
            return root_readme
        return None

    def _first_paragraph(self, md: str) -> Optional[str]:
        for line in md.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("!"):
                return line
        return None

    def _toml_get(self, content: str, *keys: str) -> Optional[Any]:
        if not content:
            return None
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                return None
        try:
            data = tomllib.loads(content)
            for k in keys:
                if not isinstance(data, dict):
                    return None
                data = data.get(k)
            return data
        except Exception:
            return None


metadata_extractor = MetadataExtractor()
