# 15 — Real Auth: Login/Register Pages (replacing HTTP Basic Auth)

The Basic Auth gate added in [14-deployment.md](14-deployment.md) works
but shows the browser's native credential popup — ugly, and there's no
way to have a proper "who's logged in" experience. This replaces it
entirely with real login/register pages styled to match the app, backed
by session cookies.

## Decisions made

- **Registration: first user only, then closed.** Whoever registers first
  becomes the account; the register route refuses everyone after that
  (enforced server-side, not just hidden in the UI — a security boundary,
  not a nicety). No shared secret to manage or rotate.
- **Landing page (`/`) stays public.** Everything else requires a session:
  `/app/*`, `/history`, all of `/api/*`, and `/ws`.
- **Session cookies, not JWT/tokens.** Starlette's built-in
  `SessionMiddleware` (itsdangerous-signed cookie, no server-side session
  store to run/manage) is enough for a single-account app. New dependency:
  `itsdangerous` (Starlette's own optional dep for this — not adding
  anything Starlette doesn't already know how to use).
- **Password hashing via stdlib** (`hashlib.pbkdf2_hmac`), not a new
  dependency like `passlib`/`bcrypt` — consistent with this project's
  existing bias toward stdlib over new packages at this scale.
- **Fully replaces `app/auth.py`'s `BasicAuthMiddleware`**, not
  toggle-able alongside it — one auth system, not two overlapping ones.

## Data model

New table in `app/storage/db.py` (same file that already owns `library`/
`downloaded`):

```sql
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

`password_hash` is self-describing: `pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>`
so the iteration count/algorithm can change later without a migration.

New `Database`/`Storage` methods: `create_user`, `get_user`,
`count_users` (drives the registration-gate check).

## New module: `app/session_auth.py`

Pure ASGI middleware (same pattern as the `BasicAuthMiddleware` it
replaces — see that file's docstring for why pure ASGI instead of
`BaseHTTPMiddleware`: it needs to gate WebSocket handshakes too, which
`BaseHTTPMiddleware` can't see).

Path allowlist (always accessible, no session required):
`/`, `/login`, `/register`, `/logout`, `/health`, `/static/*`.

Everything else is protected, split by response type so failures are
usable by their caller:
- **Page routes** (`/app/*`, `/history`): redirect (303) to
  `/login?next=<path>` when there's no valid session.
- **API/WS** (`/api/*`, `/ws`): 401 JSON body / WS close code 4401 when
  there's no valid session — a redirect would be useless to a `fetch()`
  call or a WebSocket handshake (mirrors `BasicAuthMiddleware`'s existing
  WS handling exactly).

## Routes (new, in `app/main.py` or a new `app/api/auth_routes.py`)

- `GET /login` — render `login.html`. If already logged in, redirect to `/app/name`.
- `POST /login` — verify username/password, set `request.session["user"]`, redirect to `next` (validated to be a same-app relative path — no open-redirect) or `/app/name`.
- `GET /register` — render `register.html` **only if `count_users() == 0`**; otherwise redirect to `/login`.
- `POST /register` — re-check `count_users() == 0` server-side (the real gate — the GET check above is just UX, don't rely on it), create the user, log them in, redirect to `/app/name`.
- `POST /logout` — clear the session, redirect to `/`.

## Templates

`templates/login.html` and `templates/register.html` — centered card
forms, built from the same shared partials/tokens as every other page
(`navbar.html`, `head_extras.html`, `variables.css`, `nav.css`) so they
look like part of the app, not a bolted-on generic form. Register page
should not even render a form if registration is closed — show a plain
"registration is closed" message instead (defense in depth alongside the
server-side redirect).

## Navbar

`navbar.html` needs to show auth state: **Login** link when logged out
(**Register** link too, only while `count_users() == 0`); the username +
a **Logout** button when logged in. Cleanest way to make the current
user available to every template without editing every route handler's
context dict: register a Jinja global function (e.g.
`templates.env.globals["current_user"] = lambda request: request.session.get("user")`)
and call it as `{{ current_user(request) }}` in the template — `request`
is already in context on every `TemplateResponse` call.

## Testing

- `hash_password`/`verify_password` round-trip, wrong password rejected, unit-level.
- `db.py`: create/get/count users, duplicate username rejected.
- Route-level (`TestClient`, following the pattern in `tests/test_api_routes.py`):
  - Register with zero users succeeds and logs the caller in.
  - Register with an existing user is refused **even when POSTed directly**
    (not just hidden from the UI) — this is the actual security test.
  - Wrong password on login is rejected.
  - A protected page without a session redirects to `/login`.
  - A protected API route without a session returns 401.
  - `/` is reachable with no session at all.
  - Logout clears the session (subsequent protected request redirects again).

## Deploy migration

- `requirements.txt`: add `itsdangerous`.
- Fly secrets: unset `APP_USERNAME`/`APP_PASSWORD`, set a new `SECRET_KEY`
  (random, signs the session cookie — treat it like any other credential).
- `docs/14-deployment.md` updated: drop the Basic Auth section, note that
  after deploying, visiting `/register` once (before anyone else does) is
  how the sole account gets created — and that it's a race the deployer
  should win immediately after first deploy, not leave sitting open.
- `app/auth.py` and `tests/test_auth.py` (the Basic Auth version) removed.
