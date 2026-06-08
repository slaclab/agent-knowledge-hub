"""Tests for #014 — Skill Provenance Tree."""
from __future__ import annotations

import pytest

from app.models.skill import Skill, SkillStatus, VisibilityEnum
from app.schemas.skill import SkillCreate
from app.services.skill import skill_repository
from app.services.provenance import build_tree


async def _make_skill(repo_url: str, name: str, forked_from_url: str | None = None,
                      superseded_by_slug: str | None = None,
                      visibility: VisibilityEnum = VisibilityEnum.public,
                      source_type: str = "github") -> Skill:
    """Helper: create a skill with optional fork/supersession links directly in DB."""
    data = SkillCreate(repo_url=repo_url, name=name)
    skill = await skill_repository.create(data, submitter_id="alice")
    if forked_from_url or superseded_by_slug or visibility != VisibilityEnum.public or source_type != "github":
        if forked_from_url:
            skill.forked_from_url = forked_from_url
        if superseded_by_slug:
            skill.superseded_by_slug = superseded_by_slug
        skill.visibility = visibility
        skill.source_type = source_type
        await skill.save()
    return skill


# ---------------------------------------------------------------------------
# P1 — upstream chain: catalog skill
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_upstream_catalog_skill():
    upstream_skill = await _make_skill("https://github.com/org/original", "Original")
    fork_skill = await _make_skill(
        "https://github.com/org/fork",
        "Fork",
        forked_from_url="https://github.com/org/original",
    )
    tree = await build_tree(fork_skill, viewer_authenticated=True)
    assert not tree.empty
    assert len(tree.upstream) == 1
    assert tree.upstream[0].slug == upstream_skill.slug
    assert tree.upstream[0].in_catalog is True


# ---------------------------------------------------------------------------
# P2 — upstream chain: depth cap at 3 hops
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_upstream_depth_cap():
    urls = [f"https://github.com/org/skill-{i}" for i in range(5)]
    skills = []
    for i, url in enumerate(urls):
        parent_url = urls[i - 1] if i > 0 else None
        s = await _make_skill(url, f"Skill{i}", forked_from_url=parent_url)
        skills.append(s)

    # skills[4] forks skills[3] forks skills[2] forks skills[1] forks skills[0]
    deepest = skills[4]
    tree = await build_tree(deepest, viewer_authenticated=True)
    # Should get at most 3 upstream hops
    assert len(tree.upstream) <= 3


# ---------------------------------------------------------------------------
# P3 — upstream cycle detection
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_upstream_cycle_detection():
    s1 = await _make_skill("https://github.com/org/a", "A")
    s2 = await _make_skill(
        "https://github.com/org/b", "B",
        forked_from_url="https://github.com/org/a",
    )
    # Manually create a cycle: A.forked_from_url → B
    s1.forked_from_url = "https://github.com/org/b"
    await s1.save()

    tree = await build_tree(s2, viewer_authenticated=True)
    # Should terminate without infinite loop; upstream should be at most 1 (A stops at B which is visited)
    assert len(tree.upstream) <= 2


# ---------------------------------------------------------------------------
# P4 — fork tree basic (level 1 + level 2)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fork_tree_two_levels():
    root = await _make_skill("https://github.com/org/root", "Root")
    fork1 = await _make_skill(
        "https://github.com/org/fork1", "Fork1",
        forked_from_url="https://github.com/org/root",
    )
    fork2 = await _make_skill(
        "https://github.com/org/fork2", "Fork2",
        forked_from_url="https://github.com/org/fork1",
    )
    tree = await build_tree(root, viewer_authenticated=True)
    assert not tree.empty
    assert len(tree.subject.forks) == 1
    assert tree.subject.forks[0].slug == fork1.slug
    assert len(tree.subject.forks[0].forks) == 1
    assert tree.subject.forks[0].forks[0].slug == fork2.slug


# ---------------------------------------------------------------------------
# P5 — empty tree (no upstream, no forks, no supersession)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_tree():
    orphan = await _make_skill("https://github.com/org/orphan", "Orphan")
    tree = await build_tree(orphan, viewer_authenticated=True)
    assert tree.empty is True
    assert tree.subject is not None
    assert tree.subject.slug == orphan.slug


# ---------------------------------------------------------------------------
# P6 — supersession chain
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_supersession_chain():
    s_a = await _make_skill("https://github.com/org/sa", "SA")
    s_b = await _make_skill("https://github.com/org/sb", "SB")
    s_c = await _make_skill("https://github.com/org/sc", "SC")
    # A superseded by B, B superseded by C
    s_a.superseded_by_slug = s_b.slug
    await s_a.save()
    s_b.superseded_by_slug = s_c.slug
    await s_b.save()

    tree = await build_tree(s_a, viewer_authenticated=True)
    assert len(tree.supersession) == 2
    assert tree.supersession[0].slug == s_b.slug
    assert tree.supersession[1].slug == s_c.slug


