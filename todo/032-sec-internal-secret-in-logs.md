# 032 — Security: Internal API Secret Logged in Plaintext

**Status:** ✅ Complete
**Severity:** HIGH
**Source:** Security review 2026-06-09 (H3)

---

## Phase 1 — Problem & Goal

### What is broken today

`frontend/app/api/me/route.ts` line 15 calls:

```typescript
console.debug("[me/route] outgoing headers to backend:", JSON.stringify(outHeaders));
```

`outHeaders` is the return value of `backendHeaders(request)` from `frontend/app/api/_internal.ts`. That function (line 30–33) builds the header map:

```typescript
const headers: Record<string, string> = {
  "X-Forwarded-User": user,
  "X-Internal-Secret": INTERNAL_SECRET,  // ← plaintext value included
};
```

`JSON.stringify(outHeaders)` therefore serialises the live secret value to stdout on every single `/api/me` request. Container stdout flows to the cluster's log aggregator (`kubectl logs`, Loki, etc.).

**Secondary finding:** The same file already handles the *incoming* direction correctly — lines 9–11 redact `x-internal-secret` when logging `allHeaders`. The outgoing direction (line 15) was missed.

**No other BFF route files** (`frontend/app/api/**/*.ts`) log `outHeaders` or the return of `backendHeaders()` — the exposure is isolated to `me/route.ts` line 15 and the safe `_internal.ts` debug at lines 20–28 (which logs `INTERNAL_SECRET_set=${Boolean(INTERNAL_SECRET)}`, not the value).

### Attack path

1. Attacker gains read access to container logs (compromised Loki account, over-scoped RBAC on the namespace, exfiltrated log archive).
2. Extracts `INTERNAL_SECRET` value from log lines.
3. Forges `X-Internal-Secret: <value>` + arbitrary `X-Forwarded-User: <target>` headers directly to the backend service (reachable from inside the cluster, or via the ingress if NetworkPolicy is misconfigured).
4. Backend `auth.py` internal-secret path grants the request full authenticated access as any user, including admins.

### Success criteria after the fix

- `console.debug` on `outHeaders` in `me/route.ts` emits `[REDACTED]` for `X-Internal-Secret`, not the live value.
- No other BFF route file logs header maps that include the secret.
- CI rejects any future commit that would log the raw secret.
- Existing `/api/me` behaviour is unchanged.

### Out of scope

- Rotating the secret itself (separate operational task — do after this fix lands).
- Changes to backend `auth.py` or `config.py`.
- Changes to Kubernetes secrets or kustomize overlays.

### Constraints

- Must not break existing auth flow (Vouch path, oauth2-proxy path, CLI JWT path).
- Fix must be pure TypeScript — no infra change required.
- Deploy path: standard Next.js container rebuild + kustomize overlay promotion.

---

## Phase 1.5 — User Stories

1. As a **developer debugging auth**, I want `console.debug` to show which user was resolved and whether the secret is configured, so that I can diagnose header-chain issues without the secret value appearing in logs.
2. As a **security engineer**, I want `grep -r "X-Internal-Secret" frontend/` to find no statements that emit the raw value, so that I can verify the fix in CI.
3. As an **attacker with log access**, I want to extract the internal secret from Loki/kubectl logs, so that I can forge backend requests — after this fix, this attack yields only `[REDACTED]`.
4. As a **platform operator**, I want the fix deployed without a secret rotation, so that the emergency change window is minimised while still closing the exposure.
5. As an **admin user**, I want my session and admin privileges protected from impersonation, so that an attacker with log access cannot act as me.
6. As a **regular user**, I want my authenticated session to be unforgeable even if logs are leaked, so that my install history and ratings cannot be tampered with.
7. As a **CI maintainer**, I want a lint rule or grep check that blocks any future `console.log/debug/info` of `X-Internal-Secret` raw values, so that the pattern cannot silently reappear.
8. As a **new BFF route author**, I want `backendHeaders()` itself to return a safe-to-log representation, so that I do not need to remember to redact manually in each route.

---

## Phase 2 — Requirements

### Functional Requirements

**FR-1:** `me/route.ts` line 15 must not emit the value of `INTERNAL_SECRET` in any log statement. It must emit `[REDACTED]` or the key must be omitted from log output entirely.

**FR-2:** All other files under `frontend/app/api/` must be audited and contain no `console.*` statements that serialise the return of `backendHeaders()` (or any header map containing `X-Internal-Secret`) without redaction. (Current audit: only `me/route.ts` is affected.)

**FR-3:** A CI check (ESLint rule or `grep` step in the GitHub Actions workflow) must fail the build if any file under `frontend/` contains a pattern matching a console statement with `X-Internal-Secret` and a non-redacted value.

