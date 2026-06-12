# 036 — Security: Add Python Lockfile for Reproducible Backend Builds

**Status:** ⬜ Open
**Severity:** HIGH
**Source:** Security review 2026-06-09 (H7)

---

## Phase 1 — Problem & Goal

### What is broken today

`backend/requirements.txt` (lines 1–13) uses minimum-version constraints only:

```
fastapi>=0.111.0
httpx>=0.27.0
beanie>=1.26.0,<1.27.0
...
```

`backend/Dockerfile` line 6 runs:

```dockerfile
RUN pip install --no-cache-dir -r requirements.txt
```

This means every `docker build` invocation resolves the dependency graph from PyPI at that moment. A supply-chain attacker who publishes a malicious patch release to any of these 13 packages (typosquat, compromised maintainer account, or a silent malicious update) will be silently pulled into the next image with no diff visible in git. There is no hash verification, no upper-bound pinning for most packages, and no automated vulnerability scan in the build pipeline.

`backend/requirements-dev.txt` has the same problem for test dependencies (`pytest`, `mongomock-motor`, `respx`, etc.).

`backend/Makefile` line 17–20 builds the dev venv with `$(PIP) install -r requirements-dev.txt` — also unpinned. The `.venv` was created with `python3 -m venv` (not uv — confirmed by `backend/.venv/pyvenv.cfg`).

The project has no CI (no `.github/` directory) so there is no existing lock-check gate to rely on.

### What success looks like

- Every direct and transitive dependency is pinned to an exact version with a SHA-256 hash in a committed lockfile.
- `docker build` from a clean checkout produces an identical image on repeat runs.
- Any dependency version change is visible as a git diff in the lockfile.
- A `make lock-check` target fails the build if the lockfile is stale.
- A vulnerability scan (`pip-audit`) runs against the pinned set before each image push.

### Out of scope

- Migrating `pyproject.toml` to carry all dependencies (that is a separate refactor).
- Frontend lockfile (already handled by `package-lock.json`).
- Automated Dependabot/Renovate PR setup (desirable follow-on, not this ticket).
- Pinning the `python:3.12-slim` base image digest (separate concern).

### Constraints

- Must not break existing `make dev`, `make test`, `make docker-build` workflows.
- Must deploy via existing `make docker-push` + kustomize path (no new CI system required).
- Must use tooling available in `python:3.12-slim` or installable as a build step.
- No uv binary is currently in PATH or installed on the build host; introducing uv would require installing it in the Dockerfile and dev setup.

---

## Phase 1.5 — User Stories

1. As a **backend developer**, I want a lockfile committed to git so that I can see exactly which package versions are in production at any point in history.
2. As a **developer upgrading a dependency**, I want a `make lock` target so that I can regenerate the lockfile locally and review the diff before committing.
3. As a **developer setting up a new dev environment**, I want `make dev` to install exactly the pinned versions so that my local environment matches the Docker image.
4. As a **release engineer**, I want `docker build` to verify hashes for every installed package so that a corrupted or substituted package on PyPI is detected at build time, not at runtime.
5. As a **security engineer**, I want `pip-audit` to run against the pinned lockfile before every image push so that known CVEs in transitive deps are caught before deployment.
6. As a **project maintainer**, I want a `make lock-check` target so that CI (when added) or a pre-push hook can fail fast if someone edited `requirements.txt` without regenerating the lockfile.
7. As an **attacker who has compromised a PyPI package maintainer account**, I want to publish a malicious patch release so that it gets silently pulled into the next build — the lockfile prevents this because the build will fail on hash mismatch.
8. As an **attacker attempting a typosquat**, I want my package to resolve as a transitive dependency so that it is installed without code review — the lockfile prevents this because new transitive deps require an explicit lockfile regeneration and git diff.
9. As an **API consumer / CLI user**, I want the service to behave identically between deploys so that I can trust that a passing test suite means the deployed image is bit-for-bit the same.
10. As an **admin**, I want to know the exact provenance of every installed package so that I can respond quickly to a disclosed CVE by checking if the pinned version is affected.

---

## Phase 2 — Requirements

