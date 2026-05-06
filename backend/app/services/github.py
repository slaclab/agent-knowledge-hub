from __future__ import annotations

import asyncio
import base64
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

import httpx
from cachetools import TTLCache
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


# ---------------------------------------------------------------------------
# GitHubRef — parsed URL components
# ---------------------------------------------------------------------------

class GitHubRef(BaseModel):
    owner: str
    repo: str
    branch: Optional[str] = None
    path: str = "/"


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


# ---------------------------------------------------------------------------
# RawScanResult
# ---------------------------------------------------------------------------

_SKILL_FILES = {"SKILL.md", "skill.md", "CLAUDE.md", "README.md", "package.json", "pyproject.toml", "plugin.json"}


class RawScanResult(BaseModel):
    ref: GitHubRef
    repo_meta: Dict[str, Any] = {}
    files: Dict[str, str] = {}        # filename → decoded text content
    root_readme: Optional[str] = None  # repo-root README when path != "/"
    no_skill_files: bool = False       # True when directory has no recognised skill files


# ---------------------------------------------------------------------------
# SkillScanSnapshot — richer than GitHubSnapshot, returned by /api/github-scan
# ---------------------------------------------------------------------------

class SkillScanSnapshot(BaseModel):
    ref: GitHubRef
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


# ---------------------------------------------------------------------------
# GitHubScanner
# ---------------------------------------------------------------------------

_scan_cache: TTLCache = TTLCache(maxsize=256, ttl=60)


class GitHubScanner:
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
            return app_token or pat
        return pat

    async def _api_get(self, path: str, token: Optional[str], accept: str = "application/vnd.github+json", owner: Optional[str] = None) -> tuple[Any, int]:
        headers = self._make_headers(token)
        headers["Accept"] = accept
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self._base}{path}", headers=headers)
            if resp.status_code == 401 and token:
                from app.services.github_app import github_app_client
                await github_app_client.invalidate(owner=owner)
                resp = await client.get(f"{self._base}{path}", headers=headers)
            if resp.status_code == 200:
                return resp.json(), 200
            return None, resp.status_code

    async def scan(self, ref: GitHubRef, cache_key: Optional[str] = None) -> RawScanResult:
        if cache_key and cache_key in _scan_cache:
            return _scan_cache[cache_key]

        token = await self._best_token(ref.owner)
        owner, repo = ref.owner, ref.repo
        branch = ref.branch
        path = ref.path.lstrip("/")

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

        # Fetch recognised files in parallel
        recognised: List[dict] = []
        if isinstance(contents_data, list):
            recognised = [f for f in contents_data if f.get("type") == "file" and f.get("name") in _SKILL_FILES]

        file_tasks = {
            item["name"]: asyncio.create_task(self._fetch_file_content(item, token))
            for item in recognised
        }
        files: Dict[str, str] = {}
        for fname, task in file_tasks.items():
            content = await task
            if content is not None:
                files[fname] = content

        # .claude-plugin/plugin.json fallback when plugin.json not found directly
        if "plugin.json" not in files:
            plugin_dir = f"{path}/.claude-plugin" if path else ".claude-plugin"
            alt_url = f"/repos/{owner}/{repo}/contents/{plugin_dir}/plugin.json"
            if branch:
                alt_url += f"?ref={branch}"
            alt_content = await self._fetch_text(alt_url, token)
            if alt_content:
                files["plugin.json"] = alt_content

        # Repo-root README (only needed when we're in a subdirectory)
        root_readme: Optional[str] = None
        if path:
            root_readme = await self._fetch_text(
                f"/repos/{owner}/{repo}/contents/README.md" + (f"?ref={branch}" if branch else ""),
                token,
            )

        result = RawScanResult(
            ref=GitHubRef(owner=ref.owner, repo=ref.repo, branch=branch, path=ref.path),
            repo_meta=repo_data,
            files=files,
            root_readme=root_readme,
            no_skill_files=len(files) == 0,
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
            return None
        content_b64 = data.get("content", "")
        if content_b64:
            try:
                return base64.b64decode(content_b64.replace("\n", "")).decode("utf-8", errors="replace")
            except Exception:
                pass
        return None

    async def discover(self, ref: GitHubRef, cache_key: Optional[str] = None) -> tuple[List[RawScanResult], bool, bool]:
        """Recursively find skill directories (containing skill.md or CLAUDE.md).

        Returns (results, tree_truncated, capped).
        """
        if cache_key and cache_key in _scan_cache:
            return _scan_cache[cache_key]

        token = await self._best_token(ref.owner)
        owner, repo = ref.owner, ref.repo
        branch = ref.branch

        # Resolve default branch if needed
        if not branch:
            repo_data, status = await self._api_get(f"/repos/{owner}/{repo}", token, owner=owner)
            if status != 200:
                raise GitHubFetchError("Repo not found.")
            branch = repo_data.get("default_branch", "main")

        tree_data, tree_status = await self._api_get(
            f"/repos/{owner}/{repo}/git/trees/{branch}?recursive=1", token, owner=owner
        )
        if tree_status != 200:
            raise GitHubFetchError(f"Could not retrieve repo tree: {tree_status}")

        truncated = bool(tree_data.get("truncated"))
        tree_items = tree_data.get("tree", [])

        # Find directories that contain skill.md, CLAUDE.md, or plugin.json
        base = ref.path.strip("/")  # "" for root, "engineering" for subdir
        skill_file_dirs: set[str] = set()
        for item in tree_items:
            if item.get("type") == "blob":
                ipath = item.get("path", "")
                fname = ipath.rsplit("/", 1)[-1] if "/" in ipath else ipath
                if fname in ("SKILL.md", "skill.md", "CLAUDE.md", "plugin.json"):
                    dirpath = ipath.rsplit("/", 1)[0] if "/" in ipath else "/"
                    # .claude-plugin/plugin.json → parent is the skill dir
                    if fname == "plugin.json" and (dirpath == ".claude-plugin" or dirpath.endswith("/.claude-plugin")):
                        dirpath = dirpath[: -len("/.claude-plugin")] if "/" in dirpath else "/"
                    if base and not dirpath.startswith(base):
                        continue
                    skill_file_dirs.add(dirpath)

        capped = len(skill_file_dirs) > 20
        dirs_to_scan = list(skill_file_dirs)[:20]

        # Parallel scans (up to 20)
        scan_tasks = [
            self.scan(GitHubRef(owner=owner, repo=repo, branch=branch, path="/" + d if d != "/" else "/"))
            for d in dirs_to_scan
        ]
        results = await asyncio.gather(*scan_tasks, return_exceptions=True)
        valid = [r for r in results if isinstance(r, RawScanResult)]

        out = (valid, truncated, capped)
        if cache_key:
            _scan_cache[cache_key] = out
        return out


github_scanner = GitHubScanner()


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

    def _extract_name(self, files: dict, repo: dict, ref: GitHubRef, plugin: dict = {}) -> Optional[str]:
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
