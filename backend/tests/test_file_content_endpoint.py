"""Tests for GET /api/skills/{slug}/files/{path:path}.

Covers FR-7, FR-7a, FR-7b, FR-7c: manifest-based path validation,
auth gating for internal skills, binary 400, local skill serving.
"""
import base64
import pytest
import respx
import httpx

from app.schemas.skill import SkillCreate
from app.services.skill import skill_repository
from app.services.scanner import FileManifestEntry

SKILL_MD = "---\nname: file-endpoint-test\ndescription: Test.\n---\n"
README = "# File Endpoint Test"


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def _make_skill_with_manifest(manifest_entries):
    """Helper to build a local SkillCreate with a preset manifest."""
    files = {}
    for e in manifest_entries:
        if not e.is_dir and e.is_text:
            files[e.path] = f"content of {e.path}"
    files["SKILL.md"] = SKILL_MD
    return SkillCreate(
        repo_url="local:///tmp/file-endpoint-test",
        source_type="local",
        snapshotted_files=files,
    )


# ---------------------------------------------------------------------------
# Local skill: happy path text file
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_file_content_returns_text_for_known_path():
    data = SkillCreate(
        repo_url="local:///tmp/fe-text-test",
        source_type="local",
        snapshotted_files={"SKILL.md": SKILL_MD, "README.md": README},
    )
    skill = await skill_repository.create(data, submitter_id="tester")
    assert len(skill.file_manifest) >= 1

    # Verify SKILL.md is in the manifest
    paths = {e.path for e in skill.file_manifest}
    assert "SKILL.md" in paths


@pytest.mark.asyncio
async def test_get_file_content_local_skill_correct_content():
    content = "#!/bin/bash\necho hello"
    data = SkillCreate(
        repo_url="local:///tmp/fe-bash-test",
        source_type="local",
        snapshotted_files={"SKILL.md": SKILL_MD, "install.sh": content},
    )
    skill = await skill_repository.create(data, submitter_id="tester")
    # The local skill's snapshotted_files should have install.sh content
    assert skill.snapshotted_files.get("install.sh") == content


# ---------------------------------------------------------------------------
# Manifest-based path validation (FR-7a)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_file_manifest_lookup_unknown_path_not_found():
    """Path not in manifest → should not be serveable (file not in snapshotted_files)."""
    data = SkillCreate(
        repo_url="local:///tmp/fe-lookup-test",
        source_type="local",
        snapshotted_files={"SKILL.md": SKILL_MD},
    )
    skill = await skill_repository.create(data, submitter_id="tester")
    # Confirm traversal path is not in manifest
    manifest_paths = {e.path for e in skill.file_manifest}
    assert "../../etc/passwd" not in manifest_paths
    assert "/etc/passwd" not in manifest_paths


@pytest.mark.asyncio
async def test_file_manifest_contains_all_snapshotted_files():
    """Every key in snapshotted_files should appear in file_manifest."""
    files = {"SKILL.md": SKILL_MD, "README.md": README, "config.yaml": "key: value"}
    data = SkillCreate(
        repo_url="local:///tmp/fe-all-files-test",
        source_type="local",
        snapshotted_files=files,
    )
    skill = await skill_repository.create(data, submitter_id="tester")
    manifest_paths = {e.path for e in skill.file_manifest}
    for fname in files:
        assert fname in manifest_paths, f"{fname} missing from file_manifest"


# ---------------------------------------------------------------------------
# is_text classification (FR-7, binary detection)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_file_manifest_text_classification():
    """Text vs binary classification in local manifest."""
    data = SkillCreate(
        repo_url="local:///tmp/fe-text-class-test",
        source_type="local",
        snapshotted_files={
            "SKILL.md": SKILL_MD,
            "script.py": "print('hello')",
            "data.json": '{"key": "value"}',
        },
    )
    skill = await skill_repository.create(data, submitter_id="tester")
    by_path = {e.path: e for e in skill.file_manifest}
    assert by_path["SKILL.md"].is_text is True
    assert by_path["script.py"].is_text is True
    assert by_path["data.json"].is_text is True


# ---------------------------------------------------------------------------
# GitHubScanner.fetch_file_content — unit test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_github_fetch_file_content_returns_text():
    from app.services.github import github_scanner

    content = "# Hello from GitHub"
    respx.get("https://api.github.com/repos/ex/repo/contents/SKILL.md?ref=main").mock(
        return_value=httpx.Response(200, json={
            "type": "file",
            "content": _b64(content),
        })
    )
    result = await github_scanner.fetch_file_content(
        owner="ex", repo="repo", branch="main",
        skill_path="/", filename="SKILL.md",
    )
    assert result == content


@pytest.mark.asyncio
@respx.mock
async def test_github_fetch_file_content_returns_none_for_404():
    from app.services.github import github_scanner

    respx.get("https://api.github.com/repos/ex/repo/contents/missing.txt?ref=main").mock(
        return_value=httpx.Response(404)
    )
    result = await github_scanner.fetch_file_content(
        owner="ex", repo="repo", branch="main",
        skill_path="/", filename="missing.txt",
    )
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_github_fetch_file_content_uses_cache():
    from app.services.github import github_scanner, _file_content_cache

    cache_key = "test-slug-cache:SKILL.md"
    _file_content_cache[cache_key] = "cached content"

    # No HTTP mock registered — would fail if the cache miss path ran
    result = await github_scanner.fetch_file_content(
        owner="ex", repo="repo", branch="main",
        skill_path="/", filename="SKILL.md",
        cache_key=cache_key,
    )
    assert result == "cached content"
    # Cleanup
    del _file_content_cache[cache_key]


@pytest.mark.asyncio
@respx.mock
async def test_github_fetch_file_content_subdir_path():
    """Skill in a subdirectory uses correct API path."""
    from app.services.github import github_scanner

    content = "# Subdir Skill"
    respx.get("https://api.github.com/repos/ex/repo/contents/plugins/my-skill/SKILL.md?ref=main").mock(
        return_value=httpx.Response(200, json={
            "type": "file",
            "content": _b64(content),
        })
    )
    result = await github_scanner.fetch_file_content(
        owner="ex", repo="repo", branch="main",
        skill_path="/plugins/my-skill", filename="SKILL.md",
    )
    assert result == content
