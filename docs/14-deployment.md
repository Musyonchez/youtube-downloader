# 14 — Deployment (Fly.io) + Repo Setup

**Live at:** https://yt-mp3-downloader.fly.dev (session-cookie login — see
[15-auth-plan.md](15-auth-plan.md). The one account is created by visiting
`/register` once, immediately after first deploy; `SECRET_KEY` (signs the
session cookie) is a Fly secret, not in this repo — read its *name* back
with `flyctl secrets list --app yt-mp3-downloader` if needed, or rotate it
with `flyctl secrets set SECRET_KEY=...` (rotating invalidates all existing
sessions, which is fine — everyone just logs in again).

## Repo hardening

- Repo is **public** (required for free branch protection — GitHub only
  offers it on private repos with a Pro plan). No secrets are committed;
  `data/`/`downloads/` are gitignored, config has no credentials.
- `master` is branch-protected: PRs required, `check`/`e2e` CI must pass,
  no force-push, no deletion, **enforced for admins too** (the repo owner
  can't bypass it with a direct push either — see [CONTRIBUTING.md](../CONTRIBUTING.md)
  for the branch → PR → squash-merge workflow this requires).
- Merge method is squash-only; branches auto-delete on merge.

## Why auth had to be added before deploying

This app was built with **no authentication**, on the explicit assumption
it's only reachable on a trusted LAN (a reviewed decision from the
earlier audit, docs/09). Deploying to Fly.io puts it on the public
internet by default, which breaks that assumption — anyone with the URL
could search/queue/download through it. `app/session_auth.py` adds a
session-cookie login gate (docs/15) that:

- Is effectively **zero-config locally** — `SECRET_KEY` (which signs the
  session cookie) generates a random value at process startup if unset, so
  `run.sh`/`run.ps1`/pytest all work with no env vars. The only cost is
  that sessions don't survive a restart without a persistent `SECRET_KEY`
  — a non-issue for local/LAN use, but production must set the Fly secret
  (below) or every deploy silently logs everyone out.
- Gates **both HTTP and WebSocket** (`/ws`) — a plain `BaseHTTPMiddleware`
  only sees HTTP, so this is a pure ASGI middleware instead (see the
  module docstring in `app/session_auth.py`).
- Exempts `/`, `/login`, `/register`, `/logout`, `/health`, and `/static/*`
  unconditionally — `/health` because Fly's health check has no session,
  and the deploy would never go healthy otherwise; the rest because they
  need to be reachable *without* a session by definition.
- Registration is **first-user-only, then closed** (docs/15) — there's no
  shared secret to generate/rotate/hand out; whoever visits `/register`
  first becomes the one account.

Set `SECRET_KEY` as a Fly secret (never in `fly.toml`, which is
committed): see the runbook below.

## First-time Fly.io setup

Run once, after `flyctl auth login`:

```bash
# Create the app (name is in fly.toml already; this just registers it)
flyctl apps create yt-mp3-downloader

# ONE volume -- Fly Machines only support a single mounted volume per
# machine (the original plan of separate data/downloads volumes doesn't
# work on this platform; discovered at first-deploy time). Match
# fly.toml's single [[mounts]] block. Sized generously since it holds
# both the DB/config AND every downloaded MP3.
flyctl volumes create yt_downloader_data --region iad --size 15

# SECRET_KEY signs the session cookie (never committed -- Fly secrets only).
# Generate a real random value, don't type one by hand:
flyctl secrets set SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# First deploy
flyctl deploy --remote-only

# One-time, TIME-SENSITIVE post-deploy step: registration is open to
# whoever visits /register first (docs/15) -- there's no shared secret to
# gate it, so the deployer needs to win this race immediately after the
# app goes healthy, not leave it sitting open. Visit
# https://yt-mp3-downloader.fly.dev/register in a browser and create the
# account right away; after that submission, the route refuses everyone
# else server-side (not just hidden in the UI).
#
# Then, now logged in: the app's default download_dir ("./downloads")
# resolves to ephemeral container storage, not the volume. Point it at a
# subdirectory of the mounted volume instead, using the app's own existing
# config API (no code change needed -- download_dir has always been
# user-configurable). Grab the session cookie from the browser you just
# registered with (devtools -> Application -> Cookies) and pass it here,
# or just use the Settings modal in the UI instead of curl:
curl -b "session=<cookie value from the browser you just registered with>" \
  -X POST -H "Content-Type: application/json" \
  -d '{"download_dir": "/srv/data/downloads"}' \
  https://yt-mp3-downloader.fly.dev/api/config
```

Adjust `--size` (GB) based on how large the library is expected to get;
it can be extended later without downtime (`flyctl volumes extend`).

## Ongoing deploys (CD)

`.github/workflows/deploy.yml` deploys automatically after `.github/workflows/ci.yml`'s
run against `master` succeeds (i.e. after every PR merge, once CI has
re-run on master itself and passed). Requires a `FLY_API_TOKEN` repo
secret:

```bash
flyctl tokens create deploy -x 999999h | gh secret set FLY_API_TOKEN
```

## Repo structure note: the planned browser extension

A browser extension is planned for this same repo later. Plan: a sibling
top-level directory (`extension/`), not a restructure of the existing
app. Already accounted for:

- `.dockerignore` excludes `extension/` — it'll never end up in the
  server's Docker image regardless of what it contains or how it's built.
- The Fly app only ever builds/deploys the existing `Dockerfile`, which
  only `COPY`s what the server needs — adding `extension/` at the repo
  root requires no changes to the deploy pipeline.
- CI (`ci.yml`) currently only checks Python — when the extension lands,
  add a separate job (or a separate workflow file) for its own
  lint/build/test step, path-filtered to `extension/**` so unrelated
  Python-only PRs don't wait on it.
