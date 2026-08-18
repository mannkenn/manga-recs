PYTHON ?= python
PIP ?= $(PYTHON) -m pip
PKG ?= manga_recs

.PHONY: help venv install install-dev clean \
	minio minio-down airflow airflow-down \
	lint format test test-unit cov \
	run-ingestion run-clean run-features run-pipeline run-train run-evaluate run-api \
	status docker-build docker-run

help: ## Show available commands
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "%-18s %s\n", $$1, $$2}'

venv: ## Create virtual environment at .venv
	$(PYTHON) -m venv .venv

install: ## Install runtime dependencies
	$(PIP) install -e .

install-dev: ## Install project plus dev tooling
	$(PIP) install -e ".[dev]"

clean: ## Remove temporary files and build artifacts
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	rm -rf build dist src/*.egg-info .pytest_cache .ruff_cache .coverage coverage.xml htmlcov

# --- local infrastructure -----------------------------------------------

minio: ## Start local S3-compatible storage (MinIO) and create the bucket
	docker compose up -d minio minio-init
	@echo "MinIO API      http://localhost:9000"
	@echo "MinIO console  http://localhost:9001  (minioadmin / minioadmin)"

minio-down: ## Stop MinIO
	docker compose down

airflow: ## Start local Airflow (http://localhost:8080, airflow/airflow)
	docker compose -f airflow/docker-compose.yml up -d
	@echo "Airflow UI     http://localhost:8080"

airflow-down: ## Stop local Airflow
	docker compose -f airflow/docker-compose.yml down

# --- quality ------------------------------------------------------------

lint: ## Check formatting and lint rules
	ruff check .
	ruff format --check .

format: ## Auto-format and auto-fix
	ruff format .
	ruff check --fix .

test: ## Run the full test suite (needs MinIO for integration tests)
	pytest

test-unit: ## Run only tests that need no infrastructure
	pytest --ignore=tests/test_object_store.py

cov: ## Run tests with a coverage report
	pytest --cov=$(PKG) --cov-report=term-missing

# --- pipeline -----------------------------------------------------------

run-ingestion: ## Fetch raw data from AniList
	$(PYTHON) -m $(PKG).cli ingest

run-clean: ## Normalize raw data into validated Parquet
	$(PYTHON) -m $(PKG).cli clean

run-features: ## Build model-ready feature matrices
	$(PYTHON) -m $(PKG).cli features

run-pipeline: ## Run ingest -> clean -> features
	$(PYTHON) -m $(PKG).cli pipeline

run-train: ## Train the similarity model
	$(PYTHON) -m $(PKG).cli train

run-evaluate: ## Score the model against held-out user history
	$(PYTHON) -m $(PKG).cli evaluate

run-api: ## Start FastAPI server locally
	$(PYTHON) -m $(PKG).cli api --host 127.0.0.1 --port 8000

status: ## Show the configured storage backend and its partitions
	$(PYTHON) -m $(PKG).cli status

# --- container ----------------------------------------------------------

docker-build: ## Build the API container image
	docker build -t manga-recs-api .

docker-run: ## Run the API container against local MinIO
	docker compose --profile api up --build api
