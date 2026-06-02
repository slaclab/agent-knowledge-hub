"""Tests for FileManifestEntry, _TEXT_EXTENSIONS, and file manifest pipeline.

Covers FR-1 through FR-6: scanner population, MetadataExtractor passthrough,
Skill model storage, and SkillOut serialisation.
"""
import pytest

from app.services.scanner import FileManifestEntry, RawScanResult, GitHubRef, _TEXT_EXTENSIONS, _MAX_MANIFEST


# ---------------------------------------------------------------------------
# FileManifestEntry unit tests
# ---------------------------------------------------------------------------

def test_file_manifest_entry_text_file():
    e = FileManifestEntry(path="SKILL.md", size_bytes=1024, is_text=True)
    assert e.path == "SKILL.md"
    assert e.size_bytes == 1024
    assert e.is_text is True
    assert e.is_dir is False


def test_file_manifest_entry_binary_file():
    e = FileManifestEntry(path="logo.png", size_bytes=4096, is_text=False)
    assert e.is_text is False
    assert e.is_dir is False


def test_file_manifest_entry_directory():
    e = FileManifestEntry(path="scripts", size_bytes=0, is_text=False, is_dir=True)
    assert e.is_dir is True
    assert e.size_bytes == 0
    assert e.is_text is False


# ---------------------------------------------------------------------------
# _TEXT_EXTENSIONS
# ---------------------------------------------------------------------------

def test_text_extensions_includes_common_types():
    for ext in (".md", ".py", ".sh", ".yaml", ".json", ".ts", ".toml"):
        assert ext in _TEXT_EXTENSIONS, f"{ext} should be a text extension"


def test_text_extensions_excludes_binary_types():
    for ext in (".png", ".jpg", ".zip", ".exe", ".whl"):
        assert ext not in _TEXT_EXTENSIONS, f"{ext} should NOT be a text extension"


# ---------------------------------------------------------------------------
# _MAX_MANIFEST constant
# ---------------------------------------------------------------------------

def test_max_manifest_is_200():
    assert _MAX_MANIFEST == 200


# ---------------------------------------------------------------------------
# RawScanResult.all_files field
# ---------------------------------------------------------------------------

def test_raw_scan_result_has_all_files():
    ref = GitHubRef(owner="ex", repo="repo", path="/")
    result = RawScanResult(ref=ref)
    assert result.all_files == []
    assert result.manifest_truncated is False


def test_raw_scan_result_accepts_all_files():
    ref = GitHubRef(owner="ex", repo="repo", path="/")
    entries = [FileManifestEntry(path="SKILL.md", size_bytes=500, is_text=True)]
    result = RawScanResult(ref=ref, all_files=entries)
    assert len(result.all_files) == 1
    assert result.all_files[0].path == "SKILL.md"


# ---------------------------------------------------------------------------
# GitHubScanner populates all_files from contents_data
# ---------------------------------------------------------------------------

def _make_contents_data(items):
    """Build a GitHub Contents API dir listing from simple dicts."""
    return [
        {
            "name": item["name"],
            "path": item.get("path", item["name"]),
            "type": item.get("type", "file"),
            "size": item.get("size", 100),
        }
        for item in items
    ]


def test_build_manifest_from_contents_data_text_file():
    """build_file_manifest classifies text files correctly."""
    from app.services.github import build_file_manifest
    contents = _make_contents_data([{"name": "SKILL.md", "size": 512}])
    entries, truncated = build_file_manifest(contents)
    assert len(entries) == 1
    assert entries[0].path == "SKILL.md"
    assert entries[0].size_bytes == 512
    assert entries[0].is_text is True
    assert entries[0].is_dir is False
    assert truncated is False


def test_build_manifest_from_contents_data_binary_file():
    from app.services.github import build_file_manifest
    contents = _make_contents_data([{"name": "logo.png", "size": 4096}])
    entries, truncated = build_file_manifest(contents)
    assert entries[0].is_text is False
    assert entries[0].is_dir is False


def test_build_manifest_from_contents_data_directory_entry():
    from app.services.github import build_file_manifest
    contents = _make_contents_data([{"name": "scripts", "type": "dir", "size": 0}])
    entries, truncated = build_file_manifest(contents)
    assert entries[0].is_dir is True
    assert entries[0].size_bytes == 0
    assert entries[0].is_text is False


def test_build_manifest_caps_at_200():
    from app.services.github import build_file_manifest
    contents = _make_contents_data([{"name": f"file{i}.py", "size": 100} for i in range(250)])
    entries, truncated = build_file_manifest(contents)
    assert len(entries) == 200
    assert truncated is True


