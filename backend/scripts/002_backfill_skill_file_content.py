"""Migration 002: Backfill skill_md_raw, skill_md_filename, readme_raw for existing skills.

Iterates all skills where these fields are absent and fetches file content from GitHub.
Skips skills whose GitHub repo returns an error (logged, not fatal).

Run once:
    cd backend && python -m scripts.002_backfill_skill_file_content

Idempotent: only processes skills where skill_md_raw AND readme_raw are both null.
Dry-run mode: set DRY_RUN=1 to log what would change without writing.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/agent-skills")
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
SKILL_MD_MAX_BYTES = 100_000

# Recognised skill instruction filenames in priority order
_SKILL_FILES = ("SKILL.md", "skill.md", "CLAUDE.md")


async def _fetch_files(owner: str, repo: str, skill_path: str, token: str | None) -> dict[str, str]:
    """Fetch recognised files from skill_path directory via GitHub Contents API."""
    import base64
    import httpx

    headers: dict[str, str] = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    path = skill_path.strip("/")
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}" if path else \
          f"https://api.github.com/repos/{owner}/{repo}/contents"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Contents API {resp.status_code} for {owner}/{repo}{skill_path}")
        listing = resp.json()

    if not isinstance(listing, list):
        return {}

    wanted = {f["name"]: f for f in listing if f.get("type") == "file" and f["name"] in (*_SKILL_FILES, "README.md")}
    files: dict[str, str] = {}

    async def _fetch_one(name: str, item: dict) -> None:
        dl = item.get("download_url")
        if dl:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(dl, headers=headers)
                if r.status_code == 200:
                    files[name] = r.text
                    return
        b64 = item.get("content", "")
        if b64:
            try:
                files[name] = base64.b64decode(b64.replace("\n", "")).decode("utf-8", errors="replace")
            except Exception:
                pass

    await asyncio.gather(*[_fetch_one(n, i) for n, i in wanted.items()])
    return files


async def main() -> None:
    import re

    _REPO_RE = re.compile(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")

    token = os.environ.get("GITHUB_TOKEN")

    client = AsyncIOMotorClient(MONGO_URI)
    db = client.get_default_database()
    skills = db["skills"]

    # Only process skills that are missing both file content fields
    query = {
        "$or": [
            {"skill_md_raw": {"$exists": False}},
            {"skill_md_raw": None},
        ],
        "$and": [
            {"$or": [
                {"readme_raw": {"$exists": False}},
                {"readme_raw": None},
            ]},
        ],
    }

    total = await skills.count_documents(query)
    log.info("Skills to backfill: %d%s", total, " (DRY RUN)" if DRY_RUN else "")

    processed = updated = skipped = errors = 0

    async for doc in skills.find(query, {"_id": 1, "repo_url": 1, "skill_path": 1, "name": 1}):
        processed += 1
        slug = doc.get("slug", str(doc["_id"]))
        repo_url = doc.get("repo_url", "")
        skill_path = doc.get("skill_path", "/")

        m = _REPO_RE.match(repo_url.strip())
        if not m:
            log.warning("  SKIP %s — not a GitHub URL: %s", slug, repo_url)
            skipped += 1
            continue

        owner, repo = m.group(1), m.group(2)

        try:
            files = await _fetch_files(owner, repo, skill_path, token)
        except Exception as exc:
            log.warning("  ERROR %s — %s", slug, exc)
            errors += 1
            continue

        skill_md_raw: str | None = None
        skill_md_filename: str | None = None
        for fname in _SKILL_FILES:
            if fname in files:
                skill_md_raw = files[fname][:SKILL_MD_MAX_BYTES]
                skill_md_filename = fname
                break

        readme_raw: str | None = files.get("README.md")

        if skill_md_raw is None and readme_raw is None:
            log.info("  NO FILES %s (%s/%s%s)", slug, owner, repo, skill_path)
            skipped += 1
            continue

        fields: dict = {}
        if skill_md_raw is not None:
            fields["skill_md_raw"] = skill_md_raw
            fields["skill_md_filename"] = skill_md_filename
        if readme_raw is not None:
            fields["readme_raw"] = readme_raw

        log.info(
            "  %s %s — skill_md=%s readme=%s",
            "WOULD UPDATE" if DRY_RUN else "UPDATE",
            slug,
            skill_md_filename or "none",
            "yes" if readme_raw else "no",
        )

        if not DRY_RUN:
            await skills.update_one({"_id": doc["_id"]}, {"$set": fields})
        updated += 1

    log.info(
        "Done. processed=%d updated=%d skipped=%d errors=%d",
        processed, updated, skipped, errors,
    )
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
