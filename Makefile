.PHONY: help check lint format type-check syntax test install-dev install clean run

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
	@echo "  make install-dev  - Install development dependencies"
	@echo "  make install      - Install production dependencies"
	@echo "  make run          - Run the application"
	@echo "  make clean        - Clean cache files"

# Install production dependencies
install:
	@if [ ! -d "$(VENV)" ]; then python -m venv $(VENV); fi
	$(PIP) install -r requirements.txt

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
	@$(PYTHON) -m py_compile app.py downloader.py search.py utils.py ws_manager.py api/__init__.py api/routes.py
	@echo "✅ Syntax check passed"

# Run type checking
type-check:
	@echo "🔍 Running type checks..."
	@$(MYPY) app.py downloader.py search.py utils.py ws_manager.py api/ --ignore-missing-imports --no-strict-optional

# Run linting
lint:
	@echo "🔍 Running linting..."
	@$(RUFF) check .
	@$(FLAKE8) app.py downloader.py search.py utils.py ws_manager.py api/ --max-line-length=120 --ignore=E501,W503

# Run the test suite
test:
	@echo "🧪 Running tests..."
	@$(PYTEST) tests/

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
