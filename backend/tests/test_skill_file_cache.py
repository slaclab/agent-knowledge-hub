"""Tests for #018 — skill file cache (skill_md_raw, readme_raw) and auth gate."""
import base64

import httpx
import pytest
import respx

from app.models.skill import Skill, VisibilityEnum
from app.routers.skills import _skill_to_out
from app.schemas.skill import SkillCreate
from app.services.skill import skill_repository


# ---------------------------------------------------------------------------
# GitHub Contents API helpers
# ---------------------------------------------------------------------------

def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


FAKE_REPO = {
    "name": "my-skill",
    "description": "A skill",
    "stargazers_count": 5,
    "pushed_at": "2024-01-01T00:00:00Z",
    "default_branch": "main",
    "visibility": "public",
    "private": False,
    "fork": False,
}

FAKE_DIR_LISTING = [
    {
        "name": "SKILL.md",
        "type": "file",
        "download_url": "https://raw.githubusercontent.com/ex/repo/main/SKILL.md",
    },
    {
        "name": "README.md",
        "type": "file",
        "download_url": "https://raw.githubusercontent.com/ex/repo/main/README.md",
    },
]

SKILL_MD_CONTENT = "---\nname: my-skill\ndescription: Does things.\n---\n\n# My Skill\n"
README_CONTENT = "# My Skill\n\nThis is the README."


# ---------------------------------------------------------------------------
# create() — populates file content from scan
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_create_populates_skill_md_raw():
    """skill_md_raw and skill_md_filename are set when SKILL.md is found."""
    _mock_github_for_create()

    data = SkillCreate(repo_url="https://github.com/ex/repo", name="my-skill")
    skill = await skill_repository.create(data, submitter_id="alice")

    assert skill.skill_md_raw == SKILL_MD_CONTENT
    assert skill.skill_md_filename == "SKILL.md"


@pytest.mark.asyncio
@respx.mock
async def test_create_populates_readme_raw():
    """readme_raw is set to README.md content when present."""
    _mock_github_for_create()

    data = SkillCreate(repo_url="https://github.com/ex/repo", name="my-skill")
    skill = await skill_repository.create(data, submitter_id="alice")

    assert skill.readme_raw == README_CONTENT


@pytest.mark.asyncio
@respx.mock
async def test_create_no_skill_files_leaves_fields_null():
    """If skill_path dir has no recognised files, fields stay None."""
    respx.get("https://api.github.com/repos/ex/empty").mock(
        return_value=httpx.Response(200, json={**FAKE_REPO, "name": "empty"})
    )
    respx.get("https://api.github.com/repos/ex/empty/readme").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.github.com/repos/ex/empty/contents/").mock(
        return_value=httpx.Response(200, json=[])  # empty directory
    )

    data = SkillCreate(repo_url="https://github.com/ex/empty", name="empty-skill")
    skill = await skill_repository.create(data, submitter_id="alice")

    assert skill.skill_md_raw is None
    assert skill.skill_md_filename is None
    assert skill.readme_raw is None


@pytest.mark.asyncio
@respx.mock
async def test_create_skill_md_capped_at_100kb():
    """skill_md_raw is capped at 100 000 characters."""
    large_content = "x" * 200_000

    respx.get("https://api.github.com/repos/ex/big").mock(
        return_value=httpx.Response(200, json={**FAKE_REPO, "name": "big"})
    )
    respx.get("https://api.github.com/repos/ex/big/readme").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.github.com/repos/ex/big/contents/").mock(
        return_value=httpx.Response(200, json=[{
            "name": "SKILL.md",
            "type": "file",
            "download_url": "https://raw.githubusercontent.com/ex/big/main/SKILL.md",
        }])
    )
    respx.get("https://raw.githubusercontent.com/ex/big/main/SKILL.md").mock(
        return_value=httpx.Response(200, text=large_content)
    )

    data = SkillCreate(repo_url="https://github.com/ex/big", name="big-skill")
    skill = await skill_repository.create(data, submitter_id="alice")

    assert skill.skill_md_raw is not None
    assert len(skill.skill_md_raw) == 100_000


# ---------------------------------------------------------------------------
# refetch() — updates readme_raw
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_refetch_updates_readme_raw():
    """refetch() updates readme_raw to the latest README content."""
    _mock_github_for_create()
    data = SkillCreate(repo_url="https://github.com/ex/repo", name="my-skill")
    skill = await skill_repository.create(data, submitter_id="alice")

    # Now mock a new README for refetch
    updated_readme = "# My Skill\n\nUpdated README content."
    _mock_github_for_refetch(updated_readme)

    refetched = await skill_repository.refetch(skill, actor_id="alice")

    assert refetched.readme_raw == updated_readme


