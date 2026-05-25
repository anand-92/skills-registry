# Skills Registry — Remote MCP Handoff

> **Audience:** the next engineer taking this branch (`feat/remote-mcp-server`)
> all the way to production at `https://mcp.skills-registry.dev`.
>
> **You inherit:** a fully tested code change, a partially provisioned Railway
> project, a purchased domain, and two registered GitHub apps. You need to
> finish the deploy, point DNS, and validate end‑to‑end.

---

## 1. TL;DR — what's done, what's left

**Done**
- New remote MCP server (FastMCP Streamable HTTP + GitHub OAuth Proxy + GitHub App).
- Local stdio MCP path **deleted** (the project hadn't launched, so we
  rebuilt rather than maintained two paths).
- 81 pytest tests passing, ruff clean.
- `Dockerfile`, `railway.json`, `.dockerignore` in place.
- Branch `feat/remote-mcp-server` pushed to `origin`.
- GitHub OAuth App + GitHub App **created** and credentials in Railway shared vars.
- Domain `skills-registry.dev` **purchased** on Porkbun.
- Railway project + Postgres pod **provisioned**; 12 shared env vars already set.

**Left for you (in order)**
1. Generate `STORAGE_ENCRYPTION_KEY` (Fernet) and add to Railway.
2. Add three more env vars to Railway (`FASTMCP_STORAGE_DIR`, `GITHUB_APP_SLUG`,
   and the encryption key from #1).
3. Verify naming on the existing 12 Railway vars matches what the code
   expects (table in §4 below).
4. Create the web service on Railway pointing at the `feat/remote-mcp-server`
   branch + attach a 1 GB persistent volume at `/data`.
5. Trigger the first deploy and tail logs until `/healthz` is green inside
   the container.
6. Configure custom domain `mcp.skills-registry.dev` in Railway → capture
   Railway's CNAME target.
7. Write the CNAME to Porkbun via API (or dashboard).
8. Wait for TLS provisioning, hit `/healthz` over HTTPS.
9. Confirm the GitHub OAuth App callback and GitHub App webhook URLs both
   point at the production host (not localhost / placeholder).
10. End‑to‑end smoke test from a real MCP client (Claude Desktop, Cursor).
11. Open the PR (`feat/remote-mcp-server` → `main`), get a review, merge.
12. Decide what to do with the idle Postgres pod (see §8).
13. Follow up: update README, `docs/registry.md`, and the Go CLI's MCP install
    instructions to point at the hosted URL instead of `uv tool install`.

---

## 2. Architecture at a glance

```
┌──────────────┐   OAuth (browser)   ┌──────────────────────────────┐
│ MCP client   │ ──────────────────► │ GitHubProvider               │
│ (Claude /    │ ◄────────────────── │  └─ OAuth Proxy + FastMCP JWT │
│  Cursor /…)  │      Streamable HTTP│                              │
└──────────────┘  /mcp               │  Tools: list_skills, get_skill│
                                     │                              │
                                     │  Storage:  FileTreeStore     │
                                     │            on /data (volume) │
                                     │            wrapped in Fernet │
                                     └───────────┬──────────────────┘
                                                 │ installation token
                                                 ▼
                                          GitHub REST API
                                          (Contents API only, v1)
                                                 ▲
                                                 │
        GitHub  ─ webhook ─►  /github/webhook ───┘
        (install/uninstall events auto‑link the user's repo)
```

**Two auth surfaces, deliberately separate:**
- **GitHub OAuth App** — identifies the MCP *user*. Gives us the `sub` claim
  (a numeric GitHub user ID) and nothing else. We never use the user's OAuth
  token to call GitHub.
- **GitHub App** — accesses *repos*. The user installs it on their registry
  repo. We mint short‑lived installation tokens (~1 h) via App JWTs to call
  the GitHub Contents API. The user's OAuth identity is the lookup key into
  our per‑user link state.

**Storage decision:** `FileTreeStore` on a Railway volume, wrapped in
`FernetEncryptionWrapper`. Chosen over Redis because (a) we're single‑instance
≤1k users and (b) the FastMCP docs explicitly recommend File for this shape.
Postgres is *not* used — it was provisioned earlier in the session under a
different plan; see §8.

---

## 3. Source map

```text
src/skills_mcp/
  remote_server.py     # FastMCP app assembly, env-var validation, tool registration
  github_app.py        # App JWT minter + installation-token exchange
  github_api.py        # Read-only REST wrapper (list_skill_folders, get_skill_md)
  linking.py           # Per-user KV state: user_id → {installation_id, repo, branch}
  webhooks.py          # /github/webhook handler (signature verify + auto-link)
  setup_routes.py      # /, /healthz, /github/app/callback (unauthenticated)
  frontmatter.py       # Shared SKILL.md frontmatter parser (kept from old stack)

tests/                 # 81 tests, pytest-asyncio in auto mode
Dockerfile             # python:3.12-slim multi-stage, runs as non-root `app` user
railway.json           # Healthcheck = /healthz, DOCKERFILE builder
.dockerignore          # Excludes cli/, website/, docs/, tests/ from build context
```

**Tools exposed (read-only v1):**
- `list_skills` → markdown table of every skill in the linked repo.
- `get_skill(slug)` → verbatim `SKILL.md` content (no supporting files yet).

Per the original plan: `publish_skill` is intentionally not in v1.

---

## 4. Required env vars (full list)

The Railway service needs **all** of these set before it'll boot. The 12 vars
from the earlier provisioning step *should* cover most — verify the names.
The code's `load_settings()` (`src/skills_mcp/remote_server.py`) is the
authoritative list; it fails fast with a clear error per missing var.

| Var | Value source | Notes |
|---|---|---|
| `FASTMCP_SERVER_AUTH_GITHUB_BASE_URL` | `https://mcp.skills-registry.dev` | Public URL — drives OAuth redirect URIs |
| `FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID` | `Ov23liS1hkOMtFsSHFq8` | OAuth App (per session summary) |
| `FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET` | OAuth App secret | Already in Railway shared vars |
| `GITHUB_APP_ID` | `3846201` | Numeric GitHub App ID |
| `GITHUB_APP_PRIVATE_KEY` | Multi‑line RSA PEM | Already in Railway via CodeMirror injection |
| `GITHUB_APP_WEBHOOK_SECRET` | HMAC secret | Set in Railway during App creation |
| `GITHUB_APP_SLUG` | **TBD — verify** (likely `skills-registry-mcp`) | Used to construct `https://github.com/apps/<slug>/installations/new` |
| `JWT_SIGNING_KEY` | 88‑char urlsafe random | Already in Railway |
| `FASTMCP_STORAGE_DIR` | `/data/oauth` | **You need to add this** — must match the volume mount path |
| `STORAGE_ENCRYPTION_KEY` | Fernet key | **You need to generate + add** |
| `HOST` | `0.0.0.0` | Dockerfile default; Railway will likely override |
| `PORT` | Railway injects automatically | Dockerfile defaults to 8000 |

**Generate the new secrets locally:**

```bash
# STORAGE_ENCRYPTION_KEY — 44-char urlsafe-base64 Fernet key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The `JWT_SIGNING_KEY` is already set per the session summary; only regenerate
if you have a reason to rotate it (all in-flight FastMCP JWTs would invalidate).

---

## 5. Provisioned infrastructure (don't recreate)

### Porkbun

- **Domain:** `skills-registry.dev` (registered for $10.81, renews $12.87/yr).
- **DNS:** still on Porkbun nameservers. You'll add **one CNAME record**
  here: `mcp` → `<railway-target>`. The Railway dashboard will show you the
  exact target after you add the custom domain. (Often something like
  `xyzabc.up.railway.app` or a Railway-managed CNAME.)
- **API:** Porkbun gives you an API key + secret on the account settings
  page. They have a simple JSON API:
  https://porkbun.com/api/json/v3/documentation . The relevant endpoint is
  `POST /dns/create/{domain}` with `{"type":"CNAME","name":"mcp","content":"<target>","ttl":"600"}`.

### Railway

- **Project name:** `skills-registry-mcp`
- **Project ID:** `fff5f331-b635-4a25-b42e-267eab4f5a3f`
- **Plan:** Hobby
- **Services so far:** Postgres only (idle — see §8)
- **Volume:** **not yet created**. When you add the web service, create a
  1 GB volume and mount it at `/data` (the `Dockerfile` defaults
  `FASTMCP_STORAGE_DIR=/data/oauth` so this Just Works if you mount there).
- **Shared variables:** 12 already set (per session summary). The biggest
  one is `GITHUB_APP_PRIVATE_KEY` (multi-line PEM, injected via CodeMirror's
  `execCommand` — don't try to retype it).

### GitHub apps

- **OAuth App** ("Skills Registry"):
  - Client ID: `Ov23liS1hkOMtFsSHFq8`
  - Callback URL (during creation): `https://mcp.skills-registry.dev/auth/callback` — **verify this still matches before going live.**
- **GitHub App** ("Skills Registry MCP"):
  - App ID: `3846201`
  - Client ID: `Iv23liKPKypuQdJBJveT`
  - Permissions: `Contents: Read-only`, `Metadata: Read-only`
  - Webhook events: `installation`, `installation_repositories`
  - Setup URL: should be `https://mcp.skills-registry.dev/github/app/callback`
  - Webhook URL: should be `https://mcp.skills-registry.dev/github/webhook`
  - Private key: downloaded to `~/Downloads/skills-registry-mcp.2026-05-24.private-key.pem` on the dev machine **and** copied into Railway as `GITHUB_APP_PRIVATE_KEY`.

**Confirm the OAuth callback + App setup/webhook URLs before flipping DNS.**
If they were set to localhost or a placeholder during creation, edit them
in the GitHub UI (`Settings → Developer settings → OAuth Apps` /
`GitHub Apps`).

---

## 6. Step-by-step: from here to production

### Step A — finish env-var wiring (~5 min)

```bash
# 1. Generate the encryption key
KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
echo "STORAGE_ENCRYPTION_KEY=$KEY"
```

In Railway → `skills-registry-mcp` project → **Variables** tab, add:
- `STORAGE_ENCRYPTION_KEY=<paste>`
- `FASTMCP_STORAGE_DIR=/data/oauth`
- `GITHUB_APP_SLUG=skills-registry-mcp` *(or whatever the actual slug is in your GitHub App URL — check `https://github.com/apps/<slug>`)*

Cross-check the 12 existing vars against the table in §4. Most likely fine,
but the `_CLIENT_ID` / `_CLIENT_SECRET` / `_BASE_URL` names matter — the
code uses the `FASTMCP_SERVER_AUTH_GITHUB_*` convention.

### Step B — create the web service (~10 min)

1. In the Railway project, click **+ New → GitHub Repo**.
2. Pick `anand-92/skills-registry` and the branch `feat/remote-mcp-server`.
3. Railway should detect `Dockerfile` automatically (verified by `railway.json`).
4. Once the service is created, go to **Settings → Volumes**, attach a **1 GB**
   volume with mount path `/data`.
5. Trigger a deploy. The first build takes ~3–5 min (cryptography wheel).

### Step C — verify the boot (~5 min)

Tail logs in Railway. You're looking for:
```
INFO skills_mcp.remote_server: ...
Uvicorn running on http://0.0.0.0:8000
```

If you see `Missing required env var: ...`, that's `load_settings()`
telling you which var is still missing. Add it; the service auto-restarts.

The `/healthz` endpoint should respond `{"status":"ok"}` once the container
is up. Railway's healthcheck is configured to hit it (see `railway.json`).

### Step D — add the custom domain (~5 min + propagation time)

1. In Railway → service → **Settings → Networking → Custom Domain** → add
   `mcp.skills-registry.dev`.
2. Railway shows you the CNAME target (something like
   `<random>.up.railway.app`). **Copy it exactly.**
3. Add the CNAME on Porkbun (API or dashboard). Example via API:

```bash
curl -X POST https://porkbun.com/api/json/v3/dns/create/skills-registry.dev \
  -H "Content-Type: application/json" \
  -d '{
    "apikey": "<your porkbun key>",
    "secretapikey": "<your porkbun secret>",
    "name": "mcp",
    "type": "CNAME",
    "content": "<railway-target>",
    "ttl": "600"
  }'
```

4. Wait 1–5 minutes for propagation + TLS provisioning. Watch the Railway
   domain panel — it'll go from `pending` to `active` once TLS is live.

### Step E — verify production (~5 min)

```bash
# Healthz
curl -i https://mcp.skills-registry.dev/healthz
# → 200 {"status":"ok"}

# OAuth discovery (proves GitHubProvider mounted)
curl -i https://mcp.skills-registry.dev/.well-known/oauth-authorization-server
# → 200 application/json with authorization_endpoint, token_endpoint, …

# Landing page
curl -i https://mcp.skills-registry.dev/
# → 200 text/html with install link
```

### Step F — end‑to‑end smoke test (~10 min)

1. In a real MCP client (Claude Desktop is easiest), add a remote MCP server
   with URL `https://mcp.skills-registry.dev/mcp` and auth type `oauth`.
2. Trigger a tool call. The client should pop a browser tab → GitHub OAuth.
3. Authorize. Client should auto-connect and show `list_skills` / `get_skill`
   in its tool list.
4. Call `list_skills` — expect the "no repo linked" setup message with the
   install URL.
5. Click the install URL, install the App on your registry repo.
6. Wait a few seconds (webhook lands), call `list_skills` again — expect the
   markdown table.
7. Call `get_skill(slug="<any slug from the table>")` — expect raw SKILL.md.

### Step G — open the PR

```bash
gh pr create \
  --base main \
  --head feat/remote-mcp-server \
  --title "feat: remote FastMCP server with GitHub OAuth + GitHub App auth" \
  --body-file <(echo "See HANDOFF.md for the full migration story. tl;dr: replaces the local stdio MCP with a hosted Streamable HTTP server, deployed at https://mcp.skills-registry.dev.")
```

The Python CI job should pass (lint + 81 tests, all green locally). The Go
job will also pass — we didn't touch `cli/`.

---

## 7. Verification checklist

Use this when you think you're done:

- [ ] `STORAGE_ENCRYPTION_KEY`, `FASTMCP_STORAGE_DIR`, `GITHUB_APP_SLUG` set in Railway
- [ ] Web service deployed from `feat/remote-mcp-server`
- [ ] 1 GB volume attached at `/data`
- [ ] Service logs show `Uvicorn running` and no missing-env-var errors
- [ ] Railway healthcheck green (auto, but verify in the Deployments tab)
- [ ] Custom domain `mcp.skills-registry.dev` active in Railway (TLS provisioned)
- [ ] Porkbun CNAME `mcp → <railway target>` in place
- [ ] `curl https://mcp.skills-registry.dev/healthz` returns 200
- [ ] `curl https://mcp.skills-registry.dev/.well-known/oauth-authorization-server` returns JSON
- [ ] GitHub OAuth App callback URL = `https://mcp.skills-registry.dev/auth/callback`
- [ ] GitHub App setup URL = `https://mcp.skills-registry.dev/github/app/callback`
- [ ] GitHub App webhook URL = `https://mcp.skills-registry.dev/github/webhook`
- [ ] MCP client (Claude / Cursor) can connect via OAuth
- [ ] `list_skills` returns the setup-needed message when no link exists
- [ ] After installing the App, `list_skills` returns a markdown table within ~5 s
- [ ] `get_skill(slug)` returns the file content for a known slug
- [ ] Webhook delivery in GitHub App settings shows 200 responses (no signature failures)
- [ ] PR opened and reviewed
- [ ] Decision on Postgres pod (delete or keep — see §8)

---

## 8. Decisions made (read this before second‑guessing)

### File storage instead of Redis or Postgres

`py-key-value-aio` has no Postgres backend. The choices for persistence are
Redis, DynamoDB, MongoDB, or `FileTreeStore`. The FastMCP docs explicitly
mark `FileTreeStore` as "✅ Recommended" for single-server deployments with
persistence — which is exactly our shape (≤1k users, one Railway service).
Adding Redis would be ~$5/mo of waste + lifecycle complexity for no benefit
at this scale.

### GitHub App + OAuth App (two surfaces, not one)

We could have just used the user's OAuth token to call GitHub. We don't,
because (a) OAuth tokens leak the user's full account scope, (b) installation
tokens auto‑expire so we don't need revocation logic, and (c) the original
`REMOTE_MCP_PLAN.md` explicitly chose this shape.

### Postgres pod is idle

The Postgres pod was provisioned during an earlier iteration of the plan
that called for Postgres-backed state. After we pivoted to FileTreeStore,
the pod has no consumer. **You should decide**:
- **Delete it** if you don't have near-term use for it (~$5/mo saved).
- **Keep it** if you want to add per-user audit logs, multi-region replication
  state, or any structured query workload later.

The current code base has zero Postgres references; deleting is safe.

### No `update` / `publish` tools yet

Per the plan, v1 is read-only. Adding write paths requires:
- Bumping the GitHub App's `Contents` permission from `Read-only` to `Read & write`
  (which forces every user to reinstall the App — friction).
- A token-exchange story for "user X is requesting an installation write on
  installation Y" (the current installation token is App‑scoped, not
  user‑scoped).

