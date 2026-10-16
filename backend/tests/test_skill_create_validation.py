"""Tests for #045 — repo_url and skill_path allow-lists at create time, and the [CREATE] log line.

The catalog's values reach `git clone` and `cp` on an installing user's machine, so every value
the server accepts must also pass the install loop's own argument check (#006 FR-7 › Argument
rule), and none may carry shell syntax or a newline.
"""
from __future__ import annotations

import logging
import re

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app import config as config_module
from app.main import create_app
from app.models.skill import Skill
from app.schemas.skill import SkillCreate, SkillUpdate
from app.services import skill as skill_module
from app.services.github import GitHubFetchError

_TEST_SECRET = "test-secret-for-045"

# #006 FR-7 › Argument rule: the patterns the install loop applies before it clones a member.
CLIENT_REPO_URL_RE = re.compile(r"^https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
CLIENT_SKILL_PATH_RE = re.compile(r"^/[A-Za-z0-9._/-]*$")

REJECTED_REPO_URLS = [
    "https://github.com/a/$(touch x)",
    "https://github.com/a;id/b",
    "https://github.com/a\nINFO fake/b",
    "https://github.com/a/b'c",
    "https://github.com/a/" + "x" * 5000,
    "https://github.com/a/" + "r" * 101,
    "https://github.com/" + "o" * 40 + "/repo",
    "https://github.com/a b/c",
    "https://github.com/a/b c",
    "https://github.com/a_b/c",
    "https://github.com/a/b/c",
    "https://github.com/a/",
    "https://github.com//b",
    "http://github.com/a/b",
    "https://github.com.evil.example/a/b",
    "https://github.com/a/bé",
]

ACCEPTED_REPO_URLS = [
    "https://github.com/slaclab/lcls-tools",
    "https://github.com/A-1/b.c_d-e",
    "https://github.com/" + "o" * 39 + "/" + "r" * 100,
]

REJECTED_SKILL_PATHS = [
    "/a/$(id)",
    "/a;b",
    "/a\nb",
    "/a b",
    "/a/b\n",
    "/a'b",
    "/a\\b",
    "/a/../b",
    "/a/bé",
]

ACCEPTED_SKILL_PATHS = ["/", "/skills/x", "skills/x", "/a.b/c_d-e/"]


def _create(**overrides) -> SkillCreate:
    fields = {"repo_url": "https://github.com/slaclab/lcls-tools", "skill_path": "/skills/x"}
    fields.update(overrides)
    return SkillCreate(**fields)


class TestRepoUrl:  # FR-1
    @pytest.mark.parametrize("repo_url", REJECTED_REPO_URLS)
    def test_rejected(self, repo_url):
        with pytest.raises(ValidationError):
            _create(repo_url=repo_url)

    @pytest.mark.parametrize("repo_url", ACCEPTED_REPO_URLS)
    def test_accepted(self, repo_url):
        assert _create(repo_url=repo_url).repo_url == repo_url

    def test_surrounding_whitespace_is_stripped(self):
        assert _create(repo_url="  https://github.com/a/b \n").repo_url == "https://github.com/a/b"

    def test_local_submission_keeps_its_local_url(self):
        body = _create(repo_url="local://some/dir", source_type="local")
        assert body.repo_url == "local://some/dir"


class TestSkillPath:  # FR-2
    @pytest.mark.parametrize("skill_path", REJECTED_SKILL_PATHS)
    def test_create_body_rejects(self, skill_path):
        with pytest.raises(ValidationError):
            _create(skill_path=skill_path)

    @pytest.mark.parametrize("skill_path", REJECTED_SKILL_PATHS)
    def test_model_rejects(self, skill_path):
        with pytest.raises(ValueError):
            Skill.validate_skill_path(skill_path)

    @pytest.mark.parametrize("skill_path", REJECTED_SKILL_PATHS)
    def test_local_submission_rejects(self, skill_path):
        with pytest.raises(ValidationError):
            _create(repo_url="local://dir", source_type="local", skill_path=skill_path)

    @pytest.mark.parametrize("skill_path", ACCEPTED_SKILL_PATHS)
    def test_accepted_and_normalised(self, skill_path):
        expected = skill_path if skill_path.startswith("/") else "/" + skill_path
        assert _create(skill_path=skill_path).skill_path == expected
        assert Skill.validate_skill_path(skill_path) == expected

    def test_length_limit_kept(self):
        with pytest.raises(ValueError):
            Skill.validate_skill_path("/" + "a" * 500)


class TestForkedFromUrl:  # Open Question 1: same pattern as repo_url
    def test_rejects_shell_syntax(self):
        with pytest.raises(ValidationError):
            SkillUpdate(forked_from_url="https://github.com/a/$(id)")

    def test_accepts_plain_url(self):
        assert SkillUpdate(forked_from_url="https://github.com/a/b").forked_from_url == "https://github.com/a/b"


class TestServerAcceptsOnlyWhatTheClientAccepts:  # NFR-1
    """Whatever the server accepts, the install loop's own check accepts too."""

    CANDIDATES = [chr(c) for c in range(0, 128)] + ["é", "і", " ", "K"]

    @pytest.mark.parametrize("ch", CANDIDATES, ids=lambda c: f"U+{ord(c):04X}")
    def test_repo_url_characters(self, ch):
        for url in (f"https://github.com/a{ch}/b", f"https://github.com/a/b{ch}"):
            try:
                accepted = _create(repo_url=url).repo_url
            except ValidationError:
                continue
            assert CLIENT_REPO_URL_RE.fullmatch(accepted), repr(accepted)

    @pytest.mark.parametrize("ch", CANDIDATES, ids=lambda c: f"U+{ord(c):04X}")
    def test_skill_path_characters(self, ch):
        for path in (f"/a{ch}b", f"/a/b{ch}"):
            try:
                accepted = _create(skill_path=path).skill_path
            except ValidationError:
                continue
            assert CLIENT_SKILL_PATH_RE.fullmatch(accepted), repr(accepted)

    @pytest.mark.parametrize("repo_url", ACCEPTED_REPO_URLS)
    def test_accepted_repo_urls_pass_the_client(self, repo_url):
        assert CLIENT_REPO_URL_RE.fullmatch(_create(repo_url=repo_url).repo_url)

    @pytest.mark.parametrize("skill_path", ACCEPTED_SKILL_PATHS)
    def test_accepted_skill_paths_pass_the_client(self, skill_path):
        assert CLIENT_SKILL_PATH_RE.fullmatch(_create(skill_path=skill_path).skill_path)


# ---------------------------------------------------------------------------
# HTTP and the [CREATE] log line
# ---------------------------------------------------------------------------

@pytest.fixture
def github_calls(monkeypatch):
    """Make every GitHub call fail, as during an outage, and record that one was attempted."""
    calls = []

    async def fail(*args, **kwargs):
        calls.append(args)
        raise GitHubFetchError("offline in tests")

    monkeypatch.setattr(skill_module.github_fetcher, "fetch", fail)
    monkeypatch.setattr(skill_module.github_scanner, "scan", fail)
    return calls


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setattr(config_module.settings, "internal_api_secret", _TEST_SECRET)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _auth() -> dict:
    return {"X-Internal-Secret": _TEST_SECRET, "X-Forwarded-User": "submitter"}


class TestCreateEndpoint:  # User stories
    async def test_shell_syntax_in_repo_url_is_422(self, client, github_calls):
        resp = await client.post("/api/skills", headers=_auth(),
                                 json={"repo_url": "https://github.com/a/$(touch x)", "skill_path": "/"})
        assert resp.status_code == 422
        assert await Skill.find_all().count() == 0
        assert github_calls == []

    async def test_shell_syntax_in_skill_path_is_422(self, client, github_calls):
        resp = await client.post("/api/skills", headers=_auth(),
                                 json={"repo_url": "https://github.com/slaclab/lcls-tools", "skill_path": "/a;b"})
        assert resp.status_code == 422
        assert await Skill.find_all().count() == 0
        assert github_calls == []

    async def test_plain_submission_is_201(self, client, github_calls):
        resp = await client.post("/api/skills", headers=_auth(),
                                 json={"repo_url": "https://github.com/slaclab/lcls-tools", "skill_path": "/skills/x"})
        assert resp.status_code == 201, resp.text
        assert resp.json()["skill_path"] == "/skills/x"
        assert await Skill.find_all().count() == 1


class TestCreateLogLine:  # FR-3
    async def test_newline_cannot_split_the_record(self, caplog, github_calls):
        body = SkillCreate.model_construct(
            repo_url="https://github.com/a/b\nINFO forged line",
            skill_path="/x\ny",
            source_type="github",
            name=None,
            description=None,
            compatible_platforms=[],
            keywords=[],
            license=None,
            version=None,
            uses_agent_gateway=False,
            snapshotted_files={},
            skillset_slug=None,
        )
        caplog.set_level(logging.INFO, logger=skill_module.logger.name)
        try:
            await skill_module.skill_repository.create(body, submitter_id="submitter")
        except Exception:
            pass
        lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("[CREATE] submitter=")]
        assert len(lines) == 1
        assert "\n" not in lines[0]
        assert "'https://github.com/a/b\\nINFO forged line'" in lines[0]
        assert "'/x\\ny'" in lines[0]


