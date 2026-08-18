PYTHON ?= python
PIP ?= $(PYTHON) -m pip
PKG ?= manga_recs

.PHONY: help venv install install-pipeline install-dev clean \
	minio minio-down airflow airflow-down \
	lint format test test-unit cov \
	run-ingestion run-clean run-features run-pipeline run-train run-evaluate run-api \
	status bundle frontend-build \
	docker-build docker-run docker-run-readonly docker-smoke

help: ## Show available commands
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "%-18s %s\n", $$1, $$2}'

venv: ## Create virtual environment at .venv
	$(PYTHON) -m venv .venv

install: ## Install serving dependencies only (what the deployed image gets)
	$(PIP) install -e .

install-pipeline: ## Install serving plus pipeline dependencies (boto3, mlflow, sklearn)
	$(PIP) install -e ".[pipeline]"

install-dev: ## Install everything plus test and lint tooling
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

# --- deployment ---------------------------------------------------------

bundle: ## Copy published serving artifacts locally so the image can bake them in
	$(PYTHON) -m $(PKG).cli bundle

frontend-build: ## Build the static frontend into frontend/out
	cd frontend && npm ci && npm run build

# --- container ----------------------------------------------------------

IMAGE ?= manga-recs
PORT ?= 7860

docker-build: ## Build the single-container demo image (API + UI + artifacts)
	docker build -t $(IMAGE) .

docker-run: ## Run the demo image on $(PORT)
	docker run --rm -p $(PORT):7860 $(IMAGE)

docker-run-readonly: ## Run exactly as Hugging Face Spaces does: read-only FS, /tmp only
	docker run --rm -p $(PORT):7860 --read-only --tmpfs /tmp $(IMAGE)

docker-smoke: ## Build, boot read-only, and assert /health and /recommendations/ work
	./scripts/smoke_test.sh $(IMAGE) $(PORT)
