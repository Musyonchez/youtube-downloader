# 14 — Deployment (Fly.io) + Repo Setup

**Live at:** https://yt-mp3-downloader.fly.dev (HTTP Basic Auth — credentials
are a Fly secret, not in this repo; ask whoever deployed it, or read them
back with `flyctl secrets list --app yt-mp3-downloader` if you have access
— note that only shows *names*, not values; regenerate with
`flyctl secrets set APP_PASSWORD=...` if the value itself is needed and
lost).

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
could search/queue/download through it. `app/auth.py` adds an HTTP Basic
Auth gate that:

- Is a **no-op locally** — it only activates when both `APP_USERNAME` and
  `APP_PASSWORD` are set in the environment. Local/LAN use (`run.sh`/
  `run.ps1`) is completely unaffected — no env vars set, no auth prompt,
  same zero-config experience as before.
- Gates **both HTTP and WebSocket** (`/ws`) — a plain `BaseHTTPMiddleware`
  only sees HTTP, so this is a pure ASGI middleware instead (see the
  module docstring in `app/auth.py`).
- Exempts `/health` unconditionally — Fly's health check has no
  credentials, and the deploy would never go healthy otherwise.

Set the credentials as Fly secrets (never in `fly.toml`, which is
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

# Basic Auth credentials (never committed -- Fly secrets only)
flyctl secrets set APP_USERNAME=<choose one> APP_PASSWORD=<choose a strong one>

# First deploy
flyctl deploy --remote-only

# One-time post-deploy step: the app's default download_dir ("./downloads")
# resolves to ephemeral container storage, not the volume. Point it at a
# subdirectory of the mounted volume instead, using the app's own existing
# config API (no code change needed -- download_dir has always been
# user-configurable):
curl -u "<username>:<password>" -X POST -H "Content-Type: application/json" \
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
