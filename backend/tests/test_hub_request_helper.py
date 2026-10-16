"""Tests for skill/hub-request.sh, the client's only reader of the S3DF token (#050).

These tests never run the shipped helper. They run a copy in which exactly two lines differ:
the origin constant points at a fake server on 127.0.0.1, and the real-home lookup points at a
temporary directory. A regressed refusal therefore cannot send the developer's real token to the
production catalog, and the fake server never prints a header it received (#050, Open Design
Question 1). The fake token is generated at run time, so no command line holds it.
"""
from __future__ import annotations

import datetime
import hashlib
import ipaddress
import os
import re
import secrets
import shutil
import signal
import socket
import ssl
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[2] / "skill"
HELPER = SKILL_DIR / "hub-request.sh"
SKILL_MD = SKILL_DIR / "SKILL.md"
ORIGIN_LINE = "origin=https://agent-knowledge-hub.slac.stanford.edu"
HOME_LINE_PREFIX = "home=$(getent passwd"
TOKEN_FILE = ".s3df-access-token"


def _shells() -> list[tuple[str, str]]:
    """dash and bash invoked through a link named `sh`, each where present."""
    found = []
    if shutil.which("dash"):
        found.append(("dash", shutil.which("dash")))
    bash = shutil.which("bash")
    if bash:
        link_dir = Path(os.environ.get("TMPDIR", "/tmp")) / f"akh-bash-as-sh-{os.getuid()}"
        link_dir.mkdir(exist_ok=True)
        link = link_dir / "sh"
        if not link.is_symlink():
            link.symlink_to(bash)
        found.append(("bash-as-sh", str(link)))
    return found


SHELLS = _shells()
BASH_AS_SH = [s for n, s in SHELLS if n == "bash-as-sh"]
needs_proc = pytest.mark.skipif(not Path("/proc/self/cmdline").exists(), reason="needs /proc")
each_shell = pytest.mark.parametrize("shell", [s for _, s in SHELLS], ids=[n for n, _ in SHELLS])


# ---------------------------------------------------------------------------
# Fake catalog
# ---------------------------------------------------------------------------