### Functional Requirements

**FR-1:** A lockfile (`backend/requirements.lock`) is generated from `backend/requirements.txt` using `pip-compile --generate-hashes` and committed to the repository.

**FR-2:** A corresponding `backend/requirements-dev.lock` is generated from `backend/requirements-dev.txt` (which includes `-r requirements.txt`) with hashes and committed.

**FR-3:** `backend/Dockerfile` installs from `requirements.lock` using `pip install --require-hashes -r requirements.lock`. Any hash mismatch aborts the build.

**FR-4:** `backend/Makefile` gains a `lock` target that regenerates both lockfiles, and a `lock-check` target that fails if the lockfiles are stale relative to their source `.txt` files.

**FR-5:** `backend/Makefile` `dev` target installs from `requirements-dev.lock` (with `--require-hashes`) so local dev environments are also pinned.

**FR-6:** A `make audit` target runs `pip-audit --require-hashes -r requirements.lock` against the pinned set and fails on any known CVE.

**FR-7:** The top-level `Makefile` `backend` target runs `lock-check` and `audit` before `docker-push`.

### Non-Functional Requirements

**NFR-1 (Performance):** `pip install --require-hashes` adds hash verification overhead but no network round-trips beyond normal install. The Dockerfile layer-cache means this is paid only when `requirements.lock` changes. Acceptable: <30 s additional build time.

**NFR-2 (Compatibility):** Existing callers (`make dev`, `make test`, `make run`, `make docker-build`) must continue to work without new arguments. The lockfile regeneration path (`make lock`) is additive.

**NFR-3 (Reproducibility):** Two `docker build` invocations from the same git commit must produce images with identical installed package versions and hashes, regardless of when they are run.

**NFR-4 (Auditability):** Every installed package version must be visible in git history. A `git log -- backend/requirements.lock` must show every dependency bump.

### Acceptance Criteria

**AC-1:** Given a clean checkout, when `make -C backend docker-build` is run, then `pip install` uses `--require-hashes` and aborts if any hash mismatches.

**AC-2:** Given `requirements.txt` is edited without running `make lock`, when `make -C backend lock-check` is run, then it exits non-zero.

**AC-3:** Given `requirements.lock` is committed and unchanged, when `make -C backend lock-check` is run twice in a row, then it exits 0 on both runs.

**AC-4:** Given a known-vulnerable package is pinned in `requirements.lock`, when `make -C backend audit` is run, then it exits non-zero and prints the CVE.

**AC-5:** Given the lockfile is up to date and no CVEs are present, when `make backend` is run from the repo root, then `docker-push` completes successfully.

**AC-6:** Given a developer runs `make dev` inside `backend/`, then `pip install` installs from `requirements-dev.lock` with hash verification.

---

## Phase 3 — ADRs

**ADR-036-1: pip-compile over uv lock**

Status: Accepted

Context: The task file assumed uv was in use because a `.venv` directory exists. Inspection of `backend/.venv/pyvenv.cfg` confirms the venv was created with `python3 -m venv`, not uv. uv is not in PATH on the build host or in `python:3.12-slim`.

Options considered:

| Option | Pros | Cons |
|---|---|---|
| `pip-compile --generate-hashes` (pip-tools) | Ships in PyPI, installable in any Python env, produces standard `requirements.txt`-format lockfile, `--require-hashes` is native pip | Requires adding `pip-tools` as a dev-only dep |
| `uv lock` + `uv sync --frozen` | Faster, single binary, built-in hash verification, modern standard | Binary not present on build host or in base image; requires installing uv in Dockerfile and Makefile; larger change surface |
| Manual version pinning in `requirements.txt` | No new tooling | No hash verification, still manually fragile, no automated staleness check |

Decision: Use `pip-compile --generate-hashes` from `pip-tools`. It is installable as a dev-only pip package, produces a standard pip-compatible lockfile that works with `pip install --require-hashes` (no new binary needed in the Docker image), and minimises the change surface.

Consequences: `pip-tools` becomes a build/dev dependency. The lockfile format is verbose (one package per line with multiple hashes for sdist + wheels) but human-readable and git-diffable. If the project later migrates to uv, the lockfile format would change, but the Dockerfile pattern (`--require-hashes`) remains the same.

