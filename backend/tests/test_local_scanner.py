"""Tests for LocalScanner — filesystem-based skill discovery."""

import os
import pytest

from app.services.local import LocalScanner, _MAX_FILE_SIZE, _MAX_DISCOVER_DEPTH
from app.services.scanner import LocalRef, RawScanResult


@pytest.fixture
def skill_dir(tmp_path):
    """A minimal valid skill directory."""
    (tmp_path / "SKILL.md").write_text("---\nname: test-skill\n---\nBody.")
    (tmp_path / "README.md").write_text("# Test Skill")
    return tmp_path


@pytest.fixture
def scanner():
    return LocalScanner()


# ---------------------------------------------------------------------------
# scan() — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_reads_skill_md(scanner, skill_dir):
    ref = LocalRef(path=str(skill_dir))
    result = await scanner.scan(ref)
    assert "SKILL.md" in result.files
    assert "test-skill" in result.files["SKILL.md"]


@pytest.mark.asyncio
async def test_scan_reads_readme(scanner, skill_dir):
    ref = LocalRef(path=str(skill_dir))
    result = await scanner.scan(ref)
    assert "README.md" in result.files


@pytest.mark.asyncio
async def test_scan_populates_snapshotted_files(scanner, skill_dir):
    ref = LocalRef(path=str(skill_dir))
    result = await scanner.scan(ref)
    assert result.snapshotted_files == result.files


@pytest.mark.asyncio
async def test_scan_no_skill_files_false_when_skill_md_present(scanner, skill_dir):
    ref = LocalRef(path=str(skill_dir))
    result = await scanner.scan(ref)
    assert result.no_skill_files is False


@pytest.mark.asyncio
async def test_scan_no_skill_files_true_when_no_instruction_file(scanner, tmp_path):
    (tmp_path / "README.md").write_text("# Just a readme")
    ref = LocalRef(path=str(tmp_path))
    result = await scanner.scan(ref)
    assert result.no_skill_files is True


@pytest.mark.asyncio
async def test_scan_claude_plugin_fallback(scanner, tmp_path):
    """plugin.json in .claude-plugin/ subdirectory is found as fallback."""
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text('{"name": "my-plugin"}')
    (tmp_path / "SKILL.md").write_text("---\nname: test\n---")
    ref = LocalRef(path=str(tmp_path))
    result = await scanner.scan(ref)
    assert "plugin.json" in result.files
    assert "my-plugin" in result.files["plugin.json"]


# ---------------------------------------------------------------------------
# scan() — error cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_raises_on_nonexistent_path(scanner):
    ref = LocalRef(path="/nonexistent/path/that/does/not/exist")
    with pytest.raises(Exception, match="not found|not a directory"):
        await scanner.scan(ref)


@pytest.mark.asyncio
async def test_scan_raises_on_file_not_dir(scanner, tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("content")
    ref = LocalRef(path=str(f))
    with pytest.raises(Exception, match="not found|not a directory"):
        await scanner.scan(ref)


# ---------------------------------------------------------------------------
# Security: file size cap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_skips_oversized_files(scanner, tmp_path):
    """Files exceeding _MAX_FILE_SIZE are skipped, not read into memory."""
    large = tmp_path / "README.md"
    large.write_bytes(b"x" * (_MAX_FILE_SIZE + 1))
    (tmp_path / "SKILL.md").write_text("---\nname: test\n---")
    ref = LocalRef(path=str(tmp_path))
    result = await scanner.scan(ref)
    assert "README.md" not in result.files
    assert "SKILL.md" in result.files


@pytest.mark.asyncio
async def test_scan_reads_file_exactly_at_size_limit(scanner, tmp_path):
    """Files at exactly _MAX_FILE_SIZE are read."""
    (tmp_path / "README.md").write_bytes(b"x" * _MAX_FILE_SIZE)
    (tmp_path / "SKILL.md").write_text("---\nname: test\n---")
    ref = LocalRef(path=str(tmp_path))
    result = await scanner.scan(ref)
    assert "README.md" in result.files


# ---------------------------------------------------------------------------
# Security: symlink containment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_does_not_follow_symlink_outside_dir(scanner, tmp_path):
    """A symlink pointing outside the skill dir is not read."""
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("secret content")
    link = tmp_path / "README.md"
    link.symlink_to(outside)
    (tmp_path / "SKILL.md").write_text("---\nname: test\n---")
    ref = LocalRef(path=str(tmp_path))
    result = await scanner.scan(ref)
    assert "README.md" not in result.files


# ---------------------------------------------------------------------------
# discover() — multi-skill directory
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_discover_finds_nested_skill(scanner, tmp_path):
    skill_a = tmp_path / "skills" / "skill-a"
    skill_a.mkdir(parents=True)
    (skill_a / "SKILL.md").write_text("---\nname: skill-a\n---")
    ref = LocalRef(path=str(tmp_path))
    results, truncated, capped = await scanner.discover(ref)
    assert len(results) == 1
    assert not truncated
    assert not capped


@pytest.mark.asyncio
async def test_discover_caps_at_20(scanner, tmp_path):
    for i in range(25):
        d = tmp_path / f"skill-{i:02d}"
        d.mkdir()
        (d / "SKILL.md").write_text(f"---\nname: skill-{i}\n---")
    ref = LocalRef(path=str(tmp_path))
    results, _truncated, capped = await scanner.discover(ref)
    assert len(results) == 20
    assert capped is True


@pytest.mark.asyncio
async def test_discover_respects_depth_limit(scanner, tmp_path):
    """Skills nested deeper than _MAX_DISCOVER_DEPTH are not found."""
    deep = tmp_path
    for _ in range(_MAX_DISCOVER_DEPTH + 2):
        deep = deep / "sub"
    deep.mkdir(parents=True)
    (deep / "SKILL.md").write_text("---\nname: too-deep\n---")
    ref = LocalRef(path=str(tmp_path))
    results, _, _ = await scanner.discover(ref)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_discover_skips_node_modules(scanner, tmp_path):
    nm = tmp_path / "node_modules" / "some-pkg"
    nm.mkdir(parents=True)
    (nm / "SKILL.md").write_text("---\nname: in-node-modules\n---")
    ref = LocalRef(path=str(tmp_path))
    results, _, _ = await scanner.discover(ref)
    assert len(results) == 0
