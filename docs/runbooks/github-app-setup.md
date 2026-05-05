# GitHub App Setup Runbook

**Feature:** #001 — Private/Internal GitHub Repos  
**Audience:** Platform ops / admin  
**Updated:** 2026-05-05

---

## Overview

The Agent Knowledge Hub backend uses a GitHub App to fetch metadata for private and internal repos
(including repos in the `slaclab` GitHub Enterprise Cloud org).  Without this, submitting an
internal repo URL returns "Repo not found."

Secrets live in Vault at `secret/scs/sage/agent-knowledge-hub/app` and are injected via
`make akh-apply`.

---

## Step 1: Create the GitHub App

1. Navigate to the slaclab org app settings:
   `https://github.com/organizations/slaclab/settings/apps/new`

2. Fill in:
   - **GitHub App name:** `slac-agent-knowledge-hub` (or similar)
   - **Homepage URL:** `https://agent-knowledge-hub.slac.stanford.edu`
   - **Webhook:** uncheck **Active** — not needed

3. Under **Repository permissions**:
   - `Contents`: Read-only
   - `Metadata`: Read-only (auto-selected)

4. Under **Where can this GitHub App be installed?**: select **Only on this account**.

5. Click **Create GitHub App**.

6. Note the **App ID** shown at the top of the settings page.

7. Scroll to **Private keys** → **Generate a private key**. A `.pem` file downloads.

---

## Step 2: Install the App on the slaclab org

1. In the App settings page, click **Install App** in the left sidebar.
2. Click **Install** next to `slaclab`.
3. Select **All repositories** (or specific repos).
4. Click **Install**.

---

## Step 3: Store secrets in Vault

```bash
vault kv patch secret/scs/sage/agent-knowledge-hub/app \
  GITHUB_APP_ID=<APP_ID> \
  GITHUB_APP_PRIVATE_KEY="$(cat /path/to/downloaded.pem)"
```

The `app` secret already contains `GITHUB_TOKEN` and `INTERNAL_API_SECRET` — `patch` adds
or updates only the specified fields without touching the others.

---

## Step 4: Deploy

```bash
cd /path/to/ai-playground-deploy/kubernetes/overlays/prod2
make akh-apply
```

`akh-apply` pulls all four fields (`GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_TOKEN`,
`INTERNAL_API_SECRET`) from Vault into `agent-knowledge-hub/etc/.secrets/`, applies the
kustomization, then cleans up the local secret files.

---

## Step 5: Verify

**Check the App is visible to the backend** (no redeploy needed — just needs a request to trigger):

```bash
# Generate a JWT and look up the App
APP_ID=<APP_ID>
vault kv get --field=GITHUB_APP_PRIVATE_KEY secret/scs/sage/agent-knowledge-hub/app > /tmp/akh.pem

NOW=$(date +%s); IAT=$((NOW-60)); EXP=$((NOW+600))
b64url() { openssl base64 -e -A | tr '+/' '-_' | tr -d '='; }
HEADER=$(echo -n '{"alg":"RS256","typ":"JWT"}' | b64url)
PAYLOAD=$(echo -n "{\"iat\":${IAT},\"exp\":${EXP},\"iss\":\"${APP_ID}\"}" | b64url)
SIG=$(echo -n "${HEADER}.${PAYLOAD}" | openssl dgst -sha256 -sign /tmp/akh.pem | b64url)
JWT="${HEADER}.${PAYLOAD}.${SIG}"

# App metadata
curl -s -H "Authorization: Bearer ${JWT}" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/app | grep -E '"slug"|"html_url"'

# Installations — slaclab should appear
curl -s -H "Authorization: Bearer ${JWT}" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/app/installations | grep -E '"login"|"id"'

rm /tmp/akh.pem
```

**Check backend logs after submitting a slaclab internal URL:**

```bash
KUBECONFIG=~/.kube/config.sage kubectl -n prod logs deployment/agent-knowledge-hub-backend \
  --tail=50 | grep -i "github\|install\|token\|warn\|error"
```

Expected: a log line like:
```
GitHub App installation token refreshed (installation <id>, org=slaclab)
```

Then try submitting `https://github.com/slaclab/<some-internal-repo>` — it should scan
successfully and show the amber "This repo requires SLAC GitHub access." badge (informational
only, not a blocker).

---

## Key rotation

If the private key is compromised or expired:

1. GitHub App settings → **Private keys** → **Revoke** the old key.
2. **Generate a new private key** — download the `.pem`.
3. Update Vault: `vault kv patch secret/scs/sage/agent-knowledge-hub/app GITHUB_APP_PRIVATE_KEY="$(cat new.pem)"`
4. `make akh-apply` to redeploy.

The old key is immediately invalid after revoking — no grace period.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `"Repo not found"` on slaclab internal URL | App not installed on slaclab | Complete Step 2 |
| `has no installations` in backend logs | App created but not installed anywhere | Install App on slaclab org (Step 2) |
| `JWT error` / `401` from GitHub API | Malformed or expired PEM | Check PEM includes full `-----BEGIN/END RSA PRIVATE KEY-----` block; regenerate if needed |
| `401` after working previously | Key rotated or revoked | Generate new key, update Vault, redeploy |
| `visibility=public` on known internal repo | Old image without GHEC visibility fix | Ensure image is ≥ 0.6.0 |
| Scan returns no skills for a root-level skill repo | `discover` skipping root-level files | Ensure image is ≥ 0.6.0 (bug fixed in that release) |
