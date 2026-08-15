# Contributing

This is a personal project, but `master` is branch-protected (PRs required,
CI must pass, no force-push, enforced for admins too — see repo settings).
Workflow:

1. Branch off `master`: `git checkout -b <short-description>`
2. Commit, push, open a PR into `master`.
3. CI (`check` + `e2e` workflows) must pass before merge.
4. Merge via **squash** (the only merge method enabled) — branches are
   auto-deleted on merge.

## Local checks before pushing

```bash
make check   # syntax, mypy, ruff, flake8, pytest
make e2e     # Playwright smoke tests (see tests/e2e/README or Makefile)
```

## Repo layout note

See [docs/README.md](docs/README.md) for the full documentation index —
audits, the UI redesign history, and deployment notes all live there. If
you're adding the planned browser extension, see
[docs/14-deployment.md](docs/14-deployment.md)'s note on keeping it as a
sibling top-level directory (`extension/`) so it doesn't interfere with
the existing Docker build.
