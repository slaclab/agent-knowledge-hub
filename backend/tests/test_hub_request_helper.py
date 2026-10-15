"""Tests for skill/hub-request.sh, the client's only reader of the S3DF token (#050).

These tests never run the shipped helper. They run a copy in which exactly two lines differ:
the origin constant points at a fake server on 127.0.0.1, and the real-home lookup points at a
temporary directory. A regressed refusal therefore cannot send the developer's real token to the
production catalog, and the fake server never prints a header it received (#050, Open Design
Question 1). The fake token is generated at run time, so no command line holds it.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[2] / "skill"
HELPER = SKILL_DIR / "hub-request.sh"
ORIGIN_LINE = "origin=https://agent-knowledge-hub.slac.stanford.edu"
HOME_LINE_PREFIX = "home=$(getent passwd"


def _shells(tmp_root: Path) -> list[tuple[str, str]]:
    """dash and bash invoked through a link named `sh`, each where present."""
    found = []
    if shutil.which("dash"):
        found.append(("dash", shutil.which("dash")))
    bash = shutil.which("bash")
    if bash:
        link_dir = tmp_root / "bash-as-sh"
        link_dir.mkdir(exist_ok=True)
        link = link_dir / "sh"
        if not link.exists():
            link.symlink_to(bash)
        found.append(("bash-as-sh", str(link)))
    return found


class FakeCatalog:
    """Logs each request's method, path, body length and digest; checks the token without printing it."""

    def __init__(self):
        self.requests: list[dict] = []
        self.responses: dict[tuple[str, str], tuple[int, bytes]] = {}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _handle(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                outer.requests.append({
                    "method": self.command,
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "content_type": self.headers.get("Content-Type"),
                    "body_len": len(body),
                    "body_sha": hashlib.sha256(body).hexdigest(),
                })
                status, payload = outer.responses.get((self.command, self.path), (200, b'{"ok": true}'))
                self.send_response(status)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = _handle
            do_POST = _handle

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def catalog():
    fake = FakeCatalog()
    yield fake
    fake.close()


@pytest.fixture
def homes(tmp_path):
    real = tmp_path / "real-home"
    session = tmp_path / "session-home"
    tmp = tmp_path / "tmp"
    for d in (real, session, tmp):
        d.mkdir()
    return {"real": real, "session": session, "tmp": tmp}


def make_copy(tmp_path: Path, origin: str, real_home: Path) -> Path:
    """The test copy: the shipped helper with the origin and real-home lines replaced, nothing else."""
    lines = HELPER.read_text().splitlines(keepends=True)
    out, changed = [], 0
    for line in lines:
        stripped = line.strip()
        if stripped == ORIGIN_LINE:
            out.append(line.replace(ORIGIN_LINE, f"origin={origin}"))
            changed += 1
        elif stripped.startswith(HOME_LINE_PREFIX):
            indent = line[: len(line) - len(line.lstrip())]
            out.append(f"{indent}home={real_home}\n")
            changed += 1
        else:
            out.append(line)
    assert changed == 2, "the test copy must differ from the shipped helper on exactly two lines"
    copy = tmp_path / "hub-request.sh"
    copy.write_text("".join(out))
    return copy


def clean_env(homes: dict, **extra) -> dict:
    """An environment with no proxy variable (FR-8): curl sends even loopback URLs through http_proxy."""
    env = {"PATH": "/usr/bin:/bin", "HOME": str(homes["session"]), "TMPDIR": str(homes["tmp"]), "LANG": "C.UTF-8"}
    env.update(extra)
    return env


def write_token(directory: Path, content: str | None = None) -> str:
    token = content if content is not None else secrets.token_urlsafe(32)
    (directory / ".s3df-access-token").write_text(token + "\n")
    return token


SHELLS = _shells(Path(os.environ.get("TMPDIR", "/tmp")))
needs_proc = pytest.mark.skipif(not Path("/proc/self/cmdline").exists(), reason="needs /proc")


def run(shell: str, copy: Path, env: dict, *args: str, stdin: bytes | None = b"", timeout: int = 20):
    return subprocess.run(
        [shell, str(copy), *args], env=env, input=stdin, capture_output=True, timeout=timeout,
    )


@needs_proc
@pytest.mark.parametrize("shell", [s for _, s in SHELLS], ids=[n for n, _ in SHELLS])
class TestTokenReachesCatalog:
    def test_real_home_token_is_sent(self, shell, catalog, homes, tmp_path):  # AC-1
        token = write_token(homes["real"])
        copy = make_copy(tmp_path, f"http://127.0.0.1:{catalog.port}", homes["real"])
        result = run(shell, copy, clean_env(homes), "GET", "/cli/api/skills/summary")
        assert result.returncode == 0
        assert len(catalog.requests) == 1
        request = catalog.requests[0]
        assert request["path"] == "/cli/api/skills/summary"
        assert request["authorization"] == f"Bearer {token}", "the received header does not match (not printed)"
        assert result.stdout == b'{"ok": true}'


class TestShippedHelper:
    def test_origin_is_production(self):
        assert ORIGIN_LINE in HELPER.read_text().splitlines()