**FR-4:** The `backendHeaders()` function in `_internal.ts` must continue to return `X-Internal-Secret` with the live secret value in the `HeadersInit` it passes to `fetch()` — only the logging path must be changed.

### Non-Functional Requirements

**NFR-1 (Performance):** The fix must add zero measurable latency. Redacting one key from a shallow object copy is O(1) and negligible.

**NFR-2 (Compatibility):** No change to the HTTP contract between BFF and backend. The `X-Internal-Secret` header value passed to `fetch()` is untouched.

**NFR-3 (Observability):** Debug logging must remain useful — resolved user, whether the secret is set (`Boolean(INTERNAL_SECRET)`), and the forwarded-user chain should still be visible.

**NFR-4 (Forward safety):** The CI check must catch the same pattern in any new BFF route added in future, not just the current set.

### Acceptance Criteria

**AC-1:** Given the app running in any environment, when a request hits `GET /api/me`, then `kubectl logs` / Loki for the frontend pod must not contain the string value of `INTERNAL_API_SECRET` on that request's log lines.

**AC-2:** Given a developer inspecting logs after an `/api/me` call, when they search for `outgoing headers`, then they see `"X-Internal-Secret":"[REDACTED]"` (or the key is absent), not the live value.

**AC-3:** Given the CI lint/grep check is in place, when a PR adds `console.log(JSON.stringify(backendHeaders(...)))` without redaction, then the CI step fails and the PR is blocked.

**AC-4:** Given the fix is deployed, when a real authenticated user calls `/api/me`, then the response is identical to pre-fix (HTTP 200, correct user JSON body).

**AC-5:** Given `grep -rn "X-Internal-Secret" frontend/app/api/ --include="*.ts"`, the output contains no lines inside `console.*` calls that emit the raw secret (the only permitted reference in a console context is `"[REDACTED]"` or `Boolean(...)`).

---

## Phase 3 — ADRs

**ADR-032-1: Redact at log call-site vs. make `backendHeaders()` return a sanitised copy for logging**

Status: Accepted

Context: The bug is a single unredacted log line in `me/route.ts`. Two structural approaches exist: fix the call-site, or change `_internal.ts` to export a separate `safeHeadersForLog()` helper.

| Option | Pros | Cons |
|---|---|---|
| A — Fix call-site (`me/route.ts` line 15) | One-line change, minimal blast radius | Future routes could repeat the mistake |
| B — Export `safeHeadersForLog()` from `_internal.ts` | Centralises redaction, guides future authors | Adds API surface; authors must still remember to use it |
| C — Remove the outgoing headers log line entirely | Smallest possible change | Loses useful debug signal |

Decision: **Option A** (redact at call-site) for the immediate fix, plus **FR-3** (CI grep check) as the structural guard. `safeHeadersForLog()` is desirable but out of scope for this ticket.

Consequences: The call-site fix is the fastest path to closing the live exposure. The CI check ensures the pattern cannot silently reintroduce itself without an additional helper being needed.

---

**ADR-032-2: CI enforcement mechanism — ESLint rule vs. grep step**

Status: Accepted

Context: The team needs automated prevention, not just a one-time fix.

| Option | Pros | Cons |
|---|---|---|
| ESLint custom rule | Rich AST analysis, catches indirect cases | Requires writing/maintaining a plugin |
| `grep -rn` in CI step | Zero maintenance, immediate | Regex-only, can be fooled by obfuscation |

Decision: **`grep` step** added to the existing GitHub Actions frontend workflow. A literal `X-Internal-Secret` appearing in any `console.` call is the attack surface — a simple regex is sufficient and proportional.

Consequences: Not exhaustive against obfuscation, but sufficient for this threat model (accidental logging, not malicious insider). If a more sophisticated check is needed, this can be upgraded to an ESLint rule later.

---

## Phase 3.5 — Module Design

| Module/file | Change type | What changes | Testable in isolation? |
|---|---|---|---|
| `frontend/app/api/me/route.ts` | Bug fix | Line 15: replace `JSON.stringify(outHeaders)` with `JSON.stringify({ ...outHeaders, "X-Internal-Secret": "[REDACTED]" })` | Yes — Jest/Vitest unit test mocking `backendHeaders` can assert log output |
| `.github/workflows/frontend.yml` (or equivalent CI file) | Addition | Add a `grep` step that fails if `X-Internal-Secret` appears in a console statement without `[REDACTED]` | Yes — can test locally with `grep` command |

No changes to `_internal.ts`, backend files, or Kubernetes manifests.

---

## Phase 4 — System/Infrastructure Design

### Data flow — where the fix intercepts the attack

