# Runbook: image digest pinning

Production runs the hub's images by digest, not by tag (TODO #034). A deployment's image line reads `slaclab/agent-knowledge-hub-backend:0.20.0@sha256:<digest>`. Kubernetes pulls the manifest with that digest and refuses anything else, so re-pushing the `0.20.0` tag, by mistake or by an attacker with Docker Hub access, cannot change what a restarted pod runs. The tag stays in the line so that people and logs can read the version.

Dev is not pinned. Its deployments run `:latest`, and a dev release is a rollout restart (ADR-034-3). That is why `make containers` still pushes `:latest` as well as the version tag.

## Which files are pinned

`make pin-digests` rewrites six files:

| File | Applied to |
|---|---|
| `ai-playground-deploy/kubernetes/overlays/prod/agent-knowledge-hub/backend-deployment.yaml` | prod |
| `ai-playground-deploy/kubernetes/overlays/prod/agent-knowledge-hub/frontend-deployment.yaml` | prod |
| `kubernetes/overlays/{prod,stage}/{backend,frontend}-deployment.yaml` in this repository | nothing; kept in step as reference copies |

## Pin a release

Run these from this repository's root, after `make containers` has pushed the release's images.

1. Pin the manifests to the digests Docker Hub serves for the release tag:

   ```bash
   make pin-digests
   ```

   The tag defaults to the version in `backend/pyproject.toml`; pass `TAG=X.Y.Z` to pin another. The command prints one `repository:tag@digest` line per image. It looks up every digest before it writes any file, so a tag that is not on Docker Hub, or a registry error, exits 1 and changes nothing.

2. Check that the prod diff changes only the two image lines:

   ```bash
   KUBECONFIG=~/.kube/config.sage kubectl diff -k ../ai-playground-deploy/kubernetes/overlays/prod/agent-knowledge-hub/
   ```

3. Commit the two prod files in `ai-playground-deploy`, and the four copies in this repository, then apply as `.claude/skills/deploy/SKILL.md` describes.

`scripts/pin_image_digests.py` uses only Python's standard library and asks Docker Hub's registry API anonymously, with a `HEAD` request that does not count against the pull rate limit.

## Verify a running pod

The digest a pod runs is in its status:

```bash
KUBECONFIG=~/.kube/config.sage kubectl -n prod get pods -l app=agent-knowledge-hub-backend \
  -o jsonpath='{.items[*].status.containerStatuses[0].imageID}'
```

It must equal the digest in the manifest's image line.

To look up a digest by hand, without the script:

```bash
token=$(curl -s 'https://auth.docker.io/token?service=registry.docker.io&scope=repository:slaclab/agent-knowledge-hub-backend:pull' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
curl -s -I -H "Authorization: Bearer $token" \
  -H 'Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json' \
  https://registry-1.docker.io/v2/slaclab/agent-knowledge-hub-backend/manifests/X.Y.Z | grep -i docker-content-digest
```

The local image ID that `podman image inspect` reports is not this digest: podman can rewrite the manifest when it pushes.

## Roll back

A pod whose digest cannot be pulled never becomes ready, and the old pods keep serving.

- To return to the previous release, run `kubectl -n prod rollout undo deployment/agent-knowledge-hub-backend`, and the same for `agent-knowledge-hub-frontend`. The previous ReplicaSet already holds the previous pinned reference.
- To pin again after a tag was re-pushed on purpose, rerun `make pin-digests`, review the new digest, and apply.
- To drop pinning in an emergency, edit the image line back to `name:tag` and apply. This gives up the protection, so pin again at the next release.