class FakeCatalog:
    """Logs method, path, body length and digest. Compares the token without ever printing it."""

    def __init__(self, tls_context: ssl.SSLContext | None = None):
        self.requests: list[dict] = []
        self.responses: dict[str, tuple] = {}
        self.hold = threading.Event()
        self.held = threading.Event()
        self.hold_paths: set[str] = set()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _handle(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                outer.requests.append({
                    "method": self.command,
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "content_type": self.headers.get("Content-Type"),
                    "content_length": self.headers.get("Content-Length"),
                    "body_len": len(body),
                    "body_sha": hashlib.sha256(body).hexdigest(),
                })
                if self.path in outer.hold_paths:
                    outer.held.set()
                    outer.hold.wait(15)
                kind, *rest = outer.responses.get(self.path, ("json", 200, b'{"ok": true}'))
                if kind == "truncate":
                    self.send_response(200)
                    self.send_header("Content-Length", "100")
                    self.end_headers()
                    self.wfile.write(b"x" * 11)
                    self.wfile.flush()
                    self.close_connection = True
                    return
                status, payload = rest[0], rest[1]
                self.send_response(status)
                for name, value in (rest[2] if len(rest) > 2 else {}).items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = _handle
            do_POST = _handle

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        if tls_context is not None:
            self.server.socket = tls_context.wrap_socket(self.server.socket, server_side=True)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.hold.set()
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def catalog():
    fake = FakeCatalog()
    yield fake
    fake.close()


@pytest.fixture
def second():
    fake = FakeCatalog()
    yield fake
    fake.close()


@pytest.fixture
def homes(tmp_path):
    dirs = {name: tmp_path / name for name in ("real", "session", "tmp")}
    for d in dirs.values():
        d.mkdir()
    return dirs


def make_copy(tmp_path: Path, origin: str, real_home: str) -> Path:
    """The test copy: the shipped helper with the origin and real-home lines replaced, nothing else."""
    out, changed = [], 0
    for line in HELPER.read_text().splitlines(keepends=True):
        stripped = line.strip()
        indent = line[: len(line) - len(line.lstrip())]
        if stripped == ORIGIN_LINE:
            out.append(f"{indent}origin={origin}\n")
            changed += 1
        elif stripped.startswith(HOME_LINE_PREFIX):
            out.append(f"{indent}home={real_home}\n")
            changed += 1
        else:
            out.append(line)
    assert changed == 2, "the test copy must differ from the shipped helper on exactly two lines"
    copy = tmp_path / "hub-request.sh"
    copy.write_text("".join(out))
    return copy


@pytest.fixture
def copy(tmp_path, catalog, homes):
    return make_copy(tmp_path, f"http://127.0.0.1:{catalog.port}", str(homes["real"]))


def clean_env(homes: dict, **extra) -> dict:
    """No proxy variable (FR-8): curl sends even a loopback URL through http_proxy."""
    env = {"PATH": "/usr/bin:/bin", "HOME": str(homes["session"]), "TMPDIR": str(homes["tmp"]), "LANG": "C.UTF-8"}
    env.update(extra)
    return env


def write_token(directory: Path, content: str | None = None, suffix: str = "\n") -> str:
    token = content if content is not None else secrets.token_urlsafe(32)
    (directory / TOKEN_FILE).write_text(token + suffix)
    return token


def run(argv: list[str], env: dict, stdin=b"", timeout: int = 20):
    kwargs = {"input": stdin} if isinstance(stdin, (bytes, type(None))) else {"stdin": stdin}
    return subprocess.run(argv, env=env, capture_output=True, timeout=timeout, **kwargs)


def last_err(result) -> str:
    lines = [l for l in result.stderr.decode(errors="replace").splitlines() if l.strip()]
    return lines[-1] if lines else ""


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# AC-1 and FR-2: where the token comes from
# ---------------------------------------------------------------------------

@needs_proc
@each_shell
class TestTokenLocation:
    def test_real_home_token_is_sent(self, shell, catalog, homes, copy):  # AC-1
        token = write_token(homes["real"])
        result = run([shell, str(copy), "GET", "/cli/api/skills/summary"], clean_env(homes))
        assert result.returncode == 0
        assert len(catalog.requests) == 1
        assert catalog.requests[0]["authorization"] == f"Bearer {token}", "header mismatch (not printed)"
        assert result.stdout == b'{"ok": true}'

    def test_session_home_used_when_real_home_has_none(self, shell, catalog, homes, copy):
        token = write_token(homes["session"])
        result = run([shell, str(copy), "GET", "/cli/api/skills/summary"], clean_env(homes))
        assert result.returncode == 0
        assert catalog.requests[0]["authorization"] == f"Bearer {token}", "header mismatch (not printed)"

    def test_no_token_file_names_both_paths(self, shell, catalog, homes, copy):  # FR-7 first case
        result = run([shell, str(copy), "GET", "/cli/api/skills/summary"], clean_env(homes))
        assert result.returncode == 3
        assert catalog.requests == [] and result.stdout == b""
        line = last_err(result)
        assert line.startswith("agent-knowledge-hub: no token file: ")
        assert str(homes["real"] / TOKEN_FILE) in line and str(homes["session"] / TOKEN_FILE) in line

    @pytest.mark.parametrize("content", ["has space", "dollar$sign", "café", "", "\n"])
    def test_malformed_token_file_refused(self, shell, catalog, homes, copy, content):  # FR-3, AC-5
        (homes["real"] / TOKEN_FILE).write_text(content)
        result = run([shell, str(copy), "GET", "/cli/api/skills/summary"], clean_env(homes))
        assert result.returncode == 4
        assert catalog.requests == [] and result.stdout == b""
        assert last_err(result) == f"agent-knowledge-hub: malformed token file: {homes['real'] / TOKEN_FILE}"

    def test_malformed_file_content_never_printed(self, shell, catalog, homes, copy):  # AC-5
        token = write_token(homes["real"], suffix=" \n")
        result = run([shell, str(copy), "GET", "/cli/api/skills/summary"], clean_env(homes))
        assert result.returncode == 4
        assert token.encode() not in result.stdout + result.stderr

    def test_crlf_token_accepted(self, shell, catalog, homes, copy):
        token = write_token(homes["real"], suffix="\r\n")
        result = run([shell, str(copy), "GET", "/cli/api/skills/summary"], clean_env(homes))
        assert result.returncode == 0
        assert catalog.requests[0]["authorization"] == f"Bearer {token}", "header mismatch (not printed)"

    def test_malformed_real_home_file_not_skipped(self, shell, catalog, homes, copy):  # FR-2
        (homes["real"] / TOKEN_FILE).write_text("not a token")
        write_token(homes["session"])
        result = run([shell, str(copy), "GET", "/cli/api/skills/summary"], clean_env(homes))
        assert result.returncode == 4 and catalog.requests == []

    def test_empty_real_home_lookup_falls_back(self, shell, catalog, homes, tmp_path):  # FR-2
        empty_home_copy = make_copy(tmp_path, f"http://127.0.0.1:{catalog.port}", "")
        token = write_token(homes["session"])
        result = run([shell, str(empty_home_copy), "GET", "/cli/api/skills/summary"], clean_env(homes))
        assert result.returncode == 0
        assert catalog.requests[0]["authorization"] == f"Bearer {token}", "header mismatch (not printed)"

    def test_empty_real_home_never_checks_root(self, shell, catalog, homes, tmp_path):  # FR-2
        empty_home_copy = make_copy(tmp_path, f"http://127.0.0.1:{catalog.port}", "")
        result = run([shell, str(empty_home_copy), "GET", "/cli/api/skills/summary"], clean_env(homes))
        assert result.returncode == 3
        assert last_err(result) == f"agent-knowledge-hub: no token file: {homes['session'] / TOKEN_FILE}"

    def test_environment_variable_override_removed(self, shell, catalog, homes, copy):  # FR-2
        env = clean_env(homes, AGENT_KNOWLEDGE_HUB_TOKEN=secrets.token_urlsafe(32))
        result = run([shell, str(copy), "GET", "/cli/api/skills/summary"], env)
        assert result.returncode == 3 and catalog.requests == []

    def test_same_home_named_once(self, shell, catalog, homes, tmp_path):  # FR-7 first case
        same = make_copy(tmp_path, f"http://127.0.0.1:{catalog.port}", str(homes["session"]))
        result = run([shell, str(same), "GET", "/cli/api/skills/summary"], clean_env(homes))
        assert result.returncode == 3
        assert last_err(result) == f"agent-knowledge-hub: no token file: {homes['session'] / TOKEN_FILE}"


# ---------------------------------------------------------------------------
# AC-3 and FR-5: refusals and the route table
# ---------------------------------------------------------------------------

REFUSED = [
    ("GET", "https://evil.example/x"),
    ("GET", "/api/skills/summary"),
    ("GET", "/cli/api/skills/../../x"),
    ("GET", "/cli/api/./skills/summary"),
    ("GET", "/cli/api/skills/x/."),
    ("GET", "/cli/api//skills/summary"),
    ("GET", "/cli/api/skills/%2e%2e"),
    ("GET", "/cli/api/skills/a\\b"),
    ("GET", "/cli/api/skills/a b"),
    ("DELETE", "/cli/api/skills/x"),
    ("--url", "https://evil.example/"),
    ("-K", "/cli/api/skills/summary"),
    ("GET", "--config"),
    ("GET", "-x"),
    ("POST", "/cli/api/admin/skills/x/deactivate"),
    ("POST", "/cli/api/skills/x/flag"),
    ("GET", "/cli/api/skills/"),
    ("GET", "/cli/api/skills/a/b"),
    ("POST", "/cli/api/me/installs/a/b"),
    ("POST", "/cli/api/skills//rate"),
    ("GET", "/cli/api/skillsets"),
    ("GET", "/cli/api/skillsets/"),
    ("GET", "/cli/api/skillsets/a/b"),
    ("GET", "/cli/api/skillsets/a/skills/b"),
]

ROUTES = [
    ("GET", "/cli/api/skills/summary"),
    ("GET", "/cli/api/skills/x"),
    ("POST", "/cli/api/me/installs/x"),
    ("POST", "/cli/api/skills/x/rate"),
    ("POST", "/cli/api/skills"),
    ("GET", "/cli/api/skillsets/x"),
]


@each_shell
class TestRefusals:
    @pytest.mark.parametrize("method,path", REFUSED)
    def test_refused_argument_sends_nothing(self, shell, catalog, homes, copy, method, path):  # AC-3
        write_token(homes["real"])
        result = run([shell, str(copy), method, path], clean_env(homes))
        assert result.returncode == 2
        assert catalog.requests == [] and result.stdout == b""
        assert last_err(result).startswith("agent-knowledge-hub: refused ")

    def test_third_argument_refused(self, shell, catalog, homes, copy):  # AC-3
        write_token(homes["real"])
        result = run([shell, str(copy), "GET", "/cli/api/skills/summary", "-o/tmp/x"], clean_env(homes))
        assert result.returncode == 2 and catalog.requests == []

    def test_missing_argument_refused(self, shell, catalog, homes, copy):
        write_token(homes["real"])
        result = run([shell, str(copy), "GET"], clean_env(homes))
        assert result.returncode == 2 and catalog.requests == []

    @pytest.mark.parametrize("method,path", ROUTES)
    def test_route_table_both_directions(self, shell, catalog, homes, copy, method, path):  # FR-5
        write_token(homes["real"])
        result = run([shell, str(copy), method, path], clean_env(homes), stdin=b"{}")
        assert result.returncode == 0
        assert [(r["method"], r["path"]) for r in catalog.requests] == [(method, path)]
        other = "POST" if method == "GET" else "GET"
        refused = run([shell, str(copy), other, path], clean_env(homes), stdin=b"{}")
        assert refused.returncode == 2 and len(catalog.requests) == 1

    def test_arguments_checked_before_token_file(self, shell, catalog, homes, copy):  # FR-10
        result = run([shell, str(copy), "GET", "/etc/passwd"], clean_env(homes))
        assert result.returncode == 2


@pytest.mark.parametrize("shell", BASH_AS_SH, ids=["bash-as-sh"] * len(BASH_AS_SH))
class TestExportedFunctions:
    def test_exported_bracket_and_test_cannot_pass_a_refusal(self, shell, catalog, homes, copy):  # FR-4
        write_token(homes["real"])
        env = clean_env(homes, **{"BASH_FUNC_[%%": "() { return 0; }", "BASH_FUNC_test%%": "() { return 0; }"})
        result = run([shell, str(copy), "GET", "/cli/api/skills/summary", "third"], env)
        assert result.returncode == 2 and catalog.requests == []

    @needs_proc
    @pytest.mark.parametrize("name", ["printf", "tr"])
    def test_exported_function_receives_no_token(self, shell, catalog, homes, copy, tmp_path, name):
        token = write_token(homes["real"])
        leak = tmp_path / "leak"
        env = clean_env(homes, **{f"BASH_FUNC_{name}%%": f"() {{ /usr/bin/cat > {leak}; /usr/bin/printf '%s ' \"$@\" >> {leak}; }}"})
        run([shell, str(copy), "GET", "/cli/api/skills/summary"], env)
        assert not leak.exists() or token.encode() not in leak.read_bytes()


@needs_proc
@each_shell
def test_fake_tr_on_path_receives_no_token(shell, catalog, homes, copy, tmp_path):
    token = write_token(homes["real"])
    bindir = tmp_path / "bin"
    bindir.mkdir()
    leak = tmp_path / "leak"
    (bindir / "tr").write_text(f"#!/bin/sh\n/usr/bin/cat > {leak}\n")
    (bindir / "tr").chmod(0o755)
    env = clean_env(homes, PATH=f"{bindir}:/usr/bin:/bin")
    result = run([shell, str(copy), "GET", "/cli/api/skills/summary"], env)
    assert result.returncode == 0
    assert not leak.exists() or token.encode() not in leak.read_bytes()


# ---------------------------------------------------------------------------
# AC-8, AC-4 and FR-10: outcomes
# ---------------------------------------------------------------------------

@needs_proc
@each_shell
class TestOutcomes:
    @pytest.mark.parametrize("status,expected", [(404, 6), (410, 6), (401, 5), (500, 6), (204, 0)])
    def test_http_status_maps_to_exit(self, shell, catalog, homes, copy, status, expected):  # AC-8
        write_token(homes["real"])
        body = b'{"detail": "x", "superseded_by_slug": "newer"}' if status != 204 else b""
        catalog.responses["/cli/api/skills/x"] = ("json", status, body)
        result = run([shell, str(copy), "GET", "/cli/api/skills/x"], clean_env(homes))
        assert result.returncode == expected
        assert result.stdout == body
        assert last_err(result) == f"agent-knowledge-hub: HTTP {status}"

    def test_no_listener_is_network_error(self, shell, homes, tmp_path):  # AC-8
        write_token(homes["real"])
        dead = make_copy(tmp_path, f"http://127.0.0.1:{free_port()}", str(homes["real"]))
        result = run([shell, str(dead), "GET", "/cli/api/skills/summary"], clean_env(homes))
        assert result.returncode == 7 and result.stdout == b""
        assert re.fullmatch(r"agent-knowledge-hub: network error \(curl exit \d+\)", last_err(result))

    def test_truncated_response_is_network_error(self, shell, catalog, homes, copy):  # FR-10
        write_token(homes["real"])
        catalog.responses["/cli/api/skills/summary"] = ("truncate",)
        result = run([shell, str(copy), "GET", "/cli/api/skills/summary"], clean_env(homes))
        assert result.returncode == 7 and result.stdout == b""
        assert last_err(result) == "agent-knowledge-hub: network error (curl exit 18)"

    def test_redirect_not_followed(self, shell, catalog, second, homes, copy):  # AC-4
        write_token(homes["real"])
        target = f"http://127.0.0.1:{second.port}/cli/api/skills/summary"
        catalog.responses["/cli/api/skills/summary"] = ("json", 302, b"", {"Location": target})
        result = run([shell, str(copy), "GET", "/cli/api/skills/summary"], clean_env(homes))
        assert result.returncode == 6
        assert second.requests == []

    def test_exit_zero_stderr_is_only_the_status_line(self, shell, catalog, homes, copy):  # FR-4, FR-10
        write_token(homes["real"])
        result = run([shell, str(copy), "GET", "/cli/api/skills/summary"], clean_env(homes))
        assert result.returncode == 0
        assert result.stderr == b"\nagent-knowledge-hub: HTTP 200\n"

    def test_missing_tmpdir_fails_before_sending(self, shell, catalog, homes, copy):  # FR-10
        write_token(homes["real"])
        result = run([shell, str(copy), "GET", "/cli/api/skills/summary"], clean_env(homes, TMPDIR="/nonexistent/dir"))
        assert result.returncode == 1 and result.stdout == b"" and catalog.requests == []

    def test_no_file_left_in_tmpdir(self, shell, catalog, homes, copy):  # FR-10
        write_token(homes["real"])
        catalog.responses["/cli/api/skills/x"] = ("json", 404, b"{}")
        catalog.responses["/cli/api/skills/y"] = ("truncate",)
        codes = [run([shell, str(copy), "GET", path], clean_env(homes)).returncode
                 for path in ("/cli/api/skills/summary", "/cli/api/skills/x", "/cli/api/skills/y")]
        assert codes == [0, 6, 7]
        assert list(homes["tmp"].iterdir()) == []

    def test_symlink_swapped_into_tmpdir_is_not_written_through(self, shell, catalog, homes, copy, tmp_path):
        write_token(homes["real"])
        target = tmp_path / "victim"
        target.write_bytes(b"unchanged")
        stop = threading.Event()

        def swap():
            while not stop.is_set():
                for entry in homes["tmp"].iterdir():
                    try:
                        entry.unlink()
                        entry.symlink_to(target)
                    except OSError:
                        pass

        swapper = threading.Thread(target=swap, daemon=True)
        swapper.start()
        try:
            results = [run([shell, str(copy), "GET", "/cli/api/skills/summary"], clean_env(homes)) for _ in range(20)]
        finally:
            stop.set()
            swapper.join(5)
        assert target.read_bytes() == b"unchanged"
        assert all(r.stdout == b'{"ok": true}' for r in results if r.returncode == 0)
        assert any(r.returncode == 0 for r in results)


# ---------------------------------------------------------------------------
# AC-2: the token is in no process's arguments or environment and in no output
# ---------------------------------------------------------------------------

def _scan_proc(token: bytes) -> list[str]:
    hits = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        for part in ("cmdline", "environ"):
            try:
                if token in (entry / part).read_bytes():
                    hits.append(f"{entry.name}/{part}")
            except OSError:
                pass
    return hits


def _held_run(argv, env, catalog, token: bytes):
    catalog.hold_paths.add("/cli/api/skills/summary")
    proc = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    try:
        assert catalog.held.wait(10), "the helper never reached the fake catalog"
        hits = _scan_proc(token)
        tmpdir = Path(env["TMPDIR"])
        hits += [f"TMPDIR/{p.name}" for p in tmpdir.iterdir() if p.is_file() and token in p.read_bytes()]
    finally:
        catalog.hold.set()
    out, err = proc.communicate(timeout=20)
    return proc.returncode, out, err, hits


@needs_proc
@each_shell
class TestTokenExposure:
    @pytest.mark.parametrize("flags,extra", [([], {}), (["-x"], {}), (["-a"], {}), ([], {"tok": "exported"})])
    def test_token_absent_from_processes_and_output(self, shell, catalog, homes, copy, flags, extra):  # AC-2
        token = write_token(homes["real"]).encode()
        rc, out, err, hits = _held_run([shell, *flags, str(copy), "GET", "/cli/api/skills/summary"],
                                       clean_env(homes, **extra), catalog, token)
        assert rc == 0
        assert hits == [], f"token found in {hits}"
        assert token not in out and token not in err

    def test_sigterm_leaves_no_file(self, shell, catalog, homes, copy):  # FR-10
        write_token(homes["real"])
        catalog.hold_paths.add("/cli/api/skills/summary")
        proc = subprocess.Popen([shell, str(copy), "GET", "/cli/api/skills/summary"], env=clean_env(homes),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        assert catalog.held.wait(10)
        proc.send_signal(signal.SIGTERM)
        proc.wait(10)
        catalog.hold.set()
        assert list(homes["tmp"].iterdir()) == []


@needs_proc
@pytest.mark.parametrize("shell", BASH_AS_SH, ids=["bash-as-sh"] * len(BASH_AS_SH))
def test_shellopts_xtrace_does_not_leak(shell, catalog, homes, copy):  # AC-2
    token = write_token(homes["real"]).encode()
    rc, out, err, hits = _held_run([shell, str(copy), "GET", "/cli/api/skills/summary"],
                                   clean_env(homes, SHELLOPTS="xtrace"), catalog, token)
    assert rc == 0 and hits == [] and token not in err


# ---------------------------------------------------------------------------
# AC-10 and FR-10: bodies and shared output files
# ---------------------------------------------------------------------------

@needs_proc
@each_shell
class TestBodiesAndOutput:
    def test_large_post_body_arrives_whole_as_json(self, shell, catalog, homes, copy):  # AC-10, FR-5
        write_token(homes["real"])
        body = os.urandom(300_000)
        result = run([shell, str(copy), "POST", "/cli/api/skills"], clean_env(homes), stdin=body, timeout=60)
        assert result.returncode == 0
        request = catalog.requests[0]
        assert request["body_len"] == len(body)
        assert request["body_sha"] == hashlib.sha256(body).hexdigest()
        assert request["content_type"] == "application/json"

    def test_bodiless_post_sends_empty_body(self, shell, catalog, homes, copy):  # FR-10
        write_token(homes["real"])
        result = run([shell, str(copy), "POST", "/cli/api/me/installs/x"], clean_env(homes), stdin=subprocess.DEVNULL)
        assert result.returncode == 0
        assert catalog.requests[0]["content_length"] == "0"

    def test_get_never_reads_stdin(self, shell, catalog, homes, copy):  # FR-10
        write_token(homes["real"])
        reader, writer = os.pipe()
        try:
            result = run([shell, str(copy), "GET", "/cli/api/skills/summary"], clean_env(homes), stdin=reader, timeout=10)
        finally:
            os.close(reader)
            os.close(writer)
        assert result.returncode == 0 and catalog.requests[0]["body_len"] == 0

    def test_two_calls_into_one_file(self, shell, catalog, homes, copy, tmp_path):  # AC-10
        write_token(homes["real"])
        out = tmp_path / "out.txt"
        script = (f"echo before; {shell} {copy} GET /cli/api/skills/summary; echo between; "
                  f"{shell} {copy} GET /cli/api/skills/x; echo after")
        catalog.responses["/cli/api/skills/x"] = ("json", 200, b'{"second": true}')
        with out.open("wb") as f:
            subprocess.run(["/bin/sh", "-c", script], env=clean_env(homes), stdout=f, stderr=f, timeout=30)
        data = out.read_bytes()
        assert b"\0" not in data
        order = [data.index(x) for x in (b"before", b'{"ok": true}', b"between", b'{"second": true}', b"after")]
        assert order == sorted(order)

    def test_status_line_on_its_own_line(self, shell, catalog, homes, copy, tmp_path):  # FR-10
        write_token(homes["real"])
        catalog.responses["/cli/api/skills/x"] = ("json", 200, b"no-newline")
        out = tmp_path / "out.txt"
        with out.open("wb") as f:
            subprocess.run([shell, str(copy), "GET", "/cli/api/skills/x"], env=clean_env(homes), stdout=f, stderr=f, timeout=20)
        assert out.read_bytes() == b"no-newline\nagent-knowledge-hub: HTTP 200\n"


# ---------------------------------------------------------------------------
# AC-9 and FR-5: curl's environment
# ---------------------------------------------------------------------------

@pytest.fixture
def tls_catalog(tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=1))
            .not_valid_after(now + datetime.timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    cert_path, key_path = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    fake = FakeCatalog(tls_context=context)
    fake.cert_path = cert_path
    yield fake
    fake.close()


@needs_proc
@each_shell
class TestCurlEnvironment:
    @pytest.mark.parametrize("var", ["CURL_CA_BUNDLE", "SSL_CERT_FILE", "SSL_CERT_DIR"])
    def test_trust_variables_ignored(self, shell, tls_catalog, homes, tmp_path, var):  # AC-9
        write_token(homes["real"])
        tls_copy = make_copy(tmp_path, f"https://127.0.0.1:{tls_catalog.port}", str(homes["real"]))
        value = str(tls_catalog.cert_path.parent) if var == "SSL_CERT_DIR" else str(tls_catalog.cert_path)
        if var == "SSL_CERT_DIR":
            subprocess.run(["openssl", "rehash", value], capture_output=True)
        keylog = tmp_path / "keys.log"
        env = clean_env(homes, **{var: value, "SSLKEYLOGFILE": str(keylog)})
        result = run([shell, str(tls_copy), "GET", "/cli/api/skills/summary"], env)
        assert result.returncode == 7
        assert last_err(result) == "agent-knowledge-hub: network error (curl exit 60)"
        assert tls_catalog.requests == []
        assert not keylog.exists()

    def test_proxy_variables_kept(self, shell, catalog, second, homes, copy):  # FR-5
        write_token(homes["real"])
        env = clean_env(homes, http_proxy=f"http://127.0.0.1:{second.port}")
        run([shell, str(copy), "GET", "/cli/api/skills/summary"], env)
        assert len(second.requests) == 1 and catalog.requests == []


# ---------------------------------------------------------------------------
# Static checks on the shipped files
# ---------------------------------------------------------------------------

ALLOWED_FRONTMATTER = {"name", "description", "when_to_use", "argument-hint", "arguments", "version", "license",
                       "metadata", "disable-model-invocation", "user-invocable", "disallowed-tools"}

FR7_LINES = [
    "No S3DF sign-in found at",
    "does not hold a valid token.",
    "The catalog did not accept your S3DF sign-in. It has most likely expired.",
    "To sign in again:",
    "In Cogito: open Cogito in a new private browser window and sign in.",
    "On an S3DF node outside Cogito: run  s3df login",
    "(if the shell cannot find s3df: /sdf/sw/s3df-cli/bin/s3df login)",
    "On a computer outside S3DF: use this client from Cogito or from an S3DF node.",
    "Then ask again here; this session does not need to restart.",
    "The hub client refused a request it does not make",
    "The catalog answered with a redirect (HTTP",
    "The catalog's certificate could not be checked against this computer's own certificates (curl exit 60).",
    "The hub client failed before sending a request:",
    "A rule for all of sh would let any shell command run without asking.",
]


class TestShippedFiles:
    def test_origin_is_production(self):
        assert ORIGIN_LINE in [l.strip() for l in HELPER.read_text().splitlines()]

    def test_helper_runs_no_bracket_command(self):  # FR-4
        pattern = re.compile(r"(^|[;&|(!]|\b(if|elif|then|while|until))\s*\[\s")
        offenders = [l for l in HELPER.read_text().splitlines()
                     if not l.lstrip().startswith("#") and pattern.search(l)]
        assert offenders == []

    def test_no_symlink_in_skill_folder(self):
        assert [p for p in SKILL_DIR.rglob("*") if p.is_symlink()] == []

    def test_skill_md_frontmatter_and_no_inline_shell(self):  # AC-7
        text = SKILL_MD.read_text()
        front = text.split("---")[1]
        keys = {line.split(":", 1)[0].strip() for line in front.splitlines() if line.strip() and not line.startswith(" ")}
        assert keys <= ALLOWED_FRONTMATTER
        assert "!`" not in text and "```!" not in text

    def test_skill_md_routes_catalog_requests_through_helper(self):  # FR-1, FR-6
        text = SKILL_MD.read_text()
        assert "hub-request.sh" in text
        assert "Authorization: Bearer" not in text
        assert "AGENT_KNOWLEDGE_HUB_TOKEN" not in text
        assert not re.search(r"(GET|POST) `?/api/", text), "a catalog request path does not start with /cli/api/"

    @pytest.mark.parametrize("line", FR7_LINES)
    def test_skill_md_carries_fr7_messages(self, line):  # FR-7
        assert line in SKILL_MD.read_text()