```
Browser → nginx (injects X-Auth-Request-User) → Next.js BFF → backend

[ATTACK PATH — before fix]
  me/route.ts calls backendHeaders(request)
  → outHeaders = { "X-Forwarded-User": "alice", "X-Internal-Secret": "s3cr3t!" }
  console.debug(JSON.stringify(outHeaders))
  → Loki receives: {"X-Forwarded-User":"alice","X-Internal-Secret":"s3cr3t!"}
  → Attacker reads Loki → extracts "s3cr3t!" → forges backend request as any user

[AFTER FIX]
  me/route.ts calls backendHeaders(request)
  → outHeaders = { "X-Forwarded-User": "alice", "X-Internal-Secret": "s3cr3t!" }
  console.debug(JSON.stringify({ ...outHeaders, "X-Internal-Secret": "[REDACTED]" }))
  → Loki receives: {"X-Forwarded-User":"alice","X-Internal-Secret":"[REDACTED]"}
  fetch(BACKEND/api/me, { headers: outHeaders })   ← live value still passed correctly
```

### No API contract change

The HTTP interface between BFF and backend is unchanged. Only the log emission path changes.

---

## Phase 7 — Trade-offs

| Choice | What we gain | What we give up |
|---|---|---|
| Redact at call-site, not in `backendHeaders()` | Zero risk of accidentally breaking header value passed to `fetch()` | Future authors must still be aware of the pattern (mitigated by CI check) |
| Keep `console.debug` line (redacted) rather than removing it | Retains debug utility (visible that outgoing headers were built) | Slightly more code than a simple delete |
| `grep` CI check over ESLint rule | Ships same day, zero maintenance burden | Will not catch indirect / variable-indirected logging of the secret |
| Fix without rotating the secret | Minimises change surface for emergency fix | The already-leaked secret value remains valid until rotation (rotation is a follow-up) |

---

## Phase 8 — Delivery Slices

**Slice 1 — Fix the log line (ships alone, closes the live exposure)**
- Edit `me/route.ts` line 15 to redact `X-Internal-Secret`.
- Verify `GET /api/me` still returns HTTP 200 with correct body.
- Deploy to dev, verify no secret in pod logs.

**Slice 2 — CI guard (ships alone, prevents regression)**
- Add `grep` step to frontend CI workflow.
- Step fails if pattern `console\.(log|debug|info|warn|error).*X-Internal-Secret` appears in any `frontend/app/api/**/*.ts` file without the string `[REDACTED]` on the same or adjacent line.

**Slice 3 — Secret rotation (separate ops ticket, after Slices 1–2)**
- Rotate `INTERNAL_API_SECRET` in all three overlay Secrets (dev/stage/prod).
- Coordinate frontend + backend pod restarts (zero-downtime rolling update is sufficient).
- Verify auth still works post-rotation.
- This slice is independent and can be tracked as a follow-up operations task.

---

## Phase 9 — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Redaction breaks the `fetch()` call (wrong variable passed) | Low — the fix only changes the log argument, not the `fetch()` call | HIGH — auth failure for all `/api/me` users | AC-4 smoke test before promotion; PR reviewer double-checks `outHeaders` is still passed to `fetch()` |
| Secret was already extracted from existing logs before fix | Medium — logs may already contain the value | HIGH | Rotate secret as Slice 3 immediately after Slice 1 ships |
| CI grep check produces false positives on valid `[REDACTED]` occurrences | Very low | Low — noisy CI | Regex anchored to exclude lines already containing `[REDACTED]` |
| New BFF route added post-fix that repeats the pattern before CI check lands | Low (Slice 2 ships alongside Slice 1) | HIGH | Ship both slices in the same PR |

---

## Phase 10 — Definition of Done

- [ ] `me/route.ts` line 15 logs `[REDACTED]` for `X-Internal-Secret`, confirmed by code review
- [ ] Manual smoke test: `kubectl logs -l app=frontend -n <dev-ns> | grep "outgoing headers"` shows `[REDACTED]`, not the secret value
- [ ] `GET /api/me` returns HTTP 200 with correct user JSON after the fix (no auth regression)
- [ ] Full audit of `frontend/app/api/**/*.ts` for other unredacted logging — none found (or all fixed)
- [ ] CI grep step added and passes on the fixed branch
- [ ] CI grep step fails on a synthetic test branch that re-introduces the raw log (verified locally)
- [ ] Existing frontend unit/integration tests pass (`npm test` or equivalent)
- [ ] Fix deployed to dev overlay
- [ ] Follow-up ticket opened for secret rotation (Slice 3)
- [ ] Status set to `✅ Done` in this file when all boxes checked
