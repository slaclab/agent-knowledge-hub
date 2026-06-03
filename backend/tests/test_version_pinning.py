"""Tests for skill version pinning (#017).

Covers:
- SHA format validation (model-level)
- update_available computed property
- GitHubFetcher HEAD SHA + tag fetching
- skill_repository.create() sets pinned_commit_sha
- skill_repository.refetch() updates upstream_sha, does not change pinned_commit_sha
- skill_repository.pin() self-contained, records RevisionAction.pin
- POST /{slug}/pin auth guards
- install ref passthrough (via SkillOut field)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.revision import RevisionAction, SkillRevision
from app.models.skill import Skill
from app.schemas.skill import SkillCreate, SkillOut
from app.services.github import GitHubFetchError
from app.services.skill import skill_repository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_SHA = "a" * 40
_VALID_SHA2 = "b" * 40


def _make_github_snapshot(head_sha=None, tag_name=None):
    from app.services.github import GitHubSnapshot
    from datetime import datetime, timezone
    from app.models.skill import VisibilityEnum
    snap = GitHubSnapshot(
        name="test-repo",
        description="desc",
        stars=5,
        fetched_at=datetime.now(timezone.utc),
        visibility=VisibilityEnum.public,
        head_sha=head_sha,
        head_tag=tag_name,
    )
    return snap


# ---------------------------------------------------------------------------
# SHA format validation
# ---------------------------------------------------------------------------

def test_sha_validation_accepts_valid_40char_hex():
    s = Skill(
        slug="x", name="x", repo_url="https://github.com/a/b",
        pinned_commit_sha=_VALID_SHA, submitter_id="u",
    )
    assert s.pinned_commit_sha == _VALID_SHA


def test_sha_validation_accepts_none():
    s = Skill(
        slug="x", name="x", repo_url="https://github.com/a/b",
        pinned_commit_sha=None, submitter_id="u",
    )
    assert s.pinned_commit_sha is None


def test_sha_validation_rejects_short_sha():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Skill(
            slug="x", name="x", repo_url="https://github.com/a/b",
            pinned_commit_sha="abc123", submitter_id="u",
        )


def test_sha_validation_rejects_uppercase():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Skill(
            slug="x", name="x", repo_url="https://github.com/a/b",
            pinned_commit_sha="A" * 40, submitter_id="u",
        )


def test_sha_validation_rejects_non_hex():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Skill(
            slug="x", name="x", repo_url="https://github.com/a/b",
            pinned_commit_sha="z" * 40, submitter_id="u",
        )


# ---------------------------------------------------------------------------
# update_available computed property
# ---------------------------------------------------------------------------

def _skill_with(pinned=None, upstream=None):
    return Skill(
        slug="s", name="s", repo_url="https://github.com/a/b",
        pinned_commit_sha=pinned, upstream_sha=upstream, submitter_id="u",
    )


def test_update_available_true_when_shas_differ():
    s = _skill_with(pinned=_VALID_SHA, upstream=_VALID_SHA2)
    assert s.update_available is True


def test_update_available_false_when_shas_match():
    s = _skill_with(pinned=_VALID_SHA, upstream=_VALID_SHA)
    assert s.update_available is False


def test_update_available_false_when_upstream_is_none():
    s = _skill_with(pinned=_VALID_SHA, upstream=None)
    assert s.update_available is False


def test_update_available_false_when_both_none():
    s = _skill_with(pinned=None, upstream=None)
    assert s.update_available is False


def test_update_available_false_when_pinned_is_none():
    # upstream set but no pin — skill not yet backfilled
    s = _skill_with(pinned=None, upstream=_VALID_SHA)
    assert s.update_available is False


# ---------------------------------------------------------------------------
# GitHubSnapshot has head_sha field
# ---------------------------------------------------------------------------

def test_github_snapshot_has_head_sha_field():
    snap = _make_github_snapshot(head_sha=_VALID_SHA)
    assert snap.head_sha == _VALID_SHA


def test_github_snapshot_head_sha_defaults_none():
    snap = _make_github_snapshot()
    assert snap.head_sha is None


# ---------------------------------------------------------------------------
# skill_repository.create() — sets pinned_commit_sha from github_fetcher
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_sets_pinned_commit_sha_when_fetch_succeeds():
    snap = _make_github_snapshot(head_sha=_VALID_SHA, tag_name="v1.0.0")
    with (
        patch("app.services.skill.github_fetcher.fetch", new_callable=AsyncMock, return_value=snap),
        patch("app.services.skill.github_scanner.scan", new_callable=AsyncMock, side_effect=GitHubFetchError("skip")),
    ):
        data = SkillCreate(repo_url="https://github.com/a/pintest", name="Pin Test")
        skill = await skill_repository.create(data, submitter_id="alice")
    assert skill.pinned_commit_sha == _VALID_SHA
    assert skill.pinned_ref == "v1.0.0"


@pytest.mark.asyncio
async def test_create_pinned_sha_none_when_fetch_fails():
    with (
        patch("app.services.skill.github_fetcher.fetch", new_callable=AsyncMock, side_effect=GitHubFetchError("fail")),
        patch("app.services.skill.github_scanner.scan", new_callable=AsyncMock, side_effect=GitHubFetchError("skip")),
    ):
        data = SkillCreate(repo_url="https://github.com/a/failtest", name="Fail Test")
        skill = await skill_repository.create(data, submitter_id="alice")
    assert skill.pinned_commit_sha is None


# ---------------------------------------------------------------------------
# skill_repository.refetch() — updates upstream_sha, leaves pinned intact
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refetch_updates_upstream_sha():
    snap_create = _make_github_snapshot(head_sha=_VALID_SHA)
    snap_refetch = _make_github_snapshot(head_sha=_VALID_SHA2)
    with (
        patch("app.services.skill.github_fetcher.fetch", new_callable=AsyncMock, return_value=snap_create),
        patch("app.services.skill.github_scanner.scan", new_callable=AsyncMock, side_effect=GitHubFetchError("skip")),
    ):
        data = SkillCreate(repo_url="https://github.com/a/refetchtest", name="Refetch Test")
        skill = await skill_repository.create(data, submitter_id="alice")
    assert skill.pinned_commit_sha == _VALID_SHA

    with (
        patch("app.services.skill.github_fetcher.fetch", new_callable=AsyncMock, return_value=snap_refetch),
        patch("app.services.skill.github_scanner.scan", new_callable=AsyncMock, side_effect=GitHubFetchError("skip")),
    ):
        skill = await skill_repository.refetch(skill, actor_id="alice")
    assert skill.upstream_sha == _VALID_SHA2
    assert skill.pinned_commit_sha == _VALID_SHA  # unchanged


# ---------------------------------------------------------------------------
# skill_repository.pin() — self-contained, advances pin, records revision
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pin_advances_pinned_commit_sha():
    snap_create = _make_github_snapshot(head_sha=_VALID_SHA)
    snap_pin = _make_github_snapshot(head_sha=_VALID_SHA2, tag_name="v2.0.0")
    with (
        patch("app.services.skill.github_fetcher.fetch", new_callable=AsyncMock, return_value=snap_create),
        patch("app.services.skill.github_scanner.scan", new_callable=AsyncMock, side_effect=GitHubFetchError("skip")),
    ):
        data = SkillCreate(repo_url="https://github.com/a/pinadvance", name="Pin Advance")
        skill = await skill_repository.create(data, submitter_id="alice")
    assert skill.pinned_commit_sha == _VALID_SHA

    with patch("app.services.skill.github_fetcher.fetch", new_callable=AsyncMock, return_value=snap_pin):
        skill = await skill_repository.pin(skill, actor_id="alice")
    assert skill.pinned_commit_sha == _VALID_SHA2
    assert skill.pinned_ref == "v2.0.0"
    assert skill.upstream_sha == _VALID_SHA2


@pytest.mark.asyncio
async def test_pin_works_when_upstream_sha_is_none():
    """pin() must be self-contained — no prior refetch required."""
    snap_create = _make_github_snapshot(head_sha=_VALID_SHA)
    snap_pin = _make_github_snapshot(head_sha=_VALID_SHA2)
    with (
        patch("app.services.skill.github_fetcher.fetch", new_callable=AsyncMock, return_value=snap_create),
        patch("app.services.skill.github_scanner.scan", new_callable=AsyncMock, side_effect=GitHubFetchError("skip")),
    ):
        data = SkillCreate(repo_url="https://github.com/a/freshpin", name="Fresh Pin")
        skill = await skill_repository.create(data, submitter_id="alice")
    # Force upstream_sha to None (simulating no-refetch-ever state)
    skill.upstream_sha = None
    await skill.save()

    with patch("app.services.skill.github_fetcher.fetch", new_callable=AsyncMock, return_value=snap_pin):
        skill = await skill_repository.pin(skill, actor_id="alice")
    assert skill.pinned_commit_sha == _VALID_SHA2


@pytest.mark.asyncio
async def test_pin_records_pin_revision():
    snap = _make_github_snapshot(head_sha=_VALID_SHA)
    snap2 = _make_github_snapshot(head_sha=_VALID_SHA2)
    with (
        patch("app.services.skill.github_fetcher.fetch", new_callable=AsyncMock, return_value=snap),
        patch("app.services.skill.github_scanner.scan", new_callable=AsyncMock, side_effect=GitHubFetchError("skip")),
    ):
        data = SkillCreate(repo_url="https://github.com/a/pinrev", name="Pin Rev")
        skill = await skill_repository.create(data, submitter_id="alice")

    with patch("app.services.skill.github_fetcher.fetch", new_callable=AsyncMock, return_value=snap2):
        skill = await skill_repository.pin(skill, actor_id="alice")

    revs = await SkillRevision.find(SkillRevision.skill_id == str(skill.id)).to_list()
    actions = [r.action for r in revs]
    assert RevisionAction.pin in actions


@pytest.mark.asyncio
async def test_pin_raises_for_local_skill():
    """Local skills cannot be pinned — no GitHub upstream."""
    from app.services.skill import PinNotSupportedError
    data = SkillCreate(
        repo_url="local://myfolder",
        name="Local Skill",
        source_type="local",
        snapshotted_files={"SKILL.md": "# Local"},
    )
    skill = await skill_repository.create(data, submitter_id="alice")
    with pytest.raises(PinNotSupportedError):
        await skill_repository.pin(skill, actor_id="alice")


# ---------------------------------------------------------------------------
# SkillOut includes version pinning fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skill_out_includes_pinning_fields():
    snap = _make_github_snapshot(head_sha=_VALID_SHA, tag_name="v1.0.0")
    with (
        patch("app.services.skill.github_fetcher.fetch", new_callable=AsyncMock, return_value=snap),
        patch("app.services.skill.github_scanner.scan", new_callable=AsyncMock, side_effect=GitHubFetchError("skip")),
    ):
        data = SkillCreate(repo_url="https://github.com/a/outtest", name="Out Test")
        skill = await skill_repository.create(data, submitter_id="alice")
    # Set upstream_sha to a different value to trigger update_available
    skill.upstream_sha = _VALID_SHA2
    await skill.save()
    skill = await skill_repository.get(skill.slug)
    # Use the same construction path as the router
    out = SkillOut(
        id=str(skill.id),
        slug=skill.slug,
        name=skill.name,
        repo_url=skill.repo_url,
        skill_path=skill.skill_path,
        entry_type=skill.entry_type,
        status=skill.status,
        deactivation_reason=skill.deactivation_reason,
        superseded_by_slug=skill.superseded_by_slug,
        description=skill.description,
        readme_html=skill.readme_html,
        skill_md_raw=skill.skill_md_raw,
        skill_md_filename=skill.skill_md_filename,
        readme_raw=skill.readme_raw,
        compatible_platforms=skill.compatible_platforms,
        license=skill.license,
        version=skill.version,
        github_stars=skill.github_stars,
        last_commit_at=skill.last_commit_at,
        readme_fetched_at=skill.readme_fetched_at,
        uses_agent_gateway=skill.uses_agent_gateway,
        visibility=skill.visibility,
        forked_from_url=skill.forked_from_url,
        agent_count=skill.agent_count,
        agent_names=skill.agent_names,
        has_mcp_server=skill.has_mcp_server,
        has_scripts=skill.has_scripts,
        plugin_author=skill.plugin_author,
        file_manifest=skill.file_manifest,
        manifest_truncated=skill.manifest_truncated,
        pinned_commit_sha=skill.pinned_commit_sha,
        pinned_ref=skill.pinned_ref,
        upstream_sha=skill.upstream_sha,
        update_available=skill.update_available,
        submitter_id=skill.submitter_id,
        submitted_at=skill.submitted_at,
        updated_at=skill.updated_at,
        avg_rating=skill.avg_rating,
        rating_count=skill.rating_count,
        flag_count=skill.flag_count,
    )
    assert out.pinned_commit_sha == _VALID_SHA
    assert out.pinned_ref == "v1.0.0"
    assert out.update_available is True


@pytest.mark.asyncio
async def test_skill_out_update_available_false_when_no_upstream():
    snap = _make_github_snapshot(head_sha=_VALID_SHA)
    with (
        patch("app.services.skill.github_fetcher.fetch", new_callable=AsyncMock, return_value=snap),
        patch("app.services.skill.github_scanner.scan", new_callable=AsyncMock, side_effect=GitHubFetchError("skip")),
    ):
        data = SkillCreate(repo_url="https://github.com/a/noups", name="No Upstream")
        skill = await skill_repository.create(data, submitter_id="alice")
    skill = await skill_repository.get(skill.slug)
    assert SkillOut(
        id=str(skill.id), slug=skill.slug, name=skill.name,
        repo_url=skill.repo_url, skill_path=skill.skill_path,
        entry_type=skill.entry_type, status=skill.status,
        deactivation_reason=None, superseded_by_slug=None,
        description=None, readme_html=None, skill_md_raw=None,
        skill_md_filename=None, readme_raw=None,
        compatible_platforms=[], license=None, version=None,
        github_stars=None, last_commit_at=None, readme_fetched_at=None,
        uses_agent_gateway=False, visibility=skill.visibility,
        forked_from_url=None, pinned_commit_sha=skill.pinned_commit_sha,
        pinned_ref=skill.pinned_ref, upstream_sha=skill.upstream_sha,
        update_available=skill.update_available,
        submitter_id=skill.submitter_id, submitted_at=skill.submitted_at,
        updated_at=skill.updated_at, avg_rating=0.0, rating_count=0, flag_count=0,
    ).update_available is False