@pytest.mark.asyncio
@respx.mock
async def test_refetch_does_not_overwrite_skill_md_raw():
    """refetch() leaves skill_md_raw untouched (only pin() should update it)."""
    _mock_github_for_create()
    data = SkillCreate(repo_url="https://github.com/ex/repo", name="my-skill")
    skill = await skill_repository.create(data, submitter_id="alice")
    original_skill_md = skill.skill_md_raw

    _mock_github_for_refetch("Updated README.")

    refetched = await skill_repository.refetch(skill, actor_id="alice")

    assert refetched.skill_md_raw == original_skill_md


# ---------------------------------------------------------------------------
# Auth gate — _skill_to_out with omit_content
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_auth_gate_omits_content_for_internal_unauthenticated():
    """omit_content=True nulls out all four file content fields."""
    _mock_github_for_create()
    data = SkillCreate(repo_url="https://github.com/ex/repo", name="my-skill")
    skill = await skill_repository.create(data, submitter_id="alice")
    skill.visibility = VisibilityEnum.internal
    skill.readme_html = "<h1>README</h1>"

    out = _skill_to_out(skill, omit_content=True)

    assert out.readme_html is None
    assert out.readme_raw is None
    assert out.skill_md_raw is None
    assert out.skill_md_filename is None


@pytest.mark.asyncio
@respx.mock
async def test_auth_gate_includes_content_for_internal_authenticated():
    """omit_content=False (authenticated) preserves file content fields."""
    _mock_github_for_create()
    data = SkillCreate(repo_url="https://github.com/ex/repo", name="my-skill")
    skill = await skill_repository.create(data, submitter_id="alice")
    skill.visibility = VisibilityEnum.internal
    skill.readme_html = "<h1>README</h1>"

    out = _skill_to_out(skill, omit_content=False)

    assert out.readme_html == "<h1>README</h1>"
    assert out.readme_raw == README_CONTENT
    assert out.skill_md_raw == SKILL_MD_CONTENT
    assert out.skill_md_filename == "SKILL.md"


@pytest.mark.asyncio
@respx.mock
async def test_auth_gate_public_skill_always_includes_content():
    """Public skills return content regardless of auth state."""
    _mock_github_for_create()
    data = SkillCreate(repo_url="https://github.com/ex/repo", name="my-skill")
    skill = await skill_repository.create(data, submitter_id="alice")
    # visibility defaults to public

    out = _skill_to_out(skill, omit_content=False)

    assert out.readme_raw == README_CONTENT
    assert out.skill_md_raw == SKILL_MD_CONTENT


# ---------------------------------------------------------------------------
# Snapshot includes file content — diff via revision history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_create_revision_snapshot_includes_file_content():
    """Revision snapshot created at registration includes skill_md_raw and readme_raw."""
    from app.models.revision import SkillRevision

    _mock_github_for_create()
    data = SkillCreate(repo_url="https://github.com/ex/repo", name="my-skill")
    skill = await skill_repository.create(data, submitter_id="alice")

    revs = await SkillRevision.find(SkillRevision.skill_id == str(skill.id)).to_list()
    assert len(revs) == 1
    snapshot = revs[0].snapshot
    assert snapshot.get("skill_md_raw") == SKILL_MD_CONTENT
    assert snapshot.get("readme_raw") == README_CONTENT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_github_for_create() -> None:
    respx.get("https://api.github.com/repos/ex/repo").mock(
        return_value=httpx.Response(200, json=FAKE_REPO)
    )
    respx.get("https://api.github.com/repos/ex/repo/readme").mock(
        return_value=httpx.Response(200, text="<h1>Readme</h1>")
    )
    respx.get("https://api.github.com/repos/ex/repo/contents/").mock(
        return_value=httpx.Response(200, json=FAKE_DIR_LISTING)
    )
    respx.get("https://raw.githubusercontent.com/ex/repo/main/SKILL.md").mock(
        return_value=httpx.Response(200, text=SKILL_MD_CONTENT)
    )
    respx.get("https://raw.githubusercontent.com/ex/repo/main/README.md").mock(
        return_value=httpx.Response(200, text=README_CONTENT)
    )


def _mock_github_for_refetch(updated_readme: str) -> None:
    respx.get("https://api.github.com/repos/ex/repo").mock(
        return_value=httpx.Response(200, json=FAKE_REPO)
    )
    respx.get("https://api.github.com/repos/ex/repo/readme").mock(
        return_value=httpx.Response(200, text="<h1>Updated</h1>")
    )
    respx.get("https://api.github.com/repos/ex/repo/contents/").mock(
        return_value=httpx.Response(200, json=FAKE_DIR_LISTING)
    )
    respx.get("https://raw.githubusercontent.com/ex/repo/main/SKILL.md").mock(
        return_value=httpx.Response(200, text=SKILL_MD_CONTENT)
    )
    respx.get("https://raw.githubusercontent.com/ex/repo/main/README.md").mock(
        return_value=httpx.Response(200, text=updated_readme)
    )