Don't bolt these on without thinking through the access model.

### Single-instance only

`FileTreeStore` on a local volume = no horizontal scaling. If you need to
scale out, swap to Redis (the wrapper code in `build_storage()` is the only
place that changes). Don't run two Railway replicas pointing at one volume.

---

## 9. Known risks / gaps

- **Webhook race.** When a user installs the App, the OAuth callback returns
  immediately but the `installation.created` webhook may take a few seconds.
  If the user calls `list_skills` in that window, they get the "install the
  App" message. Not a bug — the message tells them to wait a few seconds and
  retry. Worth mentioning in user docs.
- **Auto-repo selection.** If a user installs the App on multiple repos, we
  pick the first one named `*skills*` and fall back to the first repo with
  any `SKILL.md` files. No user-facing override. If this trips real users,
  add a `select_repo(repo)` tool (small change in `remote_server.py`).
- **No observability beyond stderr.** No structured logging, no metrics, no
  tracing. Railway's log search will be your only debug tool until you add
  something proper.
- **`pip install uv` in the Dockerfile is unpinned.** Reproducibility risk if
  uv ships a breaking change. Pin to a specific version when you have time.
- **No rate limiting beyond what httpx + GitHub already enforce.** A
  misbehaving client could spam `list_skills` and burn through the
  installation token's API budget (5000 req/hr). Mitigation: add a simple
  in-memory rate limiter or a CloudFlare in front of Railway.
