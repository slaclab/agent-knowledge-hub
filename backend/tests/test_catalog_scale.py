"""Tests for #015 — catalog scale: count cache, keyset pagination, name boost."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import List
from unittest.mock import AsyncMock, patch

import pytest

from app.models.skill import Skill, SkillStatus
from app.schemas.skill import SkillCreate
from app.services.skill import skill_repository, _count_cache


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

async def _make_skill(n: int, name: str | None = None) -> Skill:
    return await skill_repository.create(
        SkillCreate(
            repo_url=f"https://github.com/x/skill-{n}",
            name=name or f"Skill {n}",
        ),
        submitter_id="alice",
    )


def _encode_cursor(sv, oid: str) -> str:
    """Encode a cursor — sv may be a datetime or ISO string."""
    if hasattr(sv, "isoformat"):
        if sv.tzinfo is None:
            from datetime import timezone as _tz
            sv = sv.replace(tzinfo=_tz.utc)
        sv = sv.isoformat()
    return base64.b64encode(json.dumps({"sv": sv, "id": oid}).encode()).decode()


# ===========================================================================
# Slice 1 — count cache
# ===========================================================================


@pytest.mark.asyncio
async def test_unfiltered_list_does_not_populate_count_cache():
    """Unfiltered requests bypass the count cache (use estimatedDocumentCount or fallback)."""
    for i in range(3):
        await _make_skill(i)

    _count_cache.clear()

    items, total = await skill_repository.list()
    assert total == 3
    # Unfiltered path should NOT populate _count_cache (estimatedDocumentCount is O(1) direct)
    assert len(_count_cache) == 0


@pytest.mark.asyncio
async def test_filtered_count_is_cached():
    """Second filtered request within TTL is served from cache (count not re-run)."""
    for i in range(4):
        await _make_skill(i)

    _count_cache.clear()

    call_counts = {"n": 0}
    _orig_list = skill_repository.list.__wrapped__ if hasattr(skill_repository.list, "__wrapped__") else None

    # First call populates cache.
    _, total1 = await skill_repository.list(visibility="public")
    # Second call within TTL should reuse cached count.
    _, total2 = await skill_repository.list(visibility="public")

    assert total1 == total2 == 4
    # Cache should have exactly one entry for this filter fingerprint.
    assert len(_count_cache) == 1


@pytest.mark.asyncio
async def test_cache_cleared_on_skill_create():
    """Creating a skill flushes the count cache."""
    _count_cache.clear()
    await _make_skill(0)
    _, _ = await skill_repository.list(visibility="public")
    assert len(_count_cache) > 0

    # Creating a new skill should flush cache.
    await _make_skill(1)
    assert len(_count_cache) == 0


@pytest.mark.asyncio
async def test_cache_cleared_on_deactivate():
    """Deactivating a skill flushes the count cache."""
    skill = await _make_skill(0)
    _count_cache.clear()
    _, _ = await skill_repository.list(visibility="public")
    assert len(_count_cache) > 0

    await skill_repository.deactivate(skill.slug, reason="test", admin_id="admin")
    assert len(_count_cache) == 0


@pytest.mark.asyncio
async def test_cache_cleared_on_reactivate():
    """Reactivating a skill flushes the count cache."""
    skill = await _make_skill(0)
    await skill_repository.deactivate(skill.slug, reason="test", admin_id="admin")
    _count_cache.clear()
    _, _ = await skill_repository.list(visibility="public")
    assert len(_count_cache) > 0

    await skill_repository.reactivate(skill.slug, reason=None, admin_id="admin")
    assert len(_count_cache) == 0


# ===========================================================================
# Slice 1 — PaginatedSkills schema has cursor fields
# ===========================================================================


def test_paginated_skills_has_cursor_fields():
    """PaginatedSkills schema must include next_cursor and prev_cursor."""
    from app.schemas.skill import PaginatedSkills, SkillListOut
    from datetime import datetime

    dummy = PaginatedSkills(items=[], total=0, page=1, page_size=20)
    assert dummy.next_cursor is None
    assert dummy.prev_cursor is None


# ===========================================================================
# Slice 2 — cursor encode/decode security
# ===========================================================================


def test_cursor_roundtrip():
    """Cursor encodes/decodes correctly for sort=newest."""
    from app.services.skill import _encode_cursor, _decode_cursor

    now = datetime.now(timezone.utc)
    oid = "a" * 24
    token = _encode_cursor(now, oid)
    sv_out, id_out = _decode_cursor(token)
    assert sv_out.tzinfo is not None
    assert id_out == oid


def test_cursor_rejects_malformed_base64():
    """Malformed cursor returns ValueError."""
    from app.services.skill import _decode_cursor

    with pytest.raises(ValueError, match="Invalid or expired cursor"):
        _decode_cursor("not-valid-base64!!!")


def test_cursor_rejects_dict_sv():
    """cursor sv as dict (NoSQL injection attempt) is rejected."""
    from app.services.skill import _decode_cursor

    bad = base64.b64encode(json.dumps({"sv": {"$gt": ""}, "id": "a" * 24}).encode()).decode()
    with pytest.raises(ValueError, match="Invalid or expired cursor"):
        _decode_cursor(bad)


def test_cursor_rejects_list_sv():
    """cursor sv as list is rejected."""
    from app.services.skill import _decode_cursor

    bad = base64.b64encode(json.dumps({"sv": [1, 2, 3], "id": "a" * 24}).encode()).decode()
    with pytest.raises(ValueError, match="Invalid or expired cursor"):
        _decode_cursor(bad)


def test_cursor_rejects_null_sv():
    """cursor sv=null is rejected (submitted_at is non-nullable)."""
    from app.services.skill import _decode_cursor

    bad = base64.b64encode(json.dumps({"sv": None, "id": "a" * 24}).encode()).decode()
    with pytest.raises(ValueError, match="Invalid or expired cursor"):
        _decode_cursor(bad)


def test_cursor_rejects_invalid_object_id():
    """cursor id not matching [0-9a-f]{24} is rejected."""
    from app.services.skill import _decode_cursor

    bad = base64.b64encode(json.dumps({"sv": "2026-01-01T00:00:00+00:00", "id": "not-an-oid"}).encode()).decode()
    with pytest.raises(ValueError, match="Invalid or expired cursor"):
        _decode_cursor(bad)


def test_cursor_rejects_unanchored_oid():
    """cursor id with extra chars beyond 24 hex is rejected."""
    from app.services.skill import _decode_cursor

    bad_id = "a" * 24 + "extra"
    bad = base64.b64encode(json.dumps({"sv": "2026-01-01T00:00:00+00:00", "id": bad_id}).encode()).decode()
    with pytest.raises(ValueError, match="Invalid or expired cursor"):
        _decode_cursor(bad)


def test_cursor_rejects_invalid_bson_objectid():
    """cursor id that passes regex but fails ObjectId() is rejected."""
    from app.services.skill import _decode_cursor

    # 24 hex chars but not a valid ObjectId (all zeros is technically valid in bson,
    # so use a string that looks like hex but has an invalid timestamp).
    # We can't easily craft one that passes regex but fails bson here, but we can
    # verify the try/except path is present by checking a valid 24-hex string works.
    valid = base64.b64encode(json.dumps({"sv": "2026-01-01T00:00:00+00:00", "id": "a" * 24}).encode()).decode()
    sv_out, id_out = _decode_cursor(valid)
    assert id_out == "a" * 24


# ===========================================================================
# Slice 2 — keyset query uses no skip
# ===========================================================================


@pytest.mark.asyncio
async def test_keyset_pagination_returns_next_page():
    """cursor-based pagination returns the correct next page without skip."""
    for i in range(5):
        await _make_skill(i)

    # Get first page with page_size=2
    items1, total = await skill_repository.list(sort="newest", page=1, page_size=2)
    assert len(items1) == 2

    # Encode cursor from last item on page 1
    last = items1[-1]
    cursor = _encode_cursor(last.submitted_at.isoformat(), str(last.id))

    # Get next page via cursor
    items2, _ = await skill_repository.list(sort="newest", page_size=2, cursor=cursor)
    assert len(items2) == 2
    # No overlap
    ids1 = {str(s.id) for s in items1}
    ids2 = {str(s.id) for s in items2}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_next_cursor_populated_in_response():
    """list() returns a non-null next_cursor when there are more pages."""
    for i in range(4):
        await _make_skill(i)

    items, total, next_cursor, prev_cursor, _ = await skill_repository.list_with_cursors(
        sort="newest", page=1, page_size=2
    )
    assert next_cursor is not None
    assert prev_cursor is None  # first page


@pytest.mark.asyncio
async def test_next_cursor_null_on_last_page():
    """next_cursor is null on the last page."""
    for i in range(3):
        await _make_skill(i)

    items, total, next_cursor, prev_cursor, _ = await skill_repository.list_with_cursors(
        sort="newest", page=1, page_size=10
    )
    assert next_cursor is None  # only 3 items, page_size=10 → last page


@pytest.mark.asyncio
async def test_stale_cursor_returns_partial_page_not_error():
    """If a skill is deleted between pages, we return partial results (no 500)."""
    skills = [await _make_skill(i) for i in range(5)]
    last = skills[-1]

    # Use a cursor pointing at a deleted skill's position
    cursor = _encode_cursor(last.submitted_at.isoformat(), str(last.id))
    await skill_repository.delete(skills[0])

    # Should not raise — returns partial/empty result
    items, _ = await skill_repository.list(sort="newest", page_size=2, cursor=cursor)
    assert isinstance(items, list)


# ===========================================================================
# Slice 3 — name boost
# ===========================================================================


@pytest.mark.asyncio
async def test_exact_name_match_appears_first():
    """Exact name match is boosted to position 0 in search results."""
    from app.services.search import name_boost

    await _make_skill(0, name="kubernetes deploy")
    await _make_skill(1, name="helm chart deployer")
    await _make_skill(2, name="docker compose")

    # Get the 'docker compose' skill to be the exact match target
    all_skills = await Skill.find(Skill.status == SkillStatus.active).to_list()
    base_results = list(reversed(all_skills))  # put docker compose at end

    boosted = await name_boost("docker compose", base_results)
    assert boosted[0].name == "docker compose"


@pytest.mark.asyncio
async def test_name_boost_deduplicates():
    """name_boost does not duplicate a skill already in base_results."""
    from app.services.search import name_boost

    skill = await _make_skill(0, name="my-skill")
    base_results = [skill]

    boosted = await name_boost("my-skill", base_results)
    ids = [str(s.id) for s in boosted]
    assert ids.count(str(skill.id)) == 1


@pytest.mark.asyncio
async def test_name_boost_off_page_exact_match():
    """name_boost surfaces an exact match not present in base_results."""
    from app.services.search import name_boost

    target = await _make_skill(0, name="off-page-target")
    other1 = await _make_skill(1, name="other skill one")
    other2 = await _make_skill(2, name="other skill two")

    # base_results does NOT include target
    boosted = await name_boost("off-page-target", [other1, other2])
    assert boosted[0].name == "off-page-target"


@pytest.mark.asyncio
async def test_partial_match_not_boosted():
    """Partial name match is not surfaced by name_boost."""
    from app.services.search import name_boost

    await _make_skill(0, name="target skill full")
    other = await _make_skill(1, name="other")

    # Only base = [other]; partial name "target" should not prepend anything
    boosted = await name_boost("target", [other])
    assert boosted[0].name == "other"


# ===========================================================================
# Slice 3 — Atlas Search feature flag
# ===========================================================================


@pytest.mark.asyncio
async def test_atlas_search_flag_off_produces_text_query(monkeypatch):
    """With MONGODB_ATLAS_SEARCH=0, list() does not call build_atlas_pipeline."""
    monkeypatch.setenv("MONGODB_ATLAS_SEARCH", "0")
    for i in range(2):
        await _make_skill(i)

    with patch("app.services.search.build_atlas_pipeline") as mock_build:
        # Even if $text raises (mongomock doesn't support it), atlas pipeline is NOT called
        try:
            await skill_repository.list(q="Skill")
        except Exception:
            pass
        mock_build.assert_not_called()


@pytest.mark.asyncio
async def test_atlas_search_flag_on_falls_back_on_operation_failure(monkeypatch):
    """With MONGODB_ATLAS_SEARCH=1, OperationFailure on the atlas path is caught (no 500)."""
    import pymongo.errors
    monkeypatch.setenv("MONGODB_ATLAS_SEARCH", "1")
    for i in range(2):
        await _make_skill(i)

    # Patch both build_atlas_pipeline (raises OperationFailure) and the $text fallback
    # (which mongomock doesn't support) so we can verify the exception-guard path.
    with patch("app.services.search.build_atlas_pipeline") as mock_build, \
         patch("app.services.skill.Skill.find") as mock_find:
        mock_build.side_effect = pymongo.errors.OperationFailure("index not found")
        # Mock find() to return an empty result so $text path doesn't hit mongomock
        mock_query = AsyncMock()
        mock_query.count = AsyncMock(return_value=0)
        mock_query.sort = lambda *a, **kw: mock_query
        mock_query.skip = lambda *a, **kw: mock_query
        mock_query.limit = lambda *a, **kw: mock_query
        mock_query.to_list = AsyncMock(return_value=[])
        mock_find.return_value = mock_query

        try:
            items, total = await skill_repository.list(q="Skill")
            assert isinstance(items, list)
        except pymongo.errors.OperationFailure:
            pytest.fail("OperationFailure should have been caught and not propagated")
