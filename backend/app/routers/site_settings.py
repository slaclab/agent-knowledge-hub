from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, HttpUrl, field_validator

from app.config import settings as app_settings
from app.models.settings import SiteSettings

router = APIRouter(prefix="/api/settings")


class SiteSettingsOut(BaseModel):
    github_access_instructions_url: str


class SiteSettingsUpdate(BaseModel):
    github_access_instructions_url: str

    @field_validator("github_access_instructions_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        # Pydantic HttpUrl validation
        HttpUrl(v)
        return v


@router.get("", response_model=SiteSettingsOut)
async def get_settings() -> SiteSettingsOut:
    doc = await SiteSettings.find_one()
    url = (
        doc.github_access_instructions_url
        if doc and doc.github_access_instructions_url
        else app_settings.github_access_instructions_url
    )
    return SiteSettingsOut(github_access_instructions_url=url)
