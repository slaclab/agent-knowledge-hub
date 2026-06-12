# 034 — Security: Pin Production Images to Digest, Not Mutable Tags

**Status:** ⬜ Open
**Severity:** HIGH
**Source:** Security review 2026-06-09 (H5)

---

## Phase 1 — Problem & Goal

### What is broken today

All four stage/prod deployment manifests reference images by a mutable semver tag with `imagePullPolicy: Always`:

- `kubernetes/overlays/prod/backend-deployment.yaml` line 17: `slaclab/agent-knowledge-hub-backend:0.2.0`
- `kubernetes/overlays/prod/frontend-deployment.yaml` line 17: `slaclab/agent-knowledge-hub-frontend:0.2.0`
- `kubernetes/overlays/stage/backend-deployment.yaml` line 17: `slaclab/agent-knowledge-hub-backend:0.2.0`
- `kubernetes/overlays/stage/frontend-deployment.yaml` line 17: `slaclab/agent-knowledge-hub-frontend:0.2.0`

If Docker Hub is compromised or a tag is accidentally overwritten, the next pod restart silently pulls and runs malicious or corrupted code with no audit trail. Because `imagePullPolicy: Always` is set in every deployment, this happens on every rollout-restart, node failure, or re-schedule event.

Secondary issue: the release pipeline in `backend/Makefile` line 31-34 (`docker-push`) also pushes a `:latest` tag — a second mutable reference that nothing currently blocks from being used.

Version skew: prod/stage manifests still reference `0.2.0` while dev is at `0.6.0` and the application is at `0.17.0`. The manifests are stale — the digest pinning work must also correct the referenced versions.

### What success looks like

- Prod and stage manifests reference images as `name:tag@sha256:<digest>` — Kubernetes will reject any image that does not match the digest, even if the tag is re-pushed.
- The root `Makefile` `docker-push` workflow captures the digest immediately after push and writes it into the manifests before `kubectl apply` runs.
- Manifest image versions match the actual deployed application version.
- Dev overlay remains on mutable tags (acceptable for development velocity).

### Out of scope

- Signing images with cosign or Notary — useful but a separate initiative.
- Changing the container registry (Docker Hub stays).
- Removing `imagePullPolicy: Always` — this is kept so digest rotation still triggers a pull.

### Constraints

- Must deploy via `kubectl apply -k .` (kustomize) — no Helm, no external CD operator.
- Must not interrupt traffic during rollout (rolling update strategy already in place, replicas ≥ 1 in all overlays).
- `crane` or `skopeo` must be available on the operator workstation; if not, `docker manifest inspect` is the fallback.
- Must not require CI/CD infrastructure changes — the workflow is Makefile-driven from an operator laptop.

---

## Phase 2 — Requirements / Feasibility

### Overlays affected

| Overlay | Backend manifest | Frontend manifest | Action |
|---|---|---|---|
| prod | `backend-deployment.yaml` line 17 | `frontend-deployment.yaml` line 17 | Pin digest + correct version to `0.17.0` |
| stage | `backend-deployment.yaml` line 17 | `frontend-deployment.yaml` line 17 | Pin digest + correct version to `0.17.0` |
| dev | `backend-deployment.yaml` line 17 | `frontend-deployment.yaml` line 17 | No change required (dev velocity) |

### New Kubernetes resources required

None. This is a manifest field change only — no new objects, no new RBAC, no NetworkPolicy changes.

### Risk of breaking existing traffic

Minimal. Each deployment uses a rolling update strategy (Kubernetes default). The digest-pinned image is the same binary as the tag-referenced image — just verified. Pods replace one at a time. If the new spec is rejected (e.g., digest mismatch), the rollout stalls but existing pods continue serving traffic.

### Rollback feasibility

Immediate: revert the `image:` field in the relevant deployment YAML to the previous tag-only reference and `make apply`. The rollback is a one-line change per file.

---

## Phase 3 — ADRs

**ADR-034-1: Use `name:tag@sha256:digest` format rather than digest-only**

Status: Accepted

Context: Kubernetes accepts both `image@sha256:digest` (digest-only) and `name:tag@sha256:digest` (tag + digest). A decision was needed on which form to use in manifests.

Options considered:
| Option | Human readable | Registry fallback if digest missing | Pinned |
|---|---|---|---|
| `name:tag` only | Yes | Yes | No |
| `name@sha256:digest` | No | No | Yes |
| `name:tag@sha256:digest` | Yes | No | Yes |

Decision: `name:tag@sha256:digest`. The tag is preserved for human readability in `kubectl get pods` and log pipelines. The digest is the enforcement mechanism. If the digest does not match what the registry serves for the tag, the pull is rejected — the tag has no influence on what runs.

Consequences: The manifest YAML is slightly longer. When a new version is released, both the tag and the digest must be updated together — the release automation (Phase 3.5) handles this.

---

**ADR-034-2: Embed digest capture in the per-overlay Makefile `docker-push` target**

Status: Accepted

Context: Digest capture must happen between "image is pushed to registry" and "manifest is applied to the cluster". The question is where to embed this step.

