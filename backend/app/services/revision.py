from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.models.revision import RevisionAction, SkillRevision

_LARGE_FIELDS = {"snapshotted_files", "readme_html", "readme_raw", "skill_md_raw"}


class RevisionService:
    async def record(
        self,
        skill_id: str,
        actor_id: str,
        action: RevisionAction,
        snapshot: Dict[str, Any],
        changelog_note: str | None = None,
        labels: Optional[List[str]] = None,
    ) -> SkillRevision:
        # Embed current labels and strip large fields before persisting
        clean: Dict[str, Any] = {k: v for k, v in snapshot.items() if k not in _LARGE_FIELDS}
        if labels is not None:
            clean["labels"] = labels
        count = await SkillRevision.find(SkillRevision.skill_id == skill_id).count()
        rev = SkillRevision(
            skill_id=skill_id,
            revision_number=count + 1,
            snapshot=clean,
            actor_id=actor_id,
            action=action,
            changelog_note=changelog_note,
        )
        await rev.insert()
        return rev


revision_service = RevisionService()