- **The Go CLI bootstrap (`cli/internal/bootstrap/mcp_install.go`) still
  installs the old PyPI package.** Once this is live, update the Go CLI's
  wizard step 7 to write a hosted-URL MCP config snippet instead of running
  `uv tool install`. Out of scope for this PR — file as a follow-up issue.

---

## 10. Rollback plan

If the deploy explodes after merge to `main`:

1. **Don't** revert the merge commit immediately — the Go CLI hasn't been
   updated to point at the new endpoint yet, so reverting only takes Python
   back to a broken state (the stdio modules are gone).
2. **Do** roll back at the Railway layer: redeploy the previous good build
   from the **Deployments** tab. The container image is immutable, so you
   can pin to any prior image.
3. If the issue is config-only (missing env var, bad domain, etc.), Railway
   restarts on env var changes — no redeploy needed.
4. The OAuth + App registrations on GitHub are stable; you don't need to
   recreate them unless the secrets themselves leak.

---

## 11. Quick commands

```bash
# Run tests locally
cd /Users/dks0662779/skillsmcp
uv run pytest --no-cov -q

# Lint + format
uv run ruff check . && uv run ruff format --check .

# Build the Docker image locally (sanity check)
docker build -t skills-registry-mcp:dev .

# Run it locally with a dummy config
docker run --rm -p 8000:8000 \
  -e FASTMCP_SERVER_AUTH_GITHUB_BASE_URL=http://localhost:8000 \
  -e FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID=test \
  -e FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET=test \
  -e GITHUB_APP_ID=1 \
  -e GITHUB_APP_PRIVATE_KEY="$(cat path/to/dev.pem)" \
  -e GITHUB_APP_WEBHOOK_SECRET=dev \
  -e GITHUB_APP_SLUG=dev \
  -e JWT_SIGNING_KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(64))") \
  -e FASTMCP_STORAGE_DIR=/data/oauth \
  -e STORAGE_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") \
  -v $(pwd)/.local-data:/data \
  skills-registry-mcp:dev
# → check http://localhost:8000/healthz

# Tail Railway logs (requires Railway CLI)
railway logs --service skills-registry-mcp-web

# Probe production
curl https://mcp.skills-registry.dev/healthz
curl https://mcp.skills-registry.dev/.well-known/oauth-authorization-server | jq .
```

