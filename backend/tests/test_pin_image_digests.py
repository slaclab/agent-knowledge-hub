"""Tests for #034 — scripts/pin_image_digests.py pins the hub's image lines to registry digests.

The script runs against a fake registry in a thread; the real Docker Hub is never contacted.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pin_image_digests.py"

BACKEND_DIGEST = "sha256:" + "b" * 64
FRONTEND_DIGEST = "sha256:" + "f" * 64


class FakeRegistry:
    """Serves an anonymous token and manifest digests, and logs every manifest request."""

    def __init__(self, digests: dict[str, str]):
        self.digests = digests
        self.requests: list[tuple[str, str, str, str]] = []
        registry = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path.startswith("/token?"):
                    body = json.dumps({"token": "anon-token"}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_HEAD(self):
                registry.requests.append((self.command, self.path, self.headers.get("Authorization", ""),
                                          self.headers.get("Accept", "")))
                digest = registry.digests.get(self.path)
                if digest is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Docker-Content-Digest", digest)
                self.end_headers()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


@pytest.fixture
def registry():
    reg = FakeRegistry({
        "/v2/slaclab/agent-knowledge-hub-backend/manifests/0.20.0": BACKEND_DIGEST,
        "/v2/slaclab/agent-knowledge-hub-frontend/manifests/0.20.0": FRONTEND_DIGEST,
    })
    yield reg
    reg.close()


def run(registry: FakeRegistry, *args: str) -> subprocess.CompletedProcess:
    env = {"AKH_REGISTRY_URL": registry.url, "AKH_REGISTRY_AUTH_URL": f"{registry.url}/token", "PATH": "/usr/bin:/bin"}
    return subprocess.run([sys.executable, str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=30)


DEPLOYMENT = """apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: {name}
          image: slaclab/agent-knowledge-hub-{name}:{ref}
          imagePullPolicy: Always
"""


def write(tmp_path: Path, name: str, ref: str = "0.19.1") -> Path:
    path = tmp_path / f"{name}-deployment.yaml"
    path.write_text(DEPLOYMENT.format(name=name, ref=ref))
    return path


def test_pins_each_image_to_its_digest(tmp_path, registry):
    backend, frontend = write(tmp_path, "backend"), write(tmp_path, "frontend")
    result = run(registry, "0.20.0", str(backend), str(frontend))
    assert result.returncode == 0, result.stderr
    assert backend.read_text() == DEPLOYMENT.format(name="backend", ref=f"0.20.0@{BACKEND_DIGEST}")
    assert frontend.read_text() == DEPLOYMENT.format(name="frontend", ref=f"0.20.0@{FRONTEND_DIGEST}")
    assert f"slaclab/agent-knowledge-hub-backend:0.20.0@{BACKEND_DIGEST}" in result.stdout


def test_repins_an_already_pinned_line(tmp_path, registry):
    backend = write(tmp_path, "backend", ref="0.19.1@sha256:" + "0" * 64)
    assert run(registry, "0.20.0", str(backend)).returncode == 0
    assert backend.read_text() == DEPLOYMENT.format(name="backend", ref=f"0.20.0@{BACKEND_DIGEST}")


def test_requests_carry_the_token_and_manifest_types(tmp_path, registry):
    assert run(registry, "0.20.0", str(write(tmp_path, "backend"))).returncode == 0
    (method, path, auth, accept), = registry.requests
    assert (method, path, auth) == ("HEAD", "/v2/slaclab/agent-knowledge-hub-backend/manifests/0.20.0", "Bearer anon-token")
    for media_type in ("application/vnd.oci.image.manifest.v1+json", "application/vnd.oci.image.index.v1+json",
                       "application/vnd.docker.distribution.manifest.v2+json",
                       "application/vnd.docker.distribution.manifest.list.v2+json"):
        assert media_type in accept


def test_missing_tag_writes_nothing(tmp_path, registry):
    backend, frontend = write(tmp_path, "backend"), write(tmp_path, "frontend")
    del registry.digests["/v2/slaclab/agent-knowledge-hub-frontend/manifests/0.20.0"]
    result = run(registry, "0.20.0", str(backend), str(frontend))
    assert result.returncode == 1
    assert "agent-knowledge-hub-frontend:0.20.0" in result.stderr
    assert backend.read_text() == DEPLOYMENT.format(name="backend", ref="0.19.1")
    assert frontend.read_text() == DEPLOYMENT.format(name="frontend", ref="0.19.1")


def test_malformed_digest_writes_nothing(tmp_path, registry):
    backend = write(tmp_path, "backend")
    registry.digests["/v2/slaclab/agent-knowledge-hub-backend/manifests/0.20.0"] = "sha256:not-hex"
    assert run(registry, "0.20.0", str(backend)).returncode == 1
    assert backend.read_text() == DEPLOYMENT.format(name="backend", ref="0.19.1")


def test_file_without_a_hub_image_line_fails(tmp_path, registry):
    other = tmp_path / "other.yaml"
    other.write_text("image: nginx:1.27\n")
    backend = write(tmp_path, "backend")
    result = run(registry, "0.20.0", str(backend), str(other))
    assert result.returncode == 1
    assert "other.yaml" in result.stderr
    assert backend.read_text() == DEPLOYMENT.format(name="backend", ref="0.19.1")


@pytest.mark.parametrize("tag", ["", "0.20.0 x", "../0.20.0", "0.20.0@sha256:x", "-x"])
def test_bad_tag_is_refused(tmp_path, registry, tag):
    backend = write(tmp_path, "backend")
    result = run(registry, tag, str(backend))
    assert result.returncode == 2
    assert registry.requests == []
    assert backend.read_text() == DEPLOYMENT.format(name="backend", ref="0.19.1")
