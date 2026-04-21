from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017/agent-skills"
    github_api_url: str = "https://api.github.com"
    github_token: Optional[str] = None

    # "vouchproxy" | "dev"
    auth_mode: str = "vouchproxy"
    # Used when auth_mode=dev; value becomes the authenticated user identity
    dev_user: Optional[str] = None

    # Comma-separated list of SLAC usernames with admin rights
    admin_users: str = ""

    # GitHub App credentials (optional; enables private/internal repo support)
    github_app_id: Optional[str] = None
    github_app_private_key: Optional[str] = None

    # Comma-separated GitHub orgs known to be private (skip unauthenticated fallback)
    github_private_orgs: str = "slaclab"

    # URL shown in "SLAC Members Only" badge; configurable by admin
    github_access_instructions_url: str = "/guides/slac-github-access"

    @property
    def admin_user_set(self) -> set[str]:
        return {u.strip() for u in self.admin_users.split(",") if u.strip()}


settings = Settings()
