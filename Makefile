PYTHON ?= python
PIP ?= $(PYTHON) -m pip
PKG ?= manga_recs
PYTHONPATH ?= src

.PHONY: help venv install install-dev clean \
	run-ingestion run-clean run-features run-pipeline run-train run-api

help: ## Show available commands
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "%-18s %s\n", $$1, $$2}'

venv: ## Create virtual environment at .venv
	$(PYTHON) -m venv .venv

install: ## Install runtime dependencies
	$(PIP) install -r requirements.txt

install-dev: install ## Install project + common dev tools
	$(PIP) install -e .[dev]

clean: ## Remove temporary files and build artifacts
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	rm -rf build dist src/*.egg-info .pytest_cache .ruff_cache .mypy_cache

run-ingestion: ## Run data ingestion pipeline step
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m $(PKG).cli ingest

run-clean: ## Run data cleaning pipeline step
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m $(PKG).cli clean

run-features: ## Run feature engineering pipeline step
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m $(PKG).cli features

run-pipeline: ## Run full data pipeline (ingestion -> clean -> features)
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m $(PKG).cli pipeline

run-train: ## Train similarity model
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m $(PKG).cli train

run-api: ## Start FastAPI server locally
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m $(PKG).cli api --host 127.0.0.1 --port 8000

