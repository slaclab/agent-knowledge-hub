"""Catalog endpoints for the /agent-knowledge-hub Claude Code skill.

Provides:
  GET /api/skills/summary    — slim skill listing for LLM-powered search (no readme_html)
  GET /api/marketplace.json  — dynamic Claude Code marketplace manifest (5-min cache + ETag)
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import List

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse

from app.config import settings
from app.models.skill import EntryType, Skill, SkillStatus
from app.schemas.skill import SkillSummaryOut
from app.services.label import label_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
# In-process cache for marketplace.json (avoids a DB round-trip on every hit)
# ---------------------------------------------------------------------------
_marketplace_cache: dict = {}
_marketplace_cache_ts: float = 0.0
_MARKETPLACE_TTL = 300  # 5 minutes


@router.get("/skills/summary", response_model=List[SkillSummaryOut])
async def skills_summary(
    q: str | None = Query(None, description="Optional full-text filter (applied in-process)"),
):
    """Return a slim list of all active skills — slug, name, description, labels, avg_rating.

    Omits readme_html so the payload stays small enough to pass to Claude as context.
    Callers may pass ?q= for a basic case-insensitive substring filter on name/description.
    """
    # Fetch all active skills in one query (no pagination — summary is for LLM context budget)
    skills = await Skill.find(Skill.status == SkillStatus.active).to_list()

    # Optional client-side substring filter
    if q:
        q_lower = q.lower()
        skills = [
            s for s in skills
            if q_lower in (s.name or "").lower()
            or q_lower in (s.description or "").lower()
        ]

    skill_ids = [str(s.id) for s in skills]
    labels_by_skill = await label_service.batch_labels_for_skills(skill_ids)

    return [
        SkillSummaryOut(
            slug=s.slug,
            name=s.name,
            description=s.description,
            repo_url=s.repo_url,
            skill_path=s.skill_path,
            entry_type=s.entry_type.value,
            compatible_platforms=s.compatible_platforms,
            keywords=s.keywords,
            version=s.version,
            avg_rating=s.avg_rating,
            rating_count=s.rating_count,
            labels=[lbl.name for lbl in labels_by_skill.get(str(s.id), [])],
        )
        for s in skills
    ]


@router.get("/marketplace.json")
async def marketplace_json(response: Response):
    """Dynamic Claude Code marketplace manifest.

    Lists every active skill with entry_type=skill as a plugin entry.
    Cached for 5 minutes; returns ETag for conditional GET support.
    """
    global _marketplace_cache, _marketplace_cache_ts

    now = time.monotonic()
    if now - _marketplace_cache_ts > _MARKETPLACE_TTL or not _marketplace_cache:
        skills = await Skill.find(
            Skill.status == SkillStatus.active,
            Skill.entry_type == EntryType.skill,
        ).to_list()

        # Always include the discovery plugin itself as the first entry — it's a
        # bootstrap tool that must be installable before the user has the skill to
        # discover it via the catalog.
        plugins = [
            {
                "name": "agent-knowledge-hub",
                "description": "Discover, install, rate, and submit skills from the SLAC S3DF catalog — entirely within your agent session.",
                "source": {
                    "source": "github",
                    "repo": "slaclab/agent-knowledge-hub",
                    "path": "skill",
                },
            }
        ]
        for s in skills:
            # Derive GitHub owner/repo from repo_url
            # Expected format: https://github.com/<owner>/<repo>
            repo_path = s.repo_url.rstrip("/").removeprefix("https://github.com/")
            parts = repo_path.split("/")
            if len(parts) < 2:
                logger.debug("marketplace.json: skipping %s — repo_url not a github.com URL", s.slug)
                continue
            owner, repo = parts[0], parts[1]

            plugin: dict = {
                "name": s.slug,
                "description": s.description or s.name,
                "source": {
                    "source": "github",
                    "repo": f"{owner}/{repo}",
                },
            }
            if s.version:
                plugin["version"] = s.version
            if s.keywords:
                plugin["keywords"] = s.keywords
            if s.skill_path and s.skill_path not in ("/", ""):
                plugin["source"]["path"] = s.skill_path.lstrip("/")

            plugins.append(plugin)

        manifest = {
            "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
            "name": "SLAC-Agent-Knowledge-Hub",
            "description": "SLAC Agent Knowledge Hub Catalog",
            "owner": {
                "name": "SLAC S3DF",
                "email": "s3df-support@slac.stanford.edu",
            },
            "metadata": {"version": "1.0.0"},
            "plugins": plugins,
        }

        _marketplace_cache = manifest
        _marketplace_cache_ts = now
        logger.debug("marketplace.json: refreshed cache with %d plugins", len(plugins))

    body = json.dumps(_marketplace_cache, indent=2)
    etag = f'"{hashlib.md5(body.encode()).hexdigest()}"'

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=300"
    return JSONResponse(content=_marketplace_cache, headers={"ETag": etag, "Cache-Control": "public, max-age=300"})