Options considered:
- Add to root `Makefile` `docker-push` target (shared, but detached from overlay application)
- Add a new `pin-digests` target in each overlay Makefile, called by `apply`
- Add inline to each overlay `apply` target

Decision: Add a `pin-digests` target in each overlay Makefile that is called as a prerequisite of `apply`. This keeps overlay-specific logic in the overlay Makefile, uses `crane digest` (or `skopeo inspect`) as the tool, and writes the result via `kustomize edit set image`. The root `Makefile` `prod-deploy` and `dev-deploy` targets already call the overlay `apply` — no changes needed there.

Consequences: Operators need `crane` (or `skopeo`) on their PATH. A one-time install step is added to the runbook.

---

**ADR-034-3: Do not pin dev overlay images**

Status: Accepted

Context: Dev runs at one replica for rapid iteration. Pinning dev would require a digest update on every dev image push, slowing the inner development loop.

Decision: Dev overlay remains on mutable tag references. The security risk is acceptable for a non-production environment with no sensitive data. If dev is ever promoted to a data-bearing environment, this decision should be revisited.

Consequences: Dev images are not supply-chain hardened. This is a known and accepted gap.

---

## Phase 3.5 — Migration / Transition Path

### Zero-downtime rollout

Yes. Each deployment has rolling update semantics. The digest-pinned image is identical content to the tag-only image (same SHA) — the only change is that Kubernetes now validates the digest on pull. Rolling replace proceeds pod by pod.

### Rollout order

1. **Stage first** — apply digest-pinned stage manifests, verify both deployments reach `Ready` state, smoke test the stage endpoint.
2. **Prod second** — apply digest-pinned prod manifests only after stage is confirmed healthy.
3. Dev: no action.

### Rollback procedure

If a stage or prod deployment stalls after applying digest-pinned manifests:

```bash
# Revert the image field to the previous tag-only reference
# e.g. kubernetes/overlays/prod/backend-deployment.yaml line 17
# Change: slaclab/agent-knowledge-hub-backend:0.17.0@sha256:<digest>
# Back to: slaclab/agent-knowledge-hub-backend:0.17.0
make -C kubernetes/overlays/prod apply
```

A failed pull due to digest mismatch leaves existing pods running — no availability loss.

---

## Phase 4 — System / Infrastructure Design

### Manifest changes

**Before (prod and stage, both backend and frontend):**
```yaml
# kubernetes/overlays/prod/backend-deployment.yaml  line 17
image: slaclab/agent-knowledge-hub-backend:0.2.0
# kubernetes/overlays/prod/frontend-deployment.yaml line 17
image: slaclab/agent-knowledge-hub-frontend:0.2.0
# (stage identical)
```

**After:**
```yaml
# kubernetes/overlays/prod/backend-deployment.yaml  line 17
image: slaclab/agent-knowledge-hub-backend:0.17.0@sha256:<backend-digest>
# kubernetes/overlays/prod/frontend-deployment.yaml line 17
image: slaclab/agent-knowledge-hub-frontend:0.17.0@sha256:<frontend-digest>
# (stage identical — same version, same digests)
```

### Makefile changes

**`kubernetes/overlays/prod/Makefile`** — add `pin-digests` target and wire into `apply`:

```makefile
VERSION ?= 0.17.0

pin-digests:
	@command -v crane >/dev/null 2>&1 || { echo "crane not found — install: go install github.com/google/go-containerregistry/cmd/crane@latest"; exit 1; }
	$(eval BACKEND_DIGEST := $(shell crane digest $(REGISTRY)/agent-knowledge-hub-backend:$(VERSION)))
	$(eval FRONTEND_DIGEST := $(shell crane digest $(REGISTRY)/agent-knowledge-hub-frontend:$(VERSION)))
	cd $(CURDIR) && kustomize edit set image \
	  $(REGISTRY)/agent-knowledge-hub-backend=$(REGISTRY)/agent-knowledge-hub-backend:$(VERSION)@$(BACKEND_DIGEST) \
	  $(REGISTRY)/agent-knowledge-hub-frontend=$(REGISTRY)/agent-knowledge-hub-frontend:$(VERSION)@$(FRONTEND_DIGEST)
	@echo "Pinned backend  to $(BACKEND_DIGEST)"
	@echo "Pinned frontend to $(FRONTEND_DIGEST)"

apply: ensure-context pin-digests secrets
	kubectl apply -k .
	$(MAKE) clean-secrets
```

Apply the same pattern to `kubernetes/overlays/stage/Makefile`.

Note: `kustomize edit set image` writes the `images:` block in `kustomization.yaml`, overriding the `image:` field in the deployment patches. Alternatively, the `image:` field in each deployment YAML can be sed-replaced; either approach is acceptable as long as the committed file contains the digest reference before `kubectl apply` reads it.

### `backend/Makefile` — remove `:latest` push

Line 31-34 currently pushes `:latest` after the versioned tag. Remove this to eliminate the second mutable reference:

