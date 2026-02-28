.PHONY: help install install-dev test lint format clean run-api run-pipeline train

# Default target
help:
	@echo "Available commands:"
	@echo "  make install       - Install production dependencies"
	@echo "  make install-dev   - Install development dependencies"
	@echo "  make test          - Run tests with coverage"
	@echo "  make lint          - Run linting checks"
	@echo "  make format        - Format code with Black and isort"
	@echo "  make clean         - Remove build artifacts and cache"
	@echo "  make run-api       - Start the FastAPI server"
	@echo "  make run-pipeline  - Run the data pipeline"
	@echo "  make train         - Train the ML model"
	@echo "  make pre-commit    - Install pre-commit hooks"

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

# Testing
test:
	pytest tests/ -v --cov=manga_recs --cov-report=html --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-e2e:
	pytest tests/e2e/ -v

# Code quality
lint:
	flake8 src/
	mypy src/manga_recs --ignore-missing-imports
	bandit -r src/ -c pyproject.toml

format:
	black src/ tests/
	isort src/ tests/

format-check:
	black --check src/ tests/
	isort --check-only src/ tests/

# Pre-commit
pre-commit:
	pre-commit install
	@echo "Pre-commit hooks installed successfully!"

pre-commit-run:
	pre-commit run --all-files

# Cleaning
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .pytest_cache/ .coverage htmlcov/ .mypy_cache/

# Running services
run-api:
	uvicorn manga_recs.api.main:app --reload --host 0.0.0.0 --port 8000

run-pipeline:
	python -m manga_recs.pipelines.run_pipelines

train:
	python -m manga_recs.ml.train_similarity

# Data operations
ingest:
	python -m manga_recs.pipelines.run_ingestion

clean-data:
	python -m manga_recs.pipelines.run_clean

build-features:
	python -m manga_recs.pipelines.run_feature_engineering

# Frontend
frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

# Combined commands
dev: install-dev pre-commit
	@echo "Development environment setup complete!"

ci: lint test
	@echo "CI checks passed!"