---

**ADR-036-2: Lock check via pip-compile --dry-run, not hash comparison**

Status: Accepted

Context: A staleness check must detect when `requirements.txt` was edited but `requirements.lock` was not regenerated.

Decision: `pip-compile --dry-run --generate-hashes requirements.txt -o requirements.lock` exits non-zero if the output differs from the existing lockfile. This is the idiomatic pip-compile approach and avoids maintaining a separate hash or timestamp file.

Consequences: `pip-compile` must be available in the dev environment for the `lock-check` target to work. This is already required for `make lock`, so there is no additional dependency.

---

## Phase 3.5 — Module Design

| Module/file | Change type | What changes | Testable in isolation? |
|---|---|---|---|
| `backend/requirements.lock` | New file | Generated pinned+hashed lockfile for all runtime deps | Yes — `pip-compile --check` validates it |
| `backend/requirements-dev.lock` | New file | Generated pinned+hashed lockfile for dev+test deps | Yes — `pip-compile --check` validates it |
| `backend/Dockerfile` | Modify | Copy `requirements.lock` and use `pip install --require-hashes -r requirements.lock`; install `pip-tools` for lock-check step (optional build-time only) | Yes — `docker build` smoke test |
| `backend/Makefile` | Modify | Add `lock`, `lock-check`, `audit` targets; update `dev` target to use `requirements-dev.lock` | Yes — each target runnable in isolation |
| `backend/requirements-dev.txt` | Modify | Add `pip-tools>=7.4` and `pip-audit>=2.7` as explicit dev deps | Yes — `make dev` verifies install |
| `Makefile` (root) | Modify | Add `lock-check` and `audit` calls before `docker-push` in `backend` target | Yes — `make backend` dry-run |

---

## Phase 4 — System / Infrastructure Design

### Attack interception: before vs after

```
BEFORE (vulnerable):
  git push → make docker-push
    └─ docker build
         └─ pip install -r requirements.txt   ← resolves from PyPI at build time
              └─ ANY version PyPI returns      ← attacker-controlled if maintainer compromised

AFTER (fixed):
  developer runs: make lock  (regenerates requirements.lock with hashes)
    └─ git diff requirements.lock             ← diff visible, reviewed in PR
         └─ git push → make docker-push
              ├─ make lock-check              ← GATE: exits 1 if lock is stale
              ├─ make audit                   ← GATE: exits 1 if CVE in pinned set
              └─ docker build
                   └─ pip install --require-hashes -r requirements.lock
                        └─ ONLY pinned versions with matching SHA-256  ← hash mismatch = build abort
```

### Dockerfile before/after

```dockerfile
# BEFORE
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# AFTER
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
```

### Makefile new targets

```makefile
lock:                          ## regenerate both lockfiles
    $(PIP) install pip-tools pip-audit
    pip-compile --generate-hashes requirements.txt -o requirements.lock
    pip-compile --generate-hashes requirements-dev.txt -o requirements-dev.lock

lock-check:                    ## fail if lockfiles are stale
    pip-compile --dry-run --generate-hashes requirements.txt -o requirements.lock
    pip-compile --dry-run --generate-hashes requirements-dev.txt -o requirements-dev.lock

audit:                         ## scan pinned deps for CVEs
    pip-audit --require-hashes -r requirements.lock
```

---

## Phase 7 — Trade-offs

| Choice | What we gain | What we give up |
|---|---|---|
| pip-compile + pip --require-hashes | Hash verification in standard pip; no new binary in Docker image | Lockfile is verbose (~10 lines per package including multiple wheel hashes); requires `pip-tools` in dev env |
| Lock both runtime and dev deps | Dev environment is also reproducible; test results are trustworthy | Developers must run `make lock` when adding test-only deps, not just editing `requirements.txt` |
| Run `lock-check` + `audit` before docker-push (Makefile gate) | Enforces policy without CI | Can be bypassed by running `make docker-build` directly; not enforced by the git server |
| pip-audit for CVE scanning | Catches known CVEs in pinned deps at build time | pip-audit queries OSV/PyPI Safety DB which may have lag on very new CVEs |