---

## 12. Where to look when things go wrong

| Symptom | First place to look |
|---|---|
| Container exits immediately | Railway logs → `Missing required env var: …` |
| `401 bad signature` in webhook logs | `GITHUB_APP_WEBHOOK_SECRET` mismatch between Railway and GitHub App settings |
| `list_skills` always returns "no repo linked" | Webhook isn't reaching us. Check GitHub App → Advanced → Recent Deliveries. The webhook URL must match exactly. |
| OAuth redirect loop | OAuth App callback URL ≠ `<base_url>/auth/callback`. Check both Railway env (`FASTMCP_SERVER_AUTH_GITHUB_BASE_URL`) and GitHub OAuth App settings. |
| `401` on `/mcp` requests | FastMCP JWT signing key mismatch, OR storage encryption key mismatch (tokens were encrypted with a different `STORAGE_ENCRYPTION_KEY`). |
| Volume full | `FileTreeStore` writes one JSON file per OAuth client. 1 GB is plenty for 100k clients — you have orders of magnitude of headroom. If it actually fills up, something is wrong (probably a webhook loop creating dupes). |

---

**Last updated:** 2026-05-24 by the previous Droid session. The commit
that lands this doc also lands the implementation; everything before it
in `git log` is preparation (the migration plan + the empty Railway/GH
provisioning). Everything *after* it should be deployment + post-launch
cleanup.
