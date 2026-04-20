from __future__ import annotations

from typing import Any, Dict

from app.models.revision import RevisionAction, SkillRevision


class RevisionService:
    async def record(
        self,
        skill_id: str,
        actor_id: str,
        action: RevisionAction,
        snapshot: Dict[str, Any],
        changelog_note: str | None = None,
    ) -> SkillRevision:
        count = await SkillRevision.find(SkillRevision.skill_id == skill_id).count()
        rev = SkillRevision(
            skill_id=skill_id,
            revision_number=count + 1,
            snapshot=snapshot,
            actor_id=actor_id,
            action=action,
            changelog_note=changelog_note,
        )
        await rev.insert()
        return rev


revision_service = RevisionService()
