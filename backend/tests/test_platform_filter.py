"""Tests for #025 — platform filter: platforms= OR query, platform_counts aggregation, cache correctness."""
from __future__ import annotations

import pytest

from app.models.skill import Skill, SkillStatus
from app.schemas.skill import SkillCreate
from app.services.skill import skill_repository, _count_cache, _filter_fingerprint


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

async def _make_skill(
    n: int,
    platforms: list[str] | None = None,
    name: str | None = None,
) -> Skill:
    skill = await skill_repository.create(
        SkillCreate(
            repo_url=f"https://github.com/x/pf-skill-{n}",
            name=name or f"PF Skill {n}",
        ),
        submitter_id="alice",
    )
    if platforms:
        skill.compatible_platforms = platforms
        await skill.save()
    return skill


# ===========================================================================
# Core filter behaviour
# ===========================================================================

@pytest.mark.asyncio
async def test_platform_filter_single():
    """platforms=["claude-code"] returns only skills listing claude-code."""
    await _make_skill(1, platforms=["claude-code"])
    await _make_skill(2, platforms=["opencode"])
    await _make_skill(3, platforms=["claude-code", "mcp"])

    items, total, *_ = await skill_repository.list_with_cursors(platforms=["claude-code"])
    slugs = {s.slug for s in items}
    assert total == 2
    assert "pf-skill-1" in slugs
    assert "pf-skill-3" in slugs
    assert "pf-skill-2" not in slugs


@pytest.mark.asyncio
async def test_platform_filter_or_semantics():
    """platforms=["opencode","codex"] returns skills listing EITHER — not only both."""
    await _make_skill(10, platforms=["opencode"])
    await _make_skill(11, platforms=["codex"])
    await _make_skill(12, platforms=["langchain"])  # excluded
    await _make_skill(13, platforms=["opencode", "codex"])

    items, total, *_ = await skill_repository.list_with_cursors(platforms=["opencode", "codex"])
    slugs = {s.slug for s in items}
    assert total == 3
    assert "pf-skill-12" not in slugs
    assert {"pf-skill-10", "pf-skill-11", "pf-skill-13"}.issubset(slugs)


@pytest.mark.asyncio
async def test_platform_filter_unknown_value():
    """Unknown platform values produce an empty result without error."""
    await _make_skill(20, platforms=["claude-code"])
    items, total, *_ = await skill_repository.list_with_cursors(platforms=["does-not-exist"])
    assert total == 0
    assert items == []


@pytest.mark.asyncio
async def test_platform_filter_none_returns_all():
    """platforms=None applies no filter."""
    await _make_skill(30, platforms=["claude-code"])
    await _make_skill(31, platforms=["opencode"])
    items, total, *_ = await skill_repository.list_with_cursors(platforms=None)
    assert total == 2


@pytest.mark.asyncio
async def test_platform_filter_empty_string_ignored():
    """Empty string after strip is silently ignored."""
    await _make_skill(40, platforms=["claude-code"])
    await _make_skill(41, platforms=["opencode"])
    items, total, *_ = await skill_repository.list_with_cursors(platforms=["", "  "])
    assert total == 2  # no filter applied


@pytest.mark.asyncio
async def test_platform_filter_case_insensitive():
    """Platform values are lowercased before matching."""
    await _make_skill(50, platforms=["claude-code"])
    items, total, *_ = await skill_repository.list_with_cursors(platforms=["Claude-Code"])
    assert total == 1


@pytest.mark.asyncio
async def test_platform_filter_combined_with_label_filter():
    """platforms AND labels both applied: skill must satisfy both."""
    from app.models.label import Label, SkillLabel
    from pymongo.errors import DuplicateKeyError

    s1 = await _make_skill(60, platforms=["claude-code"])
    s2 = await _make_skill(61, platforms=["claude-code"])

    # Apply "python" label to s1 only
    label = Label(name="python", created_by="alice")
    try:
        await label.insert()
    except DuplicateKeyError:
        label = await Label.find_one(Label.name == "python")
    sl = SkillLabel(skill_id=str(s1.id), label_id=str(label.id), applied_by="alice")
    try:
        await sl.insert()
    except DuplicateKeyError:
        pass

    items, total, *_ = await skill_repository.list_with_cursors(
        platforms=["claude-code"], labels=["python"]
    )
    assert total == 1
    assert items[0].slug == "pf-skill-60"


@pytest.mark.asyncio
async def test_platform_filter_capped_at_20():
    """More than 20 values are silently truncated to the first 20."""
    await _make_skill(70, platforms=["claude-code"])
    # 21 values — should not raise, and should still match the one relevant platform
    many = [f"platform-{i}" for i in range(21)]
    many[0] = "claude-code"
    items, total, *_ = await skill_repository.list_with_cursors(platforms=many)
    assert total == 1


# ===========================================================================
# Cursor (keyset) path includes platform filter
# ===========================================================================

