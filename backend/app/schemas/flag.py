from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.flag import FlagReason, FlagStatus


class FlagCreate(BaseModel):
    reason: FlagReason
    note: Optional[str] = Field(None, max_length=500)
    superseded_by_slug: Optional[str] = Field(None, max_length=100)


class FlagOut(BaseModel):
    reason: FlagReason
    note: Optional[str] = None
    status: FlagStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminFlagOut(FlagOut):
    reporter_id: str
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None


class FlagResponse(BaseModel):
    flag_count: int
    my_flag: Optional[FlagOut] = None


class RetractResponse(BaseModel):
    flag_count: int


class FlaggedSkillSummary(BaseModel):
    skill_slug: str
    skill_name: str
    flag_count: int
    flags: List[AdminFlagOut]


class PaginatedFlaggedSkills(BaseModel):
    items: List[FlaggedSkillSummary]
    total: int
    page: int
    pages: int


class DeactivateIn(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)
    superseded_by_slug: Optional[str] = Field(None, max_length=100)


class DeactivateOut(BaseModel):
    slug: str
    status: str
    warnings: List[str] = []


class ReactivateIn(BaseModel):
    reason: Optional[str] = Field(None, max_length=1000)


class ReactivateOut(BaseModel):
    slug: str
    status: str
