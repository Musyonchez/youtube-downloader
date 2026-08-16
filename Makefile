.PHONY: help check lint format type-check syntax test e2e install-dev install clean run

# Detect virtual environment (Windows venvs use Scripts/, POSIX uses bin/)
VENV := venv
ifeq ($(OS),Windows_NT)
    VENV_BIN := $(VENV)/Scripts
else
    VENV_BIN := $(VENV)/bin
endif
PYTHON := $(VENV_BIN)/python
PIP := $(VENV_BIN)/pip
MYPY := $(VENV_BIN)/mypy
RUFF := $(VENV_BIN)/ruff
FLAKE8 := $(VENV_BIN)/flake8
PYTEST := $(VENV_BIN)/pytest

help:
	@echo "YouTube Downloader - Available commands:"
	@echo ""
	@echo "  make check        - Run all checks (syntax, type checking, linting, tests)"
	@echo "  make lint         - Run linting with ruff and flake8"
	@echo "  make format       - Format code with ruff"
	@echo "  make type-check   - Run type checking with mypy"
	@echo "  make syntax       - Check Python syntax"
	@echo "  make test         - Run the test suite with pytest"
	@echo "  make e2e          - Run browser smoke tests (Playwright, mocked search)"
	@echo "  make install-dev  - Install development dependencies"
	@echo "  make install      - Install production dependencies"
	@echo "  make run          - Run the application"
	@echo "  make clean        - Clean cache files"

# Install production dependencies (pinned -- see requirements.lock's header, docs/16 16-15)
install:
	@if [ ! -d "$(VENV)" ]; then python -m venv $(VENV); fi
	$(PIP) install -r requirements.lock

# Install development dependencies
install-dev: install
	$(PIP) install -r requirements-dev.txt

# Run all checks
check: syntax type-check lint test
	@echo ""
	@echo "✅ All checks passed!"

# Check Python syntax
syntax:
	@echo "🔍 Checking Python syntax..."
	@find app -name "*.py" -exec $(PYTHON) -m py_compile {} +
	@echo "✅ Syntax check passed"

# Run type checking
type-check:
	@echo "🔍 Running type checks..."
	@$(MYPY) app/ --ignore-missing-imports --no-strict-optional

# Run linting
lint:
	@echo "🔍 Running linting..."
	@$(RUFF) check .
	@$(FLAKE8) app/ --max-line-length=120 --ignore=E501,W503

# Run the test suite
test:
	@echo "🧪 Running tests..."
	@$(PYTEST) tests/

# Run browser smoke tests against a dev server with search mocked (no real
# YouTube calls -- see tests/e2e/serve_for_e2e.py). Requires `npm install`
# and `npx playwright install chromium` once in tests/e2e/ first.
e2e:
	@echo "🌐 Starting dev server (search mocked)..."
	@$(PYTHON) tests/e2e/serve_for_e2e.py & echo $$! > /tmp/yt-downloader-e2e.pid
	@timeout 30 bash -c 'until curl -sf http://127.0.0.1:8000/health >/dev/null; do sleep 1; done'
	@echo "🎭 Running Playwright..."
	@cd tests/e2e && npx playwright test; \
		status=$$?; \
		kill $$(cat /tmp/yt-downloader-e2e.pid) 2>/dev/null || true; \
		rm -f /tmp/yt-downloader-e2e.pid; \
		exit $$status

# Format code
format:
	@echo "✨ Formatting code..."
	@$(RUFF) format .

# Run the application
run:
	@bash run.sh

# Clean cache files
clean:
	@echo "🧹 Cleaning cache files..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "✅ Clean complete"
