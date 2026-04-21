# GitHub App Setup Runbook

**Feature:** #001 — Private/Internal GitHub Repos  
**Audience:** Platform ops / admin  
**Updated:** 2026-04-21

---

## Overview

This runbook covers the one-time setup of the GitHub App that allows the Agent Knowledge Hub
backend to fetch metadata for private/internal repos in the `slaclab` GitHub Enterprise org.

Once set up, the backend can auto-fetch README, stars, and fork provenance for slaclab private
repos without any per-user authentication.

---

## Step 1: Create the GitHub App

1. Navigate to the slaclab GitHub Enterprise org settings:
   `https://github.com/organizations/slaclab/settings/apps`

2. Click **New GitHub App**.

3. Fill in:
   - **Name:** `Agent Knowledge Hub`
   - **Homepage URL:** your catalog URL (e.g., `https://hub.slac.stanford.edu`)
   - **Webhook:** disable (uncheck "Active")
   - **Permissions → Repository permissions:**
     - `Contents`: Read-only
     - `Metadata`: Read-only (mandatory)

4. Under **Where can this GitHub App be installed?**: select **Only on this account**.

5. Click **Create GitHub App**.

6. Note the **App ID** shown on the app settings page.

7. Scroll to **Private keys** → click **Generate a private key**. Download the `.pem` file.

---

## Step 2: Install the App on the slaclab org

1. In the App settings, click **Install App**.
2. Select **slaclab** → **All repositories** (or select specific repos).
3. Click **Install**.

---

## Step 3: Store secrets in vault

```bash
# Store App ID
vault kv put secret/agent-knowledge-hub/github-app \
  app_id="<APP_ID>" \
  private_key="$(cat /path/to/private-key.pem)"
```

---

## Step 4: Inject into Kubernetes secrets

Edit `kubernetes/overlays/dev/kustomization.yaml` (and stage/prod equivalents):

```yaml
secretGenerator:
  - name: agent-knowledge-hub-secrets
    literals:
      - MONGO_URI=...
      - GITHUB_APP_ID=<APP_ID>
      - GITHUB_APP_PRIVATE_KEY=<PEM_CONTENTS_SINGLE_LINE_OR_MULTILINE>
```

For multiline PEM in a k8s secret literal, use the `|` YAML block scalar notation or base64-encode
and use `secretGenerator.envs` instead. Alternatively, mount as a file:

```yaml
volumes:
  - name: github-app-key
    secret:
      secretName: agent-knowledge-hub-secrets
      items:
        - key: GITHUB_APP_PRIVATE_KEY
          path: github-app-private-key.pem
volumeMounts:
  - name: github-app-key
    mountPath: /run/secrets
    readOnly: true
```

Then set `GITHUB_APP_PRIVATE_KEY` to the file path: `/run/secrets/github-app-private-key.pem`
(if using file-mount mode).

---

## Step 5: Verify

Deploy and test by submitting a private slaclab repo URL. The skill should appear with
`visibility: internal` and the "SLAC Members Only" badge.

Check backend logs for JWT generation:
```
grep "github_app" backend logs
```

Expected: no errors, no PEM key in log output.

---

## Rotation

If the private key is compromised:

1. In GitHub App settings → Private keys → **Revoke** the old key.
2. **Generate a new private key**.
3. Update vault and re-deploy.
4. The old key is immediately invalid.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `visibility=public` on known private repo | App not installed | Verify App installation on slaclab org |
| JWT error in logs | Malformed PEM | Ensure no extra whitespace; key must be full RSA PEM block |
| 401 from GitHub API | Key rotated | Generate new key, update vault |
| No installations found | App installed on wrong account | Re-install on `slaclab` org |
