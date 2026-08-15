# Fixing the Audit Findings

Actionable fixes for each item in [01-audit.md](01-audit.md), grouped the same way. Each entry has the concrete change and, where relevant, why that specific fix rather than an alternative.

## Correctness / consistency

### README song count is inconsistent

Update the stale line in the Tech Stack → Storage section to match the corrected count elsewhere in the file.

- File: [README.md:384](../README.md#L384)
- Change: `"Track 6,000+ songs efficiently"` → `"Track 655+ songs efficiently"` (or drop the number and say `"Track songs efficiently"` so it never goes stale again).

### Unused dependencies

Remove `pillow` and `requests` from [requirements.txt](../requirements.txt) — neither is imported anywhere. Re-run `pip install -r requirements.txt` in the venv afterward so the installed set matches (or just leave already-installed packages; they're harmless if not declared).

### WebSocket endpoint is a stub

Two options, pick based on whether real-time progress is actually wanted:

1. **Wire it up for real**: have `download_task` in [api/routes.py](../api/routes.py) accept the `ConnectionManager` (or a callback) and call `manager.broadcast(...)` from `downloader.py`'s `_progress_hook`, since that's the only place per-file byte progress is available. Requires passing the manager instance from `app.py` into the router (module-level singleton, or FastAPI dependency injection).
2. **Remove it**: if the frontend already polls `/api/status` or `/api/library` for progress (check `app.js`), delete the `/ws` route and `ConnectionManager` entirely rather than keeping dead infrastructure around.

Confirm which by checking whether `app.js` opens a WebSocket connection anywhere before choosing.

### Fragile template rendering

Replace the manual `content.replace(...)` chain in [app.py:90-142](../app.py#L90-L142) with real Jinja2, since FastAPI already ships with `Jinja2Templates` support and the templates already use Jinja-like syntax (`{{ mode }}`, `{% if %}`) that was never actually being parsed by an engine.

```python
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@app.get("/app/{mode}", response_class=HTMLResponse)
async def read_app(request: Request, mode: str):
    if mode not in ["name", "playlist", "url"]:
        return HTMLResponse(content="<h1>Invalid mode</h1>", status_code=404)
    return templates.TemplateResponse("app.html", {"request": request, "mode": mode})
```

Then update `templates/app.html` to use real Jinja conditionals (`{% if mode == 'name' %}...{% endif %}`) instead of the current placeholder tags that were being string-matched. This removes the entire class of "UI copy changed, mode-specific text silently broke" bugs.

## Security

### CORS config is contradictory

Since this is a personal LAN tool (per the README), the fix is to stop allowing credentials rather than to lock down origins (no login/cookie auth exists to protect anyway):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

If auth is ever added later, switch to an explicit origin allowlist (e.g. `["http://localhost:8000", "http://<lan-ip>:8000"]`) instead of `"*"`, and only then re-enable `allow_credentials`.

### No auth on API routes

No fix needed now — this is a documented, intentional tradeoff for a LAN-only personal tool. Revisit only if the app is ever exposed outside the home network (e.g. via port-forwarding or a tunnel); at that point add a shared-secret header or basic auth in front of the `/api/*` routes.

## Dead / legacy code

### Legacy `old.html` / `style.css`

Confirm the old UI is no longer needed, then remove:

```
rm templates/old.html static/css/style.css
```

And delete the `/old` route in [app.py:81-87](../app.py#L81-L87). If there's any chance it's still wanted as a fallback, leave it — but the audit flags it because it's currently unreferenced dead weight if nobody uses `/old`.

### One-off scripts at repo root

Move `download_temp.py` and `rename_bible.py` into a `scripts/` folder to separate one-off personal utilities from the core app modules:

```
mkdir scripts
git mv download_temp.py scripts/download_temp.py
git mv rename_bible.py scripts/rename_bible.py
```

No code changes needed — both scripts use relative paths (`./temp`) and don't import from `app.py`/`downloader.py`/etc., so moving them doesn't break anything.

## Tooling

### `make check` swallows failures

Remove the `|| true` from the `type-check` and `lint` targets in [Makefile:47](../Makefile#L47) and [Makefile:52-53](../Makefile#L52-L53) so failures actually propagate:

```makefile
type-check:
	@echo "🔍 Running type checks..."
	@$(MYPY) app.py downloader.py search.py utils.py api/ --ignore-missing-imports --no-strict-optional

lint:
	@echo "🔍 Running linting..."
	@$(RUFF) check .
	@$(FLAKE8) app.py downloader.py search.py utils.py api/ --max-line-length=120 --ignore=E501,W503
```

Expect this to surface existing lint/type issues that were previously hidden — run `make check` once after this change and triage what comes up before relying on it as a gate.

### Makefile / run.sh assume POSIX venv layout

On Windows without Git Bash/WSL, `venv/bin/python` doesn't exist (it's `venv/Scripts/python.exe`). Two options:

1. **Cheapest**: keep using Git Bash (already the primary shell in this environment) — `venv/bin/...` works fine there since Git Bash on Windows still uses the POSIX-style venv layout when the venv is created via `python -m venv` under Git Bash/MSYS.
2. **More robust**: make the Makefile detect the OS and switch the `VENV`/`PYTHON` paths accordingly, e.g. via `ifeq ($(OS),Windows_NT)`. Only worth doing if `make` is regularly run from a non-Git-Bash shell (plain PowerShell/cmd).

Given the environment already defaults to Git Bash for this project, option 1 (no change) is likely sufficient — verify by running `make check` from Git Bash before investing in cross-platform Makefile logic.

### No automated tests

Add a minimal `pytest` suite for the pure-logic functions in `utils.py` (`sanitize_filename`, `format_duration`, `extract_video_id`) since those don't require network access, unlike `search.py`/`downloader.py`'s YouTube-dependent functions:

```
pip install pytest  # add to requirements-dev.txt
mkdir tests
```

```python
# tests/test_utils.py
from utils import sanitize_filename, format_duration, extract_video_id

def test_sanitize_filename_strips_invalid_chars():
    assert sanitize_filename('a<b>c:d"e/f\\g|h?i*j') == "abcdefghij"

def test_format_duration_under_hour():
    assert format_duration(125) == "02:05"

def test_extract_video_id_from_watch_url():
    assert extract_video_id("https://www.youtube.com/watch?v=jfKfPfyJRdk") == "jfKfPfyJRdk"
```

Add a `make test` target that runs `pytest tests/`. Leave `search.py`/`downloader.py`'s live-network `test_*()` functions as manual smoke tests — not worth mocking `yt_dlp` for this project's size.

## Suggested order

1. README count fix, unused deps, CORS credentials — trivial, no behavior change.
2. Remove `|| true` from Makefile, see what it surfaces, fix or suppress deliberately.
3. Move one-off scripts to `scripts/`.
4. Decide on WebSocket (wire up or remove) and legacy `old.html` (keep or delete) — both need a quick check of `app.js` / usage first.
5. Jinja2 template migration — largest single change, do it on its own so template regressions are easy to isolate.
6. Add the `utils.py` test suite last, once the above stabilizes.
