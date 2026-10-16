# Runbook: Rotating `INTERNAL_API_SECRET`

`INTERNAL_API_SECRET` is the shared secret the Next.js frontend sends to the backend in `X-Internal-Secret`, so that the backend accepts the `X-Forwarded-User` header it sends alongside. Anyone who holds it can act as any user, admins included, on a request that reaches the backend. It lives in Vault and never in git.

Last rotated 2026-10-16, in dev (Vault version 2) and prod (version 3), after the backend was found logging it (fixed in 0.20.2). Before that date dev and prod held the same value; each now has its own.

## How the secret reaches the pods

| Environment | Vault key (KV v2 mount `secret`) | Property |
|---|---|---|
| prod | `scs/sage/agent-knowledge-hub/app` | `INTERNAL_API_SECRET` |
| dev | `scs/sage-dev/agent-knowledge-hub/app` | `INTERNAL_API_SECRET` |

The `agent-knowledge-hub-secrets` ExternalSecret in `ai-playground-deploy/kubernetes/overlays/<env>/agent-knowledge-hub/` copies it into the Secret of the same name, refreshing hourly. The backend reads that Secret through `envFrom` and the frontend through `secretKeyRef`. Both deployments carry `reloader.stakater.com/auto: "true"`, so Reloader restarts them when the Secret changes. Nothing else reads the secret.

The same Vault key holds `Client_ID`, `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY` and `GITHUB_TOKEN`. **Never use `vault kv put` on it**: `put` replaces every field, and the GitHub App credentials would be lost. Use `vault kv patch`.

## Rotate

Run from a shell that is signed in to Vault (`vault login` writes `~/.vault-token`) and to the sage cluster. In a Cogito session, `$HOME` is a per-host directory without the token, so prefix each `vault` command with `HOME=<your real home>`.

1. Write a new value straight from the generator into Vault. It goes through stdin, so it never appears in a command line or in the terminal. `-method=rw` reads and rewrites the key, keeping the other fields; it needs only the `read` and `update` capabilities, where the default method also needs `patch`.

   ```bash
   export VAULT_ADDR=https://vault.slac.stanford.edu
   python3 -c 'import secrets, sys; sys.stdout.write(secrets.token_hex(32))' \
     | vault kv patch -method=rw -mount=secret scs/sage/agent-knowledge-hub/app INTERNAL_API_SECRET=-
   ```

   Generate a separate value for each environment.

2. Have ESO copy it now instead of within the hour:

   ```bash
   KUBECONFIG=~/.kube/config.sage kubectl -n prod annotate externalsecret agent-knowledge-hub-secrets \
     force-sync="$(date +%s)" --overwrite
   ```

   On 2026-10-16 the Secret changed about 5 seconds later in both environments.

3. Reloader restarts both deployments. Wait for them:

   ```bash
   KUBECONFIG=~/.kube/config.sage kubectl -n prod rollout status deployment/agent-knowledge-hub-backend
   KUBECONFIG=~/.kube/config.sage kubectl -n prod rollout status deployment/agent-knowledge-hub-frontend
   ```

   Each deployment runs one pod, and they restart independently, so for up to a minute one pod can hold the old value and signed-in requests can fail with 401.

## Verify

Compare fingerprints, never values. Each command below prints the first 12 characters of the SHA-256 of the secret, and all four must match:

```bash
fp() { python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest()[:12])'; }
vault kv get -mount=secret -field=INTERNAL_API_SECRET scs/sage/agent-knowledge-hub/app | fp
kubectl -n prod get secret agent-knowledge-hub-secrets -o jsonpath='{.data.INTERNAL_API_SECRET}' | base64 -d | fp
kubectl -n prod exec deploy/agent-knowledge-hub-backend -- sh -c 'printf %s "$INTERNAL_API_SECRET"' | fp
kubectl -n prod exec deploy/agent-knowledge-hub-frontend -- sh -c 'printf %s "$INTERNAL_API_SECRET"' | fp
```

Then check that the frontend's secret is accepted, from inside the frontend pod; this prints `200`:

```bash
kubectl -n prod exec deploy/agent-knowledge-hub-frontend -- node -e '
fetch(process.env.BACKEND_URL + "/api/me", {headers: {"X-Internal-Secret": process.env.INTERNAL_API_SECRET, "X-Forwarded-User": "smoke"}})
  .then(r => console.log(r.status))'
```

The retired value, read from the previous Vault version and passed on stdin, must get `401`:

```bash
vault kv get -mount=secret -version=<previous> -field=INTERNAL_API_SECRET scs/sage/agent-knowledge-hub/app \
  | kubectl -n prod exec -i deploy/agent-knowledge-hub-backend -- python -c '
import sys, urllib.request, urllib.error
req = urllib.request.Request("http://127.0.0.1:8000/api/me", headers={"X-Internal-Secret": sys.stdin.read().strip(), "X-Forwarded-User": "smoke"})
try: print(urllib.request.urlopen(req, timeout=10).status)
except urllib.error.HTTPError as e: print(e.code)'
```

Finally load a signed-in page in a browser.

## Roll back

`vault kv rollback -mount=secret -version=<previous> scs/sage/agent-knowledge-hub/app` restores the previous value as a new version. Then repeat steps 2 and 3. Rolling back a leaked value defeats the rotation, so do it only to recover from a broken rotation, and rotate again afterwards.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `permission denied` from `vault` in a Cogito session | `$HOME` points at the per-host directory, which has no `.vault-token` | Prefix the command with `HOME=<your real home>`; re-run `vault login` only if `vault token lookup` then says the token expired |
| The Secret keeps the old fingerprint | ESO has not synced | `kubectl describe externalsecret agent-knowledge-hub-secrets` and read its events and `status.conditions` |
| The pods keep the old fingerprint after the Secret changed | Reloader did not restart them | `kubectl rollout restart deployment agent-knowledge-hub-backend agent-knowledge-hub-frontend` |
| Every signed-in request returns 401 | The two pods hold different values | Compare the pod fingerprints; restart the pod that holds the old one |
| The backend refuses to start: `INTERNAL_API_SECRET must be at least 32 characters` | A short value was written | Rotate again with the generator above, which writes 64 hex characters |