# ---------------------------------------------------------------------------
# P7 — supersession cycle detection
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_supersession_cycle_detection():
    s_a = await _make_skill("https://github.com/org/cyc-a", "CycA")
    s_b = await _make_skill("https://github.com/org/cyc-b", "CycB")
    s_a.superseded_by_slug = s_b.slug
    await s_a.save()
    s_b.superseded_by_slug = s_a.slug
    await s_b.save()

    tree = await build_tree(s_a, viewer_authenticated=True)
    # Should stop at B (A is in visited set)
    assert len(tree.supersession) == 1
    assert tree.supersession[0].slug == s_b.slug


# ---------------------------------------------------------------------------
# P8 — internal skill redacted for unauthenticated viewer
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_internal_skill_redacted_for_unauthenticated():
    internal = await _make_skill(
        "https://github.com/org/internal-root", "InternalRoot",
        visibility=VisibilityEnum.internal,
    )
    fork = await _make_skill(
        "https://github.com/org/public-fork", "PublicFork",
        forked_from_url="https://github.com/org/internal-root",
    )
    tree = await build_tree(fork, viewer_authenticated=False)
    upstream = tree.upstream
    assert len(upstream) == 1
    assert upstream[0].slug is None
    assert upstream[0].name == "[internal skill]"
    assert upstream[0].visibility == "internal"


# ---------------------------------------------------------------------------
# P9 — internal skill NOT redacted for authenticated viewer
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_internal_skill_visible_for_authenticated():
    internal = await _make_skill(
        "https://github.com/org/internal-root2", "InternalRoot2",
        visibility=VisibilityEnum.internal,
    )
    fork = await _make_skill(
        "https://github.com/org/public-fork2", "PublicFork2",
        forked_from_url="https://github.com/org/internal-root2",
    )
    tree = await build_tree(fork, viewer_authenticated=True)
    upstream = tree.upstream
    assert len(upstream) == 1
    assert upstream[0].slug == internal.slug
    assert upstream[0].name == "InternalRoot2"


# ---------------------------------------------------------------------------
# P10 — local source_type skill excluded from upstream matching
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_local_skill_excluded_from_upstream():
    local_skill = await _make_skill(
        "local://some-path", "LocalSkill", source_type="local"
    )
    # A skill whose forked_from_url matches a local:// URL — should not resolve
    fork = await _make_skill(
        "https://github.com/org/unresolved-fork", "UnresolvedFork",
        forked_from_url="local://some-path",
    )
    tree = await build_tree(fork, viewer_authenticated=True)
    # No catalog match because local skills are excluded
    assert len(tree.upstream) == 0 or (
        len(tree.upstream) == 1 and tree.upstream[0].in_catalog is False
    )


# ---------------------------------------------------------------------------
# P11 — forks_truncated when more than MAX_FORKS_DISPLAY forks exist
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_forks_truncated_flag():
    root = await _make_skill("https://github.com/org/popular", "Popular")
    # Create 7 forks (more than MAX_FORKS_DISPLAY=5)
    for i in range(7):
        await _make_skill(
            f"https://github.com/org/popular-fork-{i}", f"Fork{i}",
            forked_from_url="https://github.com/org/popular",
        )
    tree = await build_tree(root, viewer_authenticated=True)
    assert tree.subject.total_fork_count == 7
    assert tree.subject.forks_truncated is True


# ---------------------------------------------------------------------------
# P12 — upstream resolution prefers root skill_path="/" over subdirectory
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_upstream_prefers_root_skill_path():
    # Two skills same repo_url: one at "/" and one at "/subdir"
    root_skill = await skill_repository.create(
        SkillCreate(repo_url="https://github.com/org/multi-path", name="RootPath"),
        submitter_id="alice",
    )
    # Directly insert a subdir skill
    sub_skill = Skill(
        slug="sub-path",
        name="SubPath",
        repo_url="https://github.com/org/multi-path",
        skill_path="/subdir",
        submitter_id="alice",
    )
    await sub_skill.insert()

    fork = await _make_skill(
        "https://github.com/org/fork-mp", "ForkMP",
        forked_from_url="https://github.com/org/multi-path",
    )
    tree = await build_tree(fork, viewer_authenticated=True)
    assert len(tree.upstream) == 1
    assert tree.upstream[0].slug == root_skill.slug  # prefers root path