def test_build_manifest_200_exactly_not_truncated():
    from app.services.github import build_file_manifest
    contents = _make_contents_data([{"name": f"file{i}.py", "size": 100} for i in range(200)])
    entries, truncated = build_file_manifest(contents)
    assert len(entries) == 200
    assert truncated is False


def test_build_manifest_missing_size_defaults_to_zero():
    from app.services.github import build_file_manifest
    contents = [{"name": "README.md", "path": "README.md", "type": "file"}]  # no size key
    entries, truncated = build_file_manifest(contents)
    assert entries[0].size_bytes == 0


# ---------------------------------------------------------------------------
# LocalScanner populates all_files from snapshotted_files
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_local_scanner_all_files_populated(tmp_path):
    """LocalScanner.scan() builds all_files from the recognised files it reads."""
    skill_md = "---\nname: test\n---\n"
    (tmp_path / "SKILL.md").write_text(skill_md)
    (tmp_path / "README.md").write_text("# Test")

    from app.services.scanner import LocalRef
    from app.services.local import local_scanner

    result = await local_scanner.scan(LocalRef(path=str(tmp_path)))
    assert len(result.all_files) >= 1
    paths = {e.path for e in result.all_files}
    assert "SKILL.md" in paths


@pytest.mark.asyncio
async def test_local_scanner_all_files_have_correct_size(tmp_path):
    content = "hello world"
    (tmp_path / "SKILL.md").write_text(content)

    from app.services.scanner import LocalRef
    from app.services.local import local_scanner

    result = await local_scanner.scan(LocalRef(path=str(tmp_path)))
    skill_entry = next(e for e in result.all_files if e.path == "SKILL.md")
    assert skill_entry.size_bytes == len(content.encode("utf-8"))


# ---------------------------------------------------------------------------
# MetadataExtractor passes all_files through to SkillScanSnapshot
# ---------------------------------------------------------------------------

def test_metadata_extractor_passes_file_manifest():
    from app.services.github import metadata_extractor
    from app.services.scanner import RawScanResult, GitHubRef, FileManifestEntry

    entries = [
        FileManifestEntry(path="SKILL.md", size_bytes=100, is_text=True),
        FileManifestEntry(path="scripts", size_bytes=0, is_text=False, is_dir=True),
    ]
    result = RawScanResult(
        ref=GitHubRef(owner="ex", repo="repo", path="/"),
        all_files=entries,
        manifest_truncated=False,
        no_skill_files=True,
    )
    snap = metadata_extractor.extract(result)
    assert len(snap.file_manifest) == 2
    assert snap.manifest_truncated is False


def test_metadata_extractor_passes_manifest_truncated_flag():
    from app.services.github import metadata_extractor
    from app.services.scanner import RawScanResult, GitHubRef

    result = RawScanResult(
        ref=GitHubRef(owner="ex", repo="repo", path="/"),
        all_files=[],
        manifest_truncated=True,
        no_skill_files=True,
    )
    snap = metadata_extractor.extract(result)
    assert snap.manifest_truncated is True


# ---------------------------------------------------------------------------
# skill_repository.create() stores manifest — tested via local path (no DB needed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_local_create_stores_file_manifest():
    from app.schemas.skill import SkillCreate
    from app.services.skill import skill_repository

    SKILL_MD = "---\nname: manifest-test\ndescription: Test skill.\n---\n"
    data = SkillCreate(
        repo_url="local:///tmp/manifest-test",
        source_type="local",
        snapshotted_files={"SKILL.md": SKILL_MD},
    )
    skill = await skill_repository.create(data, submitter_id="tester")
    assert len(skill.file_manifest) >= 1
    paths = {e.path for e in skill.file_manifest}
    assert "SKILL.md" in paths


@pytest.mark.asyncio
async def test_local_create_file_manifest_size_bytes():
    from app.schemas.skill import SkillCreate
    from app.services.skill import skill_repository

    content = "---\nname: size-test\ndescription: Check sizes.\n---\n"
    data = SkillCreate(
        repo_url="local:///tmp/size-test",
        source_type="local",
        snapshotted_files={"SKILL.md": content},
    )
    skill = await skill_repository.create(data, submitter_id="tester")
    entry = next(e for e in skill.file_manifest if e.path == "SKILL.md")
    assert entry.size_bytes == len(content.encode("utf-8"))
    assert entry.is_text is True
