from __future__ import annotations

from datetime import datetime
from typing import Optional

from beanie import Document
from pydantic import Field


class SiteSettings(Document):
    skill_template_repo_url: Optional[str] = None
    updated_by: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "site_settings"
