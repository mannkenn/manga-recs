# Manga Recs

End-to-end ML recommendation project that suggests similar manga titles from AniList-derived data.

This repository includes:
- data ingestion and transformation pipelines
- feature engineering and similarity-model training
- a FastAPI backend for recommendations
- a Next.js frontend for user interaction

## Architecture

The project follows a modular layout:
- `src/manga_recs/data`: ingestion, cleaning, feature generation, storage helpers
- `src/manga_recs/models`: model training
- `src/manga_recs/serving`: local inference logic
- `src/manga_recs/api`: FastAPI app + schemas
- `src/manga_recs/pipelines`: orchestration layer
- `src/manga_recs/common`: shared constants, paths, and runtime settings
- `scripts/`: thin executable entrypoints
- `configs/`: runtime configuration files

## Quick Start

### 1) Create environment and install dependencies

```bash
make venv
source .venv/bin/activate
make install
make install-dev
```

Dependency source of truth:
- Runtime deps live in `pyproject.toml` under `[project.dependencies]`
- Dev deps live in `[project.optional-dependencies].dev`
- `requirements.txt` is intentionally minimal and installs the project (`-e .`)

### 2) Configure local settings

```bash
cp configs/local.example.toml configs/local.toml
```

Then adjust values in `configs/local.toml` as needed.

### 3) Run the pipeline and API

```bash
make run-pipeline
make run-train
make run-api
```

## CLI Usage

The project exposes a unified CLI wrapper.

### Without installing script entrypoint

```bash
PYTHONPATH=src python -m manga_recs.cli --help
```

### After install (`pip install -e .`)

```bash
manga-recs --help
```

### Commands

```bash
manga-recs ingest
manga-recs clean
manga-recs features
manga-recs pipeline
manga-recs train
manga-recs api --host 127.0.0.1 --port 8000
```

## Make Targets

```bash
make help
```

Common targets:
- `make run-ingestion`
- `make run-clean`
- `make run-features`
- `make run-pipeline`
- `make run-train`
- `make run-api`

## Configuration (How and Why)

Configuration lets you change runtime behavior without modifying source code.

### Files
- `configs/base.toml`: committed defaults for the team
- `configs/local.toml`: local machine overrides (gitignored)
- `configs/local.example.toml`: template for local overrides

### Loading order
1. `configs/base.toml`
2. `configs/local.toml` (if present)
3. environment variable overrides (highest priority)

### Optional override file path

```bash
MANGA_RECS_CONFIG=configs/local.toml make run-pipeline
```

### Environment variable overrides
- `MANGA_RECS_S3_BUCKET`
- `MANGA_RECS_GRAPHQL_URL`
- `MANGA_RECS_MLFLOW_EXPERIMENT`

Settings are loaded in `src/manga_recs/common/settings.py`.

## API

Backend runs on `http://localhost:8000` by default.

### Endpoint
- `POST /recommendations/`

### Example request

```bash
curl -X POST "http://localhost:8000/recommendations/" \
	-H "Content-Type: application/json" \
	-d '{"title":"One Piece", "top_n":5}'
```

### Example response shape

```json
{
	"title": "One Piece",
	"recommendations": [
		{
			"id": 123,
			"title": "...",
			"description": "...",
			"tags": ["..."],
			"similarity": 0.92
		}
	]
}
```

## Frontend

Frontend lives in `frontend/` and talks to the FastAPI backend.

```bash
cd frontend
npm install
npm run dev
```

By default, frontend requests are proxied to `http://localhost:8000`.
Set `BACKEND_URL` in `frontend/.env.local` to override.

## Data and Artifacts

Generated outputs under `data/` are intentionally ignored from version control:
- `data/raw/`
- `data/cleaned/`
- `data/features/`
- `data/models/`

MLflow runs are stored under `mlruns/` (also ignored where configured).

## Testing

The repo includes multiple test levels (`tests/e2e`, `tests/integration`, etc.).
As you expand coverage, prefer quick unit tests for transforms and utility logic first.

## Development Notes

- Keep dependencies in `pyproject.toml` (single source of truth)
- Prefer CLI/Make targets over direct module execution
- Use config overrides (`configs/local.toml`) for environment-specific behavior


