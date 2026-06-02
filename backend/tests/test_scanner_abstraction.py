"""Tests for the SourceScanner abstraction (scanner.py).

Slice 1 — pure refactor: zero behaviour change to GitHubScanner.
"""

import pytest

from app.services.scanner import (
    GitHubRef,
    LocalRef,
    RawScanResult,
    SourceRefParser,
    SourceScannerRegistry,
    scanner_registry,
    source_ref_parser,
)


# ---------------------------------------------------------------------------
# SourceRef types
# ---------------------------------------------------------------------------

def test_github_ref_has_source_type():
    ref = GitHubRef(owner="slaclab", repo="my-skill")
    assert ref.source_type == "github"


def test_local_ref_has_source_type():
    ref = LocalRef(path="/home/user/my-skill")
    assert ref.source_type == "local"


def test_raw_scan_result_accepts_github_ref():
    ref = GitHubRef(owner="slaclab", repo="my-skill")
    result = RawScanResult(ref=ref)
    assert result.ref.source_type == "github"


def test_raw_scan_result_accepts_local_ref():
    ref = LocalRef(path="/home/user/my-skill")
    result = RawScanResult(ref=ref)
    assert result.ref.source_type == "local"


# ---------------------------------------------------------------------------
# SourceRefParser
# ---------------------------------------------------------------------------

def test_parser_routes_github_https():
    ref = source_ref_parser.parse("https://github.com/slaclab/my-skill")
    assert isinstance(ref, GitHubRef)
    assert ref.owner == "slaclab"
    assert ref.repo == "my-skill"


def test_parser_routes_github_tree_url():
    ref = source_ref_parser.parse("https://github.com/owner/repo/tree/main/some/path")
    assert isinstance(ref, GitHubRef)
    assert ref.branch == "main"
    assert ref.path == "/some/path"


def test_parser_routes_absolute_path():
    ref = source_ref_parser.parse("/home/user/my-skill")
    assert isinstance(ref, LocalRef)
    assert ref.path == "/home/user/my-skill"


def test_parser_routes_tilde_path():
    ref = source_ref_parser.parse("~/projects/my-skill")
    assert isinstance(ref, LocalRef)
    assert "my-skill" in ref.path
    assert not ref.path.startswith("~")  # expanded


def test_parser_routes_relative_path():
    ref = source_ref_parser.parse("./my-skill")
    assert isinstance(ref, LocalRef)
    assert "my-skill" in ref.path


def test_parser_raises_on_unknown_input():
    with pytest.raises(ValueError, match="Cannot determine source type"):
        source_ref_parser.parse("ftp://example.com/something")


# ---------------------------------------------------------------------------
# SourceScannerRegistry
# ---------------------------------------------------------------------------

def test_registry_returns_registered_scanner():
    from app.services.github import github_scanner
    assert scanner_registry.get("github") is github_scanner


def test_registry_raises_on_unknown_source_type():
    with pytest.raises(ValueError, match="No scanner registered"):
        scanner_registry.get("gitlab")


def test_registry_register_and_get():
    registry = SourceScannerRegistry()

    class FakeScanner:
        pass

    fake = FakeScanner()
    registry.register("fake", fake)
    assert registry.get("fake") is fake


# ---------------------------------------------------------------------------
# GitHubScanner still satisfies SourceScanner interface
# ---------------------------------------------------------------------------

def test_github_scanner_has_scan_method():
    from app.services.github import github_scanner
    assert callable(getattr(github_scanner, "scan", None))


def test_github_scanner_has_discover_method():
    from app.services.github import github_scanner
    assert callable(getattr(github_scanner, "discover", None))


def test_github_scanner_is_source_scanner_instance():
    from app.services.github import github_scanner
    from app.services.scanner import SourceScanner
    assert isinstance(github_scanner, SourceScanner)


# ---------------------------------------------------------------------------
# Backward compatibility — github.py re-exports
# ---------------------------------------------------------------------------

def test_github_py_still_exports_raw_scan_result():
    from app.services.github import RawScanResult as GithubRawScanResult
    assert GithubRawScanResult is RawScanResult


def test_github_py_still_exports_github_ref():
    from app.services.github import GitHubRef as GithubGitHubRef
    assert GithubGitHubRef is GitHubRef
