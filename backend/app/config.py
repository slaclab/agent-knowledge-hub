from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


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

    # Public URL of this instance — used in the marketplace bootstrap plugin entry
    app_url: str = "https://agent-knowledge-hub.slac.stanford.edu"
    # Slug and repo path for the self-hosted bootstrap plugin
    self_plugin_slug: str = "agent-knowledge-hub"
    self_skill_path: str = "skills"

    # Shared secret for Next.js → backend trust; None disables the proxy auth path entirely
    internal_api_secret: Optional[str] = None

    # JWT Bearer auth (Path 3) — CLI tools with SLAC-issued tokens
    # JWKS URI is fetched automatically; keys are cached in memory and refreshed on rotation.
    # Override JWT_JWKS_URI in dev to point at dex-dev.slac.stanford.edu.
    jwt_jwks_uri: str = "https://dex-dev.slac.stanford.edu/keys"
    jwt_algorithm: str = "RS256"
    jwt_issuer: str = "https://dex-dev.slac.stanford.edu"
    # aud claim value — must match what SLAC Dex issues for this application
    jwt_audience: str = "s3df"

    @field_validator("internal_api_secret", mode="before")
    @classmethod
    def _strip_internal_api_secret(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        stripped = str(v).strip()
        return stripped if stripped else None

    @field_validator("jwt_algorithm", mode="before")
    @classmethod
    def _validate_jwt_algorithm(cls, v: object) -> str:
        allowed = {"RS256"}
        val = str(v).strip().upper()
        if val not in allowed:
            raise ValueError(f"jwt_algorithm must be one of {allowed}, got {val!r}")
        return val

    @property
    def admin_user_set(self) -> set[str]:
        return {u.strip() for u in self.admin_users.split(",") if u.strip()}


settings = Settings()
