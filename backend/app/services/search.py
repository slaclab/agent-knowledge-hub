"""Search enhancement helpers for #015 — name boost and Atlas Search pipeline builder."""
from __future__ import annotations

import logging
from typing import List

from app.models.skill import Skill, SkillStatus

logger = logging.getLogger(__name__)


async def name_boost(q: str, base_results: List[Skill]) -> List[Skill]:
    """Prepend exact name/slug matches to base_results (deduplicating by id).

    Issues a separate DB call so off-page exact matches are surfaced.
    Uses $eq only — no regex.
    """
    if not q or not q.strip():
        return base_results

    q_stripped = q.strip()
    exact_matches = await Skill.find(
        Skill.status == SkillStatus.active,
        {"$or": [
            {"name": {"$eq": q_stripped}},
            {"slug": {"$eq": q_stripped}},
        ]},
    ).to_list()

    if not exact_matches:
        return base_results

    exact_ids = {str(s.id) for s in exact_matches}
    deduped_base = [s for s in base_results if str(s.id) not in exact_ids]
    return exact_matches + deduped_base


def build_atlas_pipeline(q: str, filters: dict) -> List[dict]:
    """Build a MongoDB Atlas Search aggregation pipeline.

    Dead-letter on self-hosted Percona PSMDB — kept for future Atlas migration.
    See ADR-U34.
    """
    must_clauses = [{"text": {"query": q, "path": ["name", "description"]}}]
    for field, value in filters.items():
        must_clauses.append({"equals": {"path": field, "value": value}})
    return [
        {"$search": {"compound": {"must": must_clauses}}},
        {"$addFields": {"score": {"$meta": "searchScore"}}},
    ]
