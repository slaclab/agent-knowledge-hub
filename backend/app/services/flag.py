"""Flag service: create/upsert, retract, resolve-all, list flagged skills."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.models.flag import FlagReason, FlagStatus, SkillFlag
from app.models.skill import Skill, SkillStatus
from app.schemas.flag import AdminFlagOut, FlaggedSkillSummary


async def create_or_update(
    skill_id: str,
    reporter_id: str,
    reason: FlagReason,
    note: Optional[str],
    superseded_by_slug: Optional[str],
) -> SkillFlag:
    """Upsert a flag. Increments Skill.flag_count only when transitioning resolved→active or on new insert."""
    now = datetime.now(timezone.utc)
    collection = SkillFlag.get_motor_collection()

    for _ in range(2):  # retry once on DuplicateKeyError race
        try:
            before = await collection.find_one_and_update(
                {"skill_id": skill_id, "reporter_id": reporter_id},
                {
                    "$set": {
                        "reason": reason.value,
                        "note": note,
                        "superseded_by_slug": superseded_by_slug,
                        "status": FlagStatus.active.value,
                        "created_at": now,
                        "resolved_by": None,
                        "resolution_note": None,
                        "resolved_at": None,
                    },
                    "$setOnInsert": {
                        "skill_id": skill_id,
                        "reporter_id": reporter_id,
                    },
                },
                upsert=True,
                return_document=False,  # returns the BEFORE state (None for new inserts)
            )
            break
        except DuplicateKeyError:
            continue

    # Increment flag_count when:
    #   - New insert (before is None)
    #   - Re-flag after resolved (before.status == "resolved")
    # Skip when the flag was already active (no state change).
    should_increment = before is None or before.get("status") == FlagStatus.resolved.value
    if should_increment:
        await Skill.find_one(Skill.id == ObjectId(skill_id)).update(
            {"$inc": {"flag_count": 1}}
        )

    return await SkillFlag.find_one(
        SkillFlag.skill_id == skill_id,
        SkillFlag.reporter_id == reporter_id,
    )


async def retract(skill_id: str, reporter_id: str) -> None:
    """Set the user's active flag to resolved and decrement flag_count (floor 0)."""
    collection = SkillFlag.get_motor_collection()
    result = await collection.find_one_and_update(
        {"skill_id": skill_id, "reporter_id": reporter_id, "status": FlagStatus.active.value},
        {"$set": {"status": FlagStatus.resolved.value, "resolved_at": datetime.now(timezone.utc)}},
        return_document=False,
    )
    if result is None:
        raise ValueError("no_active_flag")

    # Decrement with floor-at-0 guarantee via conditional update
    skill_collection = Skill.get_motor_collection()
    await skill_collection.update_one(
        {"_id": ObjectId(skill_id), "flag_count": {"$gt": 0}},
        {"$inc": {"flag_count": -1}},
    )


async def resolve_all_for_skill(skill_id: str, resolved_by: str) -> int:
    """Bulk-resolve all active flags for a skill. Hard-resets flag_count to 0."""
    now = datetime.now(timezone.utc)
    collection = SkillFlag.get_motor_collection()
    result = await collection.update_many(
        {"skill_id": skill_id, "status": FlagStatus.active.value},
        {
            "$set": {
                "status": FlagStatus.resolved.value,
                "resolved_by": resolved_by,
                "resolved_at": now,
            }
        },
    )
    # Hard-reset flag_count to 0 — idempotent, avoids TOCTOU vs $inc
    await Skill.find_one(Skill.id == ObjectId(skill_id)).update(
        {"$set": {"flag_count": 0}}
    )
    return result.modified_count


async def get_my_flag(skill_id: str, reporter_id: str) -> Optional[SkillFlag]:
    return await SkillFlag.find_one(
        SkillFlag.skill_id == skill_id,
        SkillFlag.reporter_id == reporter_id,
    )


async def list_flagged_skills(
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[FlaggedSkillSummary], int]:
    """Return active skills with flag_count >= 1, sorted by flag_count desc."""
    skip = (page - 1) * page_size

    flagged = (
        await Skill.find(
            Skill.flag_count >= 1,
            Skill.status == SkillStatus.active,
        )
        .sort(-Skill.flag_count)
        .skip(skip)
        .limit(page_size)
        .to_list()
    )

    total = await Skill.find(
        Skill.flag_count >= 1,
        Skill.status == SkillStatus.active,
    ).count()

    items = []
    for skill in flagged:
        flags_docs = await SkillFlag.find(
            SkillFlag.skill_id == str(skill.id),
            SkillFlag.status == FlagStatus.active,
        ).to_list()

        flag_outs = [
            AdminFlagOut(
                reason=f.reason,
                note=f.note,
                status=f.status,
                created_at=f.created_at,
                reporter_id=f.reporter_id,
                resolved_by=f.resolved_by,
                resolution_note=f.resolution_note,
            )
            for f in flags_docs
        ]
        items.append(
            FlaggedSkillSummary(
                skill_slug=skill.slug,
                skill_name=skill.name,
                flag_count=skill.flag_count,
                flags=flag_outs,
            )
        )

    return items, total
