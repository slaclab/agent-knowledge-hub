"""Tests for local skill submission (source_type='local').

Covers POST /api/skills with snapshotted_files — no GitHub calls made.
"""

import pytest

from app.schemas.skill import SkillCreate
from app.services.skill import skill_repository


SKILL_MD = "---\nname: my-local-skill\ndescription: A locally submitted skill.\n---\n\n# My Local Skill\n"
README = "# My Local Skill\n\nThis is the README."


# ---------------------------------------------------------------------------
# SkillCreate schema
# ---------------------------------------------------------------------------

def test_skill_create_defaults_source_type_github():
    data = SkillCreate(repo_url="https://github.com/ex/repo", name="test")
    assert data.source_type == "github"


def test_skill_create_accepts_local_source_type():
    data = SkillCreate(
        repo_url="local:///home/user/my-skill",
        source_type="local",
        snapshotted_files={"SKILL.md": SKILL_MD},
        name="my-local-skill",
    )
    assert data.source_type == "local"
    assert "SKILL.md" in data.snapshotted_files


# ---------------------------------------------------------------------------
# skill_repository.create() with source_type='local'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_local_create_extracts_name_from_skill_md():
    """Name is extracted from SKILL.md frontmatter, no GitHub call needed."""
    data = SkillCreate(
        repo_url="local:///home/user/my-skill",
        source_type="local",
        snapshotted_files={
            "SKILL.md": SKILL_MD,
            "README.md": README,
        },
    )
    skill = await skill_repository.create(data, submitter_id="alice")
    assert skill.name == "my-local-skill"
    assert skill.source_type == "local"


@pytest.mark.asyncio
async def test_local_create_populates_skill_md_raw():
    data = SkillCreate(
        repo_url="local:///home/user/my-skill2",
        source_type="local",
        snapshotted_files={"SKILL.md": SKILL_MD},
    )
    skill = await skill_repository.create(data, submitter_id="alice")
    assert skill.skill_md_raw == SKILL_MD
    assert skill.skill_md_filename == "SKILL.md"


@pytest.mark.asyncio
async def test_local_create_populates_readme_raw():
    data = SkillCreate(
        repo_url="local:///home/user/my-skill3",
        source_type="local",
        snapshotted_files={"SKILL.md": SKILL_MD, "README.md": README},
    )
    skill = await skill_repository.create(data, submitter_id="alice")
    assert skill.readme_raw == README


@pytest.mark.asyncio
async def test_local_create_stores_snapshotted_files():
    data = SkillCreate(
        repo_url="local:///home/user/my-skill4",
        source_type="local",
        snapshotted_files={"SKILL.md": SKILL_MD, "README.md": README},
    )
    skill = await skill_repository.create(data, submitter_id="alice")
    assert skill.snapshotted_files == {"SKILL.md": SKILL_MD, "README.md": README}


@pytest.mark.asyncio
async def test_local_create_makes_no_github_calls():
    """No respx mock needed — confirms no HTTP calls are made for local submissions."""
    data = SkillCreate(
        repo_url="local:///home/user/my-skill5",
        source_type="local",
        snapshotted_files={"SKILL.md": SKILL_MD},
    )
    # If any GitHub HTTP call is made this will raise a connection error in test env
    skill = await skill_repository.create(data, submitter_id="alice")
    assert skill.source_type == "local"


@pytest.mark.asyncio
async def test_local_create_uses_name_arg_when_no_frontmatter():
    """Falls back to data.name when SKILL.md has no name in frontmatter."""
    bare_skill_md = "# My Skill\n\nNo frontmatter here."
    data = SkillCreate(
        repo_url="local:///home/user/my-skill6",
        source_type="local",
        name="explicit-name",
        snapshotted_files={"SKILL.md": bare_skill_md},
    )
    skill = await skill_repository.create(data, submitter_id="alice")
    assert skill.name == "explicit-name"


@pytest.mark.asyncio
async def test_local_create_description_from_frontmatter():
    data = SkillCreate(
        repo_url="local:///home/user/my-skill7",
        source_type="local",
        snapshotted_files={"SKILL.md": SKILL_MD},
    )
    skill = await skill_repository.create(data, submitter_id="alice")
    assert skill.description == "A locally submitted skill."