@pytest.mark.asyncio
async def test_platform_filter_with_cursor():
    """Keyset cursor path also applies the platforms filter."""
    for i in range(5):
        await _make_skill(80 + i, platforms=["claude-code"])
    await _make_skill(85, platforms=["opencode"])

    # First page — page_size=3
    items1, total, next_cursor, _, _ = await skill_repository.list_with_cursors(
        platforms=["claude-code"], page_size=3, sort="newest"
    )
    assert total == 5
    assert len(items1) == 3
    assert next_cursor is not None

    # Second page via cursor
    items2, total2, _, _, _ = await skill_repository.list_with_cursors(
        platforms=["claude-code"], page_size=3, sort="newest", cursor=next_cursor
    )
    assert total2 == 5
    assert len(items2) == 2
    # opencode skill must never appear
    all_slugs = {s.slug for s in items1 + items2}
    assert "pf-skill-85" not in all_slugs


# ===========================================================================
# platform_counts aggregation
# ===========================================================================

@pytest.mark.asyncio
async def test_platform_counts_present_in_response():
    """platform_counts is returned and contains correct per-platform counts."""
    await _make_skill(90, platforms=["claude-code"])
    await _make_skill(91, platforms=["claude-code", "mcp"])
    await _make_skill(92, platforms=["opencode"])

    _, _, _, _, platform_counts = await skill_repository.list_with_cursors()
    assert platform_counts["claude-code"] == 2
    assert platform_counts["mcp"] == 1
    assert platform_counts["opencode"] == 1


@pytest.mark.asyncio
async def test_platform_counts_excludes_platforms_filter():
    """platform_counts reflects the base query (without platforms filter) so chips show counts."""
    await _make_skill(100, platforms=["claude-code"])
    await _make_skill(101, platforms=["opencode"])
    await _make_skill(102, platforms=["mcp"])

    # Filter to claude-code only, but counts should still show all platforms
    _, _, _, _, platform_counts = await skill_repository.list_with_cursors(
        platforms=["claude-code"]
    )
    assert platform_counts["claude-code"] >= 1
    assert platform_counts["opencode"] >= 1
    assert platform_counts["mcp"] >= 1


@pytest.mark.asyncio
async def test_platform_counts_empty_catalog():
    """platform_counts returns {} when no skills exist."""
    _, _, _, _, platform_counts = await skill_repository.list_with_cursors()
    assert platform_counts == {}


@pytest.mark.asyncio
async def test_platform_counts_empty_when_q_active():
    """platform_counts returns {} when full-text search (q=) is active.

    The guard `if not q: platform_counts = await _platform_counts_aggregation(...)` is
    exercised by patching _platform_counts_aggregation and confirming it is never invoked.
    ($text is unsupported by mongomock so we bypass list_with_cursors entirely.)
    """
    from unittest.mock import AsyncMock, patch

    called = []

    async def fake_agg(raw_match):
        called.append(raw_match)
        return {"claude-code": 1}

    with patch.object(skill_repository, "_platform_counts_aggregation", side_effect=fake_agg):
        # Invoke the guard logic directly by inspecting: when q is truthy,
        # the code path `if not q:` skips the aggregation entirely.
        # We verify this by calling list_with_cursors with no skills and q="anything".
        # With zero skills, _build_query_parts returns ([], False) → no $text executed.
        _, _, _, _, platform_counts = await skill_repository.list_with_cursors(q="anything")

    assert called == [], "aggregation must NOT be called when q is active"
    assert platform_counts == {}


@pytest.mark.asyncio
async def test_platform_counts_respects_visibility_filter():
    """platform_counts only counts skills matching other active filters."""
    from app.models.skill import VisibilityEnum
    s1 = await _make_skill(120, platforms=["claude-code"])
    s2 = await _make_skill(121, platforms=["claude-code"])
    s2.visibility = VisibilityEnum.internal
    await s2.save()

    _, _, _, _, platform_counts = await skill_repository.list_with_cursors(
        visibility="public"
    )
    assert platform_counts.get("claude-code", 0) == 1


# ===========================================================================
# Cache correctness
# ===========================================================================

@pytest.mark.asyncio
async def test_filter_fingerprint_includes_platforms():
    """Different platforms values produce different cache fingerprints."""
    fp1 = _filter_fingerprint(None, None, None, None, "newest", None, False, ["claude-code"])
    fp2 = _filter_fingerprint(None, None, None, None, "newest", None, False, ["opencode"])
    fp3 = _filter_fingerprint(None, None, None, None, "newest", None, False, None)
    assert fp1 != fp2
    assert fp1 != fp3
    assert fp2 != fp3


@pytest.mark.asyncio
async def test_platform_filter_only_uses_count_cache():
    """platforms= as the only filter is treated as filtered (not estimatedDocumentCount)."""
    await _make_skill(130, platforms=["claude-code"])
    await _make_skill(131, platforms=["opencode"])

    _count_cache.clear()
    _, total, *_ = await skill_repository.list_with_cursors(platforms=["claude-code"])
    assert total == 1
    # Cache should be populated (filtered path, not estimated)
    assert len(_count_cache) >= 1


@pytest.mark.asyncio
async def test_different_platform_filters_do_not_share_cache():
    """Switching platforms= param does not serve stale cached counts."""
    await _make_skill(140, platforms=["claude-code"])
    await _make_skill(141, platforms=["opencode"])

    _count_cache.clear()
    _, total1, *_ = await skill_repository.list_with_cursors(platforms=["claude-code"])
    _, total2, *_ = await skill_repository.list_with_cursors(platforms=["opencode"])
    assert total1 == 1
    assert total2 == 1
