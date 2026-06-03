from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, Optional

from beanie import Document, Link
from pydantic import Field


class RevisionAction(str, enum.Enum):
    create = "create"
    edit = "edit"
    refetch = "refetch"
    deactivate = "deactivate"
    reactivate = "reactivate"
    pin = "pin"


class SkillRevision(Document):
    skill_id: str  # stringified ObjectId of the parent Skill
    revision_number: int
    snapshot: Dict[str, Any]
    actor_id: str
    action: RevisionAction
    changelog_note: Optional[str] = None  # max 280 chars
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "skill_revisions"
        indexes = [
            [("skill_id", 1), ("revision_number", 1)],
        ]
