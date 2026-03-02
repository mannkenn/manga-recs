# Manga Recs

End-to-end ML recommendation project that suggests similar manga from AniList data.

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
- `configs/`: runtime config files

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