```makefile
# Before (lines 30-34):
docker-push: docker-build
	$(CONTAINER_RT) push $(IMAGE):$(TAG)
	$(CONTAINER_RT) tag $(IMAGE):$(TAG) $(IMAGE):latest
	$(CONTAINER_RT) push $(IMAGE):latest

# After:
docker-push: docker-build
	$(CONTAINER_RT) push $(IMAGE):$(TAG)
```

No NetworkPolicy changes required.

---

## Phase 7 — Trade-offs

| Choice | What we gain | What we give up |
|---|---|---|
| Digest pinning in deployment YAML | Immutable, verifiable image references; supply-chain attack prevention | Manifest must be updated on every release — slight operator overhead |
| `crane` for digest lookup | Simple one-liner, fast, no Docker daemon needed | Requires `crane` binary on operator workstation |
| Pin stage + prod, skip dev | Security where it matters; no inner-loop friction for devs | Dev remains on mutable tags; supply-chain gap in non-prod |
| `name:tag@sha256:digest` format | Human-readable tag preserved in logs and `kubectl` output | Slightly longer YAML; both tag and digest must stay in sync |
| Remove `:latest` push from `backend/Makefile` | Eliminates second mutable registry reference | Any tooling that assumed `:latest` exists will break (none identified) |

---

## Phase 8 — Delivery Slices

### Slice 1 — Correct manifest versions + pin stage (safe to ship alone)

- Update stage backend and frontend deployment YAMLs: set image version from `0.2.0` to `0.17.0` and add digest.
- Add `pin-digests` target to `kubernetes/overlays/stage/Makefile`.
- Apply to stage: `make -C kubernetes/overlays/stage apply`.
- Smoke test stage frontend and `/health` endpoint.

### Slice 2 — Pin prod

- Update prod backend and frontend deployment YAMLs: set image version from `0.2.0` to `0.17.0` and add digest.
- Add `pin-digests` target to `kubernetes/overlays/prod/Makefile`.
- Apply to prod: `make -C kubernetes/overlays/prod apply`.
- Verify both deployments `Ready` and no pod restarts.

### Slice 3 — Harden release pipeline

- Remove `:latest` push from `backend/Makefile` (and `frontend/Makefile` if it has the same pattern).
- Add a `pin-digests` step to the root `Makefile` `prod-deploy` / `all` targets so future releases automatically update manifests with fresh digests before applying.
- Add runbook entry at `docs/runbooks/image-digest-pinning.md` covering: how to retrieve and verify a digest manually, how to rollback if a digest is wrong.

---

## Phase 9 — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `crane` not installed on operator workstation | Medium | Blocks `make apply` | Fallback: `skopeo inspect --raw docker://... \| jq -r .config.digest` or `docker manifest inspect`; document in runbook |
| Digest mismatch — image re-pushed under same tag after digest captured | Low | Deployment stalls; existing pods keep running | Re-run `pin-digests` to refresh digest; rolling update resumes |
| Stale version in manifests after initial fix | Low | Security regression on next release | Slice 3 (automation) prevents this; checklist item in release runbook |
| Docker Hub rate-limiting `crane digest` calls | Low | Slow CI / blocked pipeline | `crane` uses anonymous pulls; add Docker Hub credentials to operator env if rate-limited |
| `:latest` tag removal breaks an internal tool | Very low | Minor operational disruption | No tooling was found referencing `:latest`; verify with `grep -r latest kubernetes/` before removing |

---

## Phase 10 — Definition of Done

- [ ] `kubernetes/overlays/stage/backend-deployment.yaml` image field uses `name:0.17.0@sha256:<digest>` format
- [ ] `kubernetes/overlays/stage/frontend-deployment.yaml` image field uses `name:0.17.0@sha256:<digest>` format
- [ ] `kubernetes/overlays/prod/backend-deployment.yaml` image field uses `name:0.17.0@sha256:<digest>` format
- [ ] `kubernetes/overlays/prod/frontend-deployment.yaml` image field uses `name:0.17.0@sha256:<digest>` format
- [ ] Digests verified with `crane digest` or `docker manifest inspect` — output matches manifest
- [ ] `pin-digests` Makefile target present in both stage and prod overlay Makefiles
- [ ] `backend/Makefile` no longer pushes `:latest` tag
- [ ] `make diff` on prod overlay shows only the `image:` field change (no unintended diffs)
- [ ] Stage deployment smoke test passes (frontend loads, `/health` returns 200)
- [ ] Prod deployment smoke test passes (frontend loads, `/health` returns 200, no unexpected pod restarts)
- [ ] Rollback procedure documented in `docs/runbooks/image-digest-pinning.md`
- [ ] This task file status updated to `✅ Done` after all items above are checked

---

## Original Implementation Plan (retained for reference)

- [ ] Retrieve current SHA256 digests for both images at the current deployed version
- [ ] Update `kubernetes/overlays/prod/backend-deployment.yaml` to use digest-pinned reference
- [ ] Update `kubernetes/overlays/prod/frontend-deployment.yaml` to use digest-pinned reference
- [ ] Update `kubernetes/overlays/stage/` manifests similarly
- [ ] Add digest pinning step to release workflow (Makefile `release` target or CI)
- [ ] Document the process in the runbook / `docs/`
