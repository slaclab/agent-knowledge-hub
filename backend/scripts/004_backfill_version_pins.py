"""Migration 004: Backfill pinned_commit_sha for existing GitHub skills.

Iterates all GitHub skills where pinned_commit_sha is absent, fetches the HEAD SHA
of the default branch, and populates pinned_commit_sha (and pinned_ref if a matching
tag exists). Local skills are skipped — pinning is not applicable.

Run once:
    cd backend && python -m scripts.004_backfill_version_pins

Idempotent: only processes skills where pinned_commit_sha is null and source_type != 'local'.
Dry-run mode: set DRY_RUN=1 to log what would change without writing.
Concurrency: set WORKERS=N to control parallel GitHub API calls (default: 5).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/agent-skills")
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
WORKERS = int(os.environ.get("WORKERS", "5"))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

_REPO_PREFIX_RE = re.compile(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:[/?#]|$)")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


async def _fetch_head_sha(client: httpx.AsyncClient, owner: str, repo: str) -> tuple[str | None, str | None]:
    """Return (head_sha, tag_name_or_None). Both None on any error."""
    try:
        # Step 1: get default branch
        repo_resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=_headers())
        if repo_resp.status_code != 200:
            log.warning("  repo metadata failed status=%d", repo_resp.status_code)
            return None, None
        default_branch = repo_resp.json().get("default_branch", "main")

        # Step 2: fetch HEAD SHA
        ref_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{default_branch}",
            headers=_headers(),
        )
        if ref_resp.status_code != 200:
            log.warning("  git/ref failed status=%d", ref_resp.status_code)
            return None, None
        head_sha = ref_resp.json()["object"]["sha"]
        if not _SHA_RE.match(head_sha):
            log.warning("  unexpected SHA format: %r", head_sha)
            return None, None

        # Step 3: find matching tag (best-effort)
        head_tag = None
        tags_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/tags",
            params={"per_page": "10"},
            headers=_headers(),
        )
        if tags_resp.status_code == 200:
            for tag in tags_resp.json():
                if tag.get("commit", {}).get("sha") == head_sha:
                    head_tag = tag.get("name")
                    break

        return head_sha, head_tag
    except Exception as exc:
        log.warning("  exception fetching SHA: %s", exc)
        return None, None


async def _process_skill(semaphore: asyncio.Semaphore, db, skill: dict) -> None:
    slug = skill.get("slug", "<unknown>")
    repo_url = skill.get("repo_url", "")
    m = _REPO_PREFIX_RE.match(repo_url)
    if not m:
        log.warning("[%s] cannot parse repo_url=%r — skipping", slug, repo_url)
        return

    owner, repo = m.group(1), m.group(2)
    log.info("[%s] fetching HEAD SHA owner=%s repo=%s", slug, owner, repo)

    async with semaphore:
        async with httpx.AsyncClient(timeout=15) as client:
            head_sha, head_tag = await _fetch_head_sha(client, owner, repo)

    if head_sha is None:
        log.warning("[%s] could not get HEAD SHA — leaving unpinned", slug)
        return

    log.info("[%s] HEAD SHA=%s tag=%s", slug, head_sha[:7], head_tag)

    if DRY_RUN:
        log.info("[%s] DRY_RUN — would set pinned_commit_sha=%s pinned_ref=%s", slug, head_sha[:7], head_tag)
        return

    await db["skills"].update_one(
        {"_id": skill["_id"]},
        {"$set": {"pinned_commit_sha": head_sha, "pinned_ref": head_tag}},
    )
    log.info("[%s] updated ✓", slug)


async def main() -> None:
    log.info("Migration 004: backfill version pins  DRY_RUN=%s WORKERS=%d", DRY_RUN, WORKERS)

    client = AsyncIOMotorClient(MONGO_URI)
    db = client.get_default_database()

    # Find all GitHub skills without a pin
    cursor = db["skills"].find({
        "$or": [{"pinned_commit_sha": None}, {"pinned_commit_sha": {"$exists": False}}],
        "source_type": {"$ne": "local"},
    })
    skills = await cursor.to_list(length=None)
    log.info("Found %d skill(s) needing backfill", len(skills))

    if not skills:
        log.info("Nothing to do.")
        client.close()
        return

    semaphore = asyncio.Semaphore(WORKERS)
    tasks = [_process_skill(semaphore, db, s) for s in skills]
    await asyncio.gather(*tasks)

    log.info("Done.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