# ---------------------------------------------------------------------------
# #049 — file names in local submissions
# ---------------------------------------------------------------------------

REJECTED_LOCAL_NAMES = [
    "/etc/profile",          # absolute
    "../x",                  # parent segment
    "a/../../x",
    "..",
    "./SKILL.md",            # current-directory segment
    "a//b",                  # empty segment
    "a/",                    # trailing slash: empty last segment
    "",                      # empty name
    "a\\b",                  # backslash, a separator on Windows
    "C:/x",                  # drive letter
    "c:x",
    "a\x00b",                # NUL
    "a\nb",                  # control character
]

ACCEPTED_LOCAL_NAMES = ["SKILL.md", "scripts/run.sh", "a..b.md", ".hidden/config", "dir with space/file.md"]


def _local(**files) -> dict:
    return {"repo_url": "local://some/dir", "source_type": "local", "skill_path": "/", "snapshotted_files": files}


class TestLocalFileNames:  # #049 FR-1
    @pytest.mark.parametrize("name", REJECTED_LOCAL_NAMES, ids=repr)
    def test_rejected(self, name):
        with pytest.raises(ValidationError) as exc:
            SkillCreate(**_local(**{"SKILL.md": "---\nname: x\n---\n", name: "x"}))
        assert "snapshotted_files" in str(exc.value)

    @pytest.mark.parametrize("name", ACCEPTED_LOCAL_NAMES)
    def test_accepted(self, name):
        body = SkillCreate(**_local(**{name: "x"}))
        assert name in body.snapshotted_files

    def test_github_submission_unaffected(self):  # AC-3
        body = SkillCreate(repo_url="https://github.com/a/b", snapshotted_files={"../x": "ignored"})
        assert body.source_type == "github"


class TestLocalFileNamesEndpoint:  # #049 AC-1, AC-2
    @pytest.mark.parametrize("name", ["/etc/profile", "../x", "a/../../x", ".."])
    async def test_unsafe_name_is_422(self, client, name):
        resp = await client.post("/api/skills", headers=_auth(),
                                 json=_local(**{"SKILL.md": "---\nname: x\n---\n", name: "x"}))
        assert resp.status_code == 422
        assert await Skill.find_all().count() == 0

    async def test_safe_names_are_201(self, client):
        files = {"SKILL.md": "---\nname: local-skill\ndescription: x\n---\nBody\n", "scripts/run.sh": "echo", "a..b.md": "x"}
        resp = await client.post("/api/skills", headers=_auth(), json=_local(**files))
        assert resp.status_code == 201, resp.text
        (stored,) = await Skill.find_all().to_list()
        assert {e.path for e in stored.file_manifest} == set(files)
