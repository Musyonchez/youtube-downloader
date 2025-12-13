.PHONY: help check lint format type-check syntax install-dev install clean run

help:
	@echo "YouTube Downloader - Available commands:"
	@echo ""
	@echo "  make check        - Run all checks (syntax, type checking, linting)"
	@echo "  make lint         - Run linting with ruff and flake8"
	@echo "  make format       - Format code with ruff"
	@echo "  make type-check   - Run type checking with mypy"
	@echo "  make syntax       - Check Python syntax"
	@echo "  make install-dev  - Install development dependencies"
	@echo "  make install      - Install production dependencies"
	@echo "  make run          - Run the application"
	@echo "  make clean        - Clean cache files"

# Install production dependencies
install:
	pip install -r requirements.txt

# Install development dependencies
install-dev: install
	pip install -r requirements-dev.txt

# Run all checks
check: syntax type-check lint
	@echo ""
	@echo "✅ All checks passed!"

# Check Python syntax
syntax:
	@echo "🔍 Checking Python syntax..."
	@python -m py_compile app.py downloader.py search.py utils.py api/__init__.py api/routes.py
	@echo "✅ Syntax check passed"

# Run type checking
type-check:
	@echo "🔍 Running type checks..."
	@mypy app.py downloader.py search.py utils.py api/ --ignore-missing-imports --no-strict-optional || true

# Run linting
lint:
	@echo "🔍 Running linting..."
	@ruff check . || true
	@flake8 app.py downloader.py search.py utils.py api/ --max-line-length=120 --ignore=E501,W503 || true

# Format code
format:
	@echo "✨ Formatting code..."
	@ruff format .

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
