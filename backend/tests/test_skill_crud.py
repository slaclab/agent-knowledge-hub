import pytest

from app.models.skill import Skill, SkillStatus
from app.models.revision import SkillRevision
from app.schemas.skill import SkillCreate, SkillUpdate
from app.services.skill import skill_repository


@pytest.mark.asyncio
async def test_create_skill_no_github():
    """Creates a skill when GitHub fetch is unavailable (name provided manually)."""
    data = SkillCreate(repo_url="https://github.com/example/fake-repo", name="My Skill")
    skill = await skill_repository.create(data, submitter_id="alice")
    assert skill.slug == "my-skill"
    assert skill.name == "My Skill"
    assert skill.submitter_id == "alice"
    # A revision should have been recorded
    revs = await SkillRevision.find(SkillRevision.skill_id == str(skill.id)).to_list()
    assert len(revs) == 1
    assert revs[0].action == "create"
    assert revs[0].actor_id == "alice"


@pytest.mark.asyncio
async def test_create_skill_slug_collision():
    """Second skill with same slugified name gets a numeric suffix."""
    d1 = SkillCreate(repo_url="https://github.com/a/foo", name="Foo")
    d2 = SkillCreate(repo_url="https://github.com/b/foo", name="Foo")
    s1 = await skill_repository.create(d1, submitter_id="alice")
    s2 = await skill_repository.create(d2, submitter_id="bob")
    assert s1.slug == "foo"
    assert s2.slug == "foo-2"


@pytest.mark.asyncio
async def test_list_skills_pagination():
    for i in range(5):
        await skill_repository.create(
            SkillCreate(repo_url=f"https://github.com/x/skill-{i}", name=f"Skill {i}"),
            submitter_id="alice",
        )
    items, total = await skill_repository.list(page=1, page_size=3)
    assert total == 5
    assert len(items) == 3


@pytest.mark.asyncio
async def test_get_skill():
    data = SkillCreate(repo_url="https://github.com/x/get-test", name="Get Test")
    skill = await skill_repository.create(data, submitter_id="alice")
    found = await skill_repository.get(skill.slug)
    assert found is not None
    assert found.slug == skill.slug


@pytest.mark.asyncio
async def test_get_deactivated_skill_hidden():
    """get() hides deactivated skills unless include_deactivated=True."""
    data = SkillCreate(repo_url="https://github.com/x/deact", name="Deact")
    skill = await skill_repository.create(data, submitter_id="alice")
    skill.status = SkillStatus.deactivated
    skill.deactivation_reason = "test"
    await skill.save()

    assert await skill_repository.get(skill.slug) is None
    assert await skill_repository.get(skill.slug, include_deactivated=True) is not None


@pytest.mark.asyncio
async def test_update_skill_records_revision():
    data = SkillCreate(repo_url="https://github.com/x/upd", name="Update Me")
    skill = await skill_repository.create(data, submitter_id="alice")

    update = SkillUpdate(description="New description", changelog_note="Added description")
    updated = await skill_repository.update(skill, update, actor_id="alice")

    assert updated.description == "New description"
    revs = await SkillRevision.find(SkillRevision.skill_id == str(skill.id)).to_list()
    assert len(revs) == 2
    assert revs[1].action == "edit"
    assert revs[1].changelog_note == "Added description"


@pytest.mark.asyncio
async def test_delete_skill():
    data = SkillCreate(repo_url="https://github.com/x/del", name="Delete Me")
    skill = await skill_repository.create(data, submitter_id="alice")
    await skill_repository.delete(skill)
    assert await skill_repository.get(skill.slug) is None