---

## Phase 8 — Delivery Slices

**Slice 1 — Lockfile generation and Docker build update (ship independently)**

Generate `requirements.lock` and `requirements-dev.lock`, update `backend/Dockerfile` to use `--require-hashes`, update `backend/requirements-dev.txt` to add `pip-tools` and `pip-audit`. Verify `make docker-build` succeeds. This is the core security fix — all other slices are enforcement tooling.

Safe to ship alone: yes. The image produced is functionally identical; the only change is that `pip install` now verifies hashes.

**Slice 2 — Makefile `lock`, `lock-check`, `audit` targets**

Add the three new Makefile targets. Update `make dev` to install from `requirements-dev.lock`. Developers can now run `make lock` to regenerate and `make audit` to scan.

Safe to ship alone: yes. Additive changes; existing targets are not modified.

**Slice 3 — Root Makefile gate**

Update the root `Makefile` `backend` target to run `make -C backend lock-check` and `make -C backend audit` before `docker-push`. This gates every image push on a passing lock-check and clean vulnerability scan.

Safe to ship alone: yes (depends on Slice 1 and 2 being present for the gates to pass).

---

## Phase 9 — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `pip-compile` generates different lockfile on different platforms (e.g., Linux vs macOS wheel hashes differ) | Medium | Lockfile drift, `lock-check` false positives | Always regenerate lockfile on Linux (or in Docker); document this in `make lock` help text |
| A developer edits `requirements.txt`, skips `make lock`, and the gate is bypassed by running `make docker-build` directly | Medium | Unlocked build proceeds | Add `lock-check` as a dependency of `docker-build` target in `backend/Makefile` |
| `pip-audit` reports a CVE in a transitive dep with no available fix | Low–Medium | Build blocked; no ability to ship | Add `--ignore-vuln VULN-ID` escape hatch with a mandatory comment explaining why; track in risk register |
| Lockfile regeneration pulls in an unexpected transitive dep upgrade | Low | Silent behaviour change | The full `git diff requirements.lock` review in PR catches this |
| `python:3.12-slim` base image itself has vulnerabilities | Medium | Not addressed by this ticket | Follow-on: pin base image digest in Dockerfile |

---

## Phase 10 — Definition of Done

- [ ] `backend/requirements.lock` committed with hashes for all runtime transitive deps
- [ ] `backend/requirements-dev.lock` committed with hashes for all dev/test transitive deps
- [ ] `backend/Dockerfile` updated to use `pip install --require-hashes -r requirements.lock`
- [ ] `backend/requirements-dev.txt` adds `pip-tools>=7.4` and `pip-audit>=2.7`
- [ ] `backend/Makefile` has `lock`, `lock-check`, and `audit` targets; `dev` target installs from `requirements-dev.lock`
- [ ] Root `Makefile` `backend` target runs `lock-check` and `audit` before `docker-push`
- [ ] `make -C backend docker-build` succeeds from a clean checkout
- [ ] `make -C backend lock-check` exits 0 on unmodified repo
- [ ] `make -C backend lock-check` exits non-zero after manually editing `requirements.txt` without regenerating
- [ ] `make -C backend audit` exits 0 (no CVEs in pinned set, or all findings acknowledged)
- [ ] `make docker-build` from `backend/` verified with `podman run` smoke test (app starts, `/health` returns 200)
- [ ] Deployed to dev overlay; no regressions in `make test`
- [ ] PR diff shows lockfile added; reviewer has confirmed no unexpected package version changes

---

## Original Implementation Plan (preserved)

- [ ] Decide on tooling: `pip-compile` (chosen; see ADR-036-1) or `uv lock`
- [ ] Generate the lockfile from `backend/`
- [ ] Commit `requirements.lock` and `requirements-dev.lock` to the repository
- [ ] Update `backend/Dockerfile` to install from lockfile with `--require-hashes`
- [ ] Add `make lock-check` and `make audit` targets
- [ ] Verify Docker build produces a working image after the change
