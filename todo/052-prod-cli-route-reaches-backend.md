# TODO #052 — Production `/cli` Requests Reach the Backend

> **Priority:** 🟠 P1 — High
> **Status:** ✅ Complete
> **Branch:** —
> **PR:** —
> **Created:** 2026-10-15
> **Shipped:** 2026-10-16

---

## Provenance

**Raised by:** the live check for #050 on 2026-10-15, which sent a catalog request through `skill/hub-request.sh` to production and got the frontend's 404 page (#050 › Measured facts › Production `/cli` route).

---

## Problem Statement

The `/agent-knowledge-hub` client sends every catalog request to `https://agent-knowledge-hub.slac.stanford.edu/cli/api/…`, and expects the deployment to route `/cli` to the backend with the `/cli` prefix removed. In production that route is not in effect: `/cli` requests reach the frontend instead. The client on `main` has therefore not worked against production since at least 2026-10-03, and no live request has confirmed #050's route table end to end.

### What fails today

As of 2026-10-15:

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| `GET /cli/api/skills/summary` with a token the catalog accepts | HTTP 404 with the frontend's Next.js HTML page | HTTP 200 with the backend's JSON summary |
| Any `/agent-knowledge-hub` command that calls the catalog | Fails with "The catalog answered HTTP 404." or another frontend answer | Works |
| `/cli/api/marketplace.json`, which #047 plans to document | Not checked; the same route serves it | Reaches the backend |

---

## Goals

1. A request to `https://agent-knowledge-hub.slac.stanford.edu/cli/<path>` reaches the production backend as `/<path>`.
2. A check that anyone can repeat shows it, and is recorded here.

## Non-Goals

- Whether `/marketplace.json` needs a token. That is #047.
- Changes to the client or the backend. Both already expect the route.

---

## Measured facts — read 2026-10-15, read-only, re-derive before acting

| Fact | Value | How |
|---|---|---|
| Live request | With a token the catalog accepted, `sh skill/hub-request.sh GET /cli/api/skills/summary` got HTTP 404 and the frontend's Next.js page. With the same token after it expired, the same call got exit 5 and `agent-knowledge-hub: HTTP 401` | The helper, run at about 22:02 and 22:04 |
| Backend log | Since the backend pod started on 2026-10-03, its log holds `/health` probes and API requests from the frontend pod `192.168.198.98` only. No request has come through `/cli` | `kubectl logs` of the backend in vcluster `sage`, namespace `prod` |
| Public name | Resolves to `lb01-sdf-k8s01-gw` (134.79.138.59), the host cluster's gateway, which serves the vcluster's HTTPRoutes | DNS lookup |
| HTTPRoutes in the vcluster | `agent-knowledge-hub` sends `/` to `frontend:3000`. `agent-knowledge-hub-api` sends PathPrefix `/cli` to `backend:8000` with a `URLRewrite` `ReplacePrefixMatch` of `/`, and answers Exact `/marketplace.json` with a 301 `RequestRedirect`. Both carry the label `httproute.sdf.slac.stanford.edu/approved=true`. Neither has `parentRefs` or a `status`. `agent-knowledge-hub-api` is the only approved route in the vcluster with a filter | `kubectl get httproute -n prod -o yaml`, `KUBECONFIG=~/.kube/config.sage` |
| Other objects | No Gateway exists in the vcluster. nginx Ingresses for the hub also exist there | `kubectl get gateway,ingress -A` |
| Where the routes are defined | Not in this repository: the `Makefile` applies overlays from `ai-playground-deploy`, outside it | `grep -rl HTTPRoute kubernetes/` found nothing; `Makefile` lines 4 to 5 |
| Host gateway | Its configuration, and whether it takes routes with filters, was not visible from the vcluster | — |

**Hypothesis, not confirmed:** the host gateway applies the hub's plain route and not `agent-knowledge-hub-api`, because that route has filters or because of how routes without `parentRefs` are picked up.

---

## Acceptance criteria

- [x] AC-1: With a valid token, `sh skill/hub-request.sh GET /cli/api/skills/summary` exits 0 and prints JSON. On 2026-10-16 at 07:37 UTC it exited 0 with `agent-knowledge-hub: HTTP 200` and a 23,552-byte JSON list of skills.
- [x] AC-2: The backend log shows that request, from the gateway, not from the frontend pod. The backend log holds `GET /api/skills/summary HTTP/1.1" 200 OK` from `192.168.112.40`, not from the frontend pod `192.168.198.98`.

---

## Resolution

The route was fixed from `ai-playground-deploy` on 2026-10-16; the cause is not recorded in this repository. Read afterwards from vcluster `sage`, namespace `prod`, read-only:

- `agent-knowledge-hub-api` is at generation 2. It sends PathPrefix `/cli` to `agent-knowledge-hub-backend:8000` with the same `URLRewrite`, and it no longer has the Exact `/marketplace.json` `RequestRedirect` rule. A request for `/marketplace.json` now reaches the frontend, where `redirects()` in `frontend/next.config.mjs` answers it (#047).
- Both hub routes carry the annotation `auth.sdf.slac.stanford.edu/required: "true"` and the `approved` label, and still have no `parentRefs` or `status` in the vcluster.

---

## Implementation Plan

1. Confirm which route answers. `/marketplace.json` is one candidate: `agent-knowledge-hub-api` answers it with a 301, and Next.js's `redirects()` with a 308. An anonymous request got 401 on 2026-10-14 (#047), so the check may need a token, which must never go into a command's arguments.
2. Read the host gateway's handling of approved routes with the S3DF admins, or read the route definitions in `ai-playground-deploy`.
3. Fix the route in `ai-playground-deploy`, or have the admins apply it, then run AC-1 and AC-2.
4. Run #050's and #051's hand-run checks against production once AC-1 passes.

---

## Relationship to Other Tasks

- **#050 (client token helper):** its live checks need this route. The helper and its tests are done.
- **#051 (MCP servers and agents):** its install flow fetches skill details through the same route.
- **#047 (marketplace route):** plans to document `/cli/api/marketplace.json`, which this route serves.

---

## References

- `todo/050-client-token-helper.md` › Measured facts › Production `/cli` route, and › Problems & Solutions.
