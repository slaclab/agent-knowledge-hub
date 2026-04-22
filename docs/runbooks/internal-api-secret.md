# Runbook: Rotating `INTERNAL_API_SECRET`

The `INTERNAL_API_SECRET` is a shared secret that lets the backend verify requests came from the
Next.js proxy rather than a spoofed source. It must be stored in Vault and never committed to git.

---

## 1. Generate a new secret

```bash
openssl rand -hex 32
# Example output: a3f8b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1
```

---

## 2. Store in Vault

Replace `<env>` with `dev`, `stage`, or `prod`:

```bash
vault kv put secret/tid/agent-knowledge-hub-<env>/app INTERNAL_API_SECRET=<new-value>
```

For the dev overlay, the Vault path is `secret/tid/agent-knowledge-hub-dev/app`.
For stage and prod, the Vault path is `secret/tid/agent-knowledge-hub-stage` /
`secret/tid/agent-knowledge-hub-prod` (see `SECRET_PATH` in each overlay's `Makefile`).

---

## 3. Deploy backend first

Pull the new secret from Vault and deploy the backend. The backend's `@field_validator`
strips trailing whitespace (including newlines from Vault file injection) automatically.

```bash
# From the overlay directory (e.g. kubernetes/overlays/dev/)
make secrets
kubectl apply -k .
kubectl rollout status deployment/agent-knowledge-hub-backend -n <namespace>
```

Deploy backend first so the new secret is active before the frontend starts sending it.
Old frontend pods send the old secret; the backend still rejects them on the Next.js proxy path —
auth falls back to the expand-phase `X-Forwarded-User` fallback during the window.

---

## 4. Deploy frontend

After backend rollout is complete:

```bash
kubectl rollout status deployment/agent-knowledge-hub-backend -n <namespace>
# Once Ready, deploy frontend:
kubectl apply -k .
kubectl rollout status deployment/agent-knowledge-hub-frontend -n <namespace>
```

---

## 5. Verify all 7 auth routes

After both rollouts complete, verify the authenticated flow works end-to-end:

| Route | Method | Expected |
|-------|--------|----------|
| `/api/me` | GET | 200 with user info |
| `/api/skills` | GET | 200 with skill list |
| `/api/skills` | POST | 200/201 (as authenticated user) |
| `/api/skills/[slug]` | GET | 200 |
| `/api/skills/[slug]` | PATCH/DELETE | 200/204 |
| `/api/skills/[slug]/refetch` | POST | 200 |
| `/api/skills/[slug]/revisions` | GET | 200 |
| `/api/skills/[slug]/revisions/[n]` | GET | 200 |
| `/api/github-scan` | GET | 200/4xx (auth works, response depends on URL) |

---

## 6. Rollback if frontend fails mid-rotation

If the frontend deployment fails after the backend has already started using the new secret:

```bash
# Rollback frontend to previous revision
kubectl rollout undo deployment/agent-knowledge-hub-frontend -n <namespace>
kubectl rollout status deployment/agent-knowledge-hub-frontend -n <namespace>
```

Auth continues to function via the `X-Forwarded-User` fallback (expand phase) while the
old frontend is running. The new secret in Vault is still valid — retry the frontend deploy
once the underlying issue is resolved.

If both backend and frontend need to be rolled back:

```bash
kubectl rollout undo deployment/agent-knowledge-hub-backend -n <namespace>
kubectl rollout undo deployment/agent-knowledge-hub-frontend -n <namespace>
# Then restore the old secret in Vault
vault kv put secret/tid/agent-knowledge-hub-<env>/app INTERNAL_API_SECRET=<old-value>
```

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| All API routes return 401 after deploy | Backend loaded new secret, frontend still sending old one | Check frontend rollout is complete; rollback frontend if stuck |
| Silent 401s on one pod, not others | Trailing newline in Vault-injected secret on one replica | `@field_validator` should strip it; check `kubectl logs` for `INTERNAL_API_SECRET` length warnings |
| `kubectl rollout status` hangs | Readiness probe failing due to 401 on health endpoint | Health endpoint (`/health`) is exempt from auth — check if NetworkPolicy is blocking probe traffic |
| Auth works via browser but not via direct `/api/` path | Fix 1 (ingress header stripping) is deferred — this is expected | See ADR-P05 for accepted residual risk |
| `INTERNAL_API_SECRET` not found in Vault | Wrong path or missing `put` step | Re-run step 2; verify with `vault kv get secret/tid/agent-knowledge-hub-<env>/app` |
