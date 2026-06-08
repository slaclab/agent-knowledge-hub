from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from app.models.revision import RevisionAction, SkillRevision
from app.models.skill import Skill, SkillStatus


class UserActivityService:
    async def get_submitted(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Skill], int]:
        query = Skill.find(
            Skill.submitter_id == user_id,
            Skill.status == SkillStatus.active,
        )
        total = await query.count()
        items = (
            await query.sort([("submitted_at", -1)])
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list()
        )
        return items, total

    async def get_edited(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Skill], int]:
        """Return skills where user_id has at least one edit/refetch revision.

        Uses two parallel aggregation pipelines (count + items) because $count
        collapses the stream and cannot coexist with $skip/$limit in one pipeline.
        """
        edit_actions = [RevisionAction.edit.value, RevisionAction.refetch.value]
        collection = SkillRevision.get_motor_collection()

        match_stage = {"$match": {"actor_id": user_id, "action": {"$in": edit_actions}}}
        group_stage = {"$group": {"_id": "$skill_id"}}

        # Count pipeline
        count_pipeline = [match_stage, group_stage, {"$count": "total"}]
        count_cursor = collection.aggregate(count_pipeline)
        count_docs = [doc async for doc in count_cursor]
        total = count_docs[0]["total"] if count_docs else 0

        if total == 0:
            return [], 0

        # Items pipeline — sort by most recently edited (max created_at per skill)
        items_pipeline = [
            match_stage,
            {"$group": {"_id": "$skill_id", "last_edited": {"$max": "$created_at"}}},
            {"$sort": {"last_edited": -1}},
            {"$skip": (page - 1) * page_size},
            {"$limit": page_size},
        ]
        items_cursor = collection.aggregate(items_pipeline)
        skill_ids = [doc["_id"] async for doc in items_cursor]

        if not skill_ids:
            return [], total

        skills = await Skill.find(
            {"_id": {"$in": [__import__("bson").ObjectId(sid) for sid in skill_ids]}},
            Skill.status == SkillStatus.active,
        ).to_list()

        # Preserve sort order from aggregation
        skill_map = {str(s.id): s for s in skills}
        ordered = [skill_map[sid] for sid in skill_ids if sid in skill_map]
        return ordered, total

    async def get_summary(
        self,
        user_id: str,
        viewer_id: Optional[str],
        viewer_is_admin: bool,
    ) -> dict:
        submitted_query = Skill.find(
            Skill.submitter_id == user_id,
            Skill.status == SkillStatus.active,
        )
        submitted_count = await submitted_query.count()

        edit_actions = [RevisionAction.edit.value, RevisionAction.refetch.value]
        collection = SkillRevision.get_motor_collection()
        count_cursor = collection.aggregate([
            {"$match": {"actor_id": user_id, "action": {"$in": edit_actions}}},
            {"$group": {"_id": "$skill_id"}},
            {"$count": "total"},
        ])
        count_docs = [doc async for doc in count_cursor]
        edited_count = count_docs[0]["total"] if count_docs else 0

        summary: dict = {
            "user_id": user_id,
            "submitted_count": submitted_count,
            "edited_count": edited_count,
        }

        is_self = viewer_id == user_id
        if is_self or viewer_is_admin:
            from app.models.install_event import SkillInstallEvent
            install_count = await SkillInstallEvent.find(
                SkillInstallEvent.user_id == user_id
            ).count()
            summary["install_count"] = install_count

        return summary


user_activity_service = UserActivityService()
