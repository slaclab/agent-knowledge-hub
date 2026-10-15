from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.skill import SkillStatus, VisibilityEnum


class SkillsetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: Optional[str] = None  # derived from name when omitted
    description: str = Field(default="", max_length=2000)


class SkillsetUpdate(BaseModel):
    # slug is immutable after creation, so it is not a field here.
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)


class SkillsetOrderIn(BaseModel):
    skill_slugs: List[str]
    version: int


class SkillsetMemberOut(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    labels: List[str] = []
    avg_rating: float = 0.0
    visibility: VisibilityEnum
    status: SkillStatus


class SkillsetListOut(BaseModel):
    slug: str
    name: str
    description: str
    created_by: str
    member_count: int
    created_at: datetime


class SkillsetOut(SkillsetListOut):
    version: int
    skills: List[SkillsetMemberOut]


class PaginatedSkillsets(BaseModel):
    items: List[SkillsetListOut]
    total: int
    page: int
    page_size: int
