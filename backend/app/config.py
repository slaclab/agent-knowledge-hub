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

    @property
    def admin_user_set(self) -> set[str]:
        return {u.strip() for u in self.admin_users.split(",") if u.strip()}


settings = Settings()
