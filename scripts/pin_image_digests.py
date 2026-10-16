#!/usr/bin/env python3
"""Pin the hub's deployment manifests to the registry digests of one image tag (#034).

Usage: pin_image_digests.py TAG FILE [FILE ...]

Every line `image: [docker.io/]slaclab/agent-knowledge-hub-<name>:<old>` in each FILE becomes
`image: ...agent-knowledge-hub-<name>:TAG@sha256:<digest>`, where <digest> is the manifest digest
Docker Hub serves for <name>:TAG. With the digest in the reference, a later re-push of the tag
cannot change what Kubernetes runs. Every digest is looked up before any file is written, so a
missing tag or a registry error leaves all files unchanged.

Exit status: 0 pinned, 1 lookup or file error, 2 bad arguments.
AKH_REGISTRY_URL and AKH_REGISTRY_AUTH_URL replace Docker Hub's endpoints in tests.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

REGISTRY = os.environ.get("AKH_REGISTRY_URL", "https://registry-1.docker.io")
AUTH = os.environ.get("AKH_REGISTRY_AUTH_URL", "https://auth.docker.io/token")
MEDIA_TYPES = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])
TAG_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
IMAGE_RE = re.compile(
    r"^(?P<lead>\s*image:\s*)(?P<host>docker\.io/)?(?P<repo>slaclab/agent-knowledge-hub-[a-z]+)"
    r"(?::[A-Za-z0-9_.-]+)?(?:@sha256:[0-9a-f]{64})?(?P<trail>\s*)$",
    re.M,
)


def fail(message, status=1):
    sys.stderr.write("pin_image_digests: %s\n" % message)
    sys.exit(status)


def digest_of(repo, tag):
    query = urllib.parse.urlencode({"service": "registry.docker.io", "scope": "repository:%s:pull" % repo})
    try:
        with urllib.request.urlopen("%s?%s" % (AUTH, query), timeout=30) as resp:
            token = json.load(resp)["token"]
        request = urllib.request.Request(
            "%s/v2/%s/manifests/%s" % (REGISTRY, repo, tag), method="HEAD",
            headers={"Authorization": "Bearer %s" % token, "Accept": MEDIA_TYPES},
        )
        with urllib.request.urlopen(request, timeout=30) as resp:
            digest = resp.headers.get("Docker-Content-Digest", "")
    except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
        fail("cannot look up %s:%s: %s" % (repo, tag, exc))
    if not DIGEST_RE.fullmatch(digest):
        fail("registry returned no valid digest for %s:%s" % (repo, tag))
    return digest


def main(argv):
    if len(argv) < 2 or not TAG_RE.fullmatch(argv[0]):
        fail("usage: pin_image_digests.py TAG FILE [FILE ...], where TAG is a Docker tag", 2)
    tag, paths = argv[0], argv[1:]
    texts = {}
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                texts[path] = f.read()
        except OSError as exc:
            fail("cannot read %s: %s" % (path, exc))
        if not IMAGE_RE.search(texts[path]):
            fail("no agent-knowledge-hub image line in %s" % path)
    repos = sorted({m.group("repo") for text in texts.values() for m in IMAGE_RE.finditer(text)})
    digests = {repo: digest_of(repo, tag) for repo in repos}
    for path, text in texts.items():
        pinned = IMAGE_RE.sub(lambda m: "%s%s%s:%s@%s%s" % (
            m.group("lead"), m.group("host") or "", m.group("repo"), tag, digests[m.group("repo")], m.group("trail")), text)
        with open(path, "w", encoding="utf-8") as f:
            f.write(pinned)
    for repo in repos:
        print("%s:%s@%s" % (repo, tag, digests[repo]))


if __name__ == "__main__":
    main(sys.argv[1:])
