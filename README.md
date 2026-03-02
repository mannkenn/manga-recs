building end-to-end ml project for a manga recommendation system using data from anilist api

## Python dependencies

This project keeps dependencies in `pyproject.toml`.

- Add or update runtime packages in `[project.dependencies]`.
- Add or update developer-only tools in `[project.optional-dependencies].dev`.
- `requirements.txt` is intentionally minimal (`-e .`) so environments that still use `pip install -r requirements.txt` install the package and its `pyproject.toml` dependencies.

Typical setup:

```bash
make venv
source .venv/bin/activate
make install
make install-dev
```

## CLI

Use a single CLI wrapper for common workflows:

```bash
PYTHONPATH=src python -m manga_recs.cli --help
PYTHONPATH=src python -m manga_recs.cli ingest
PYTHONPATH=src python -m manga_recs.cli clean
PYTHONPATH=src python -m manga_recs.cli features
PYTHONPATH=src python -m manga_recs.cli pipeline
PYTHONPATH=src python -m manga_recs.cli train
PYTHONPATH=src python -m manga_recs.cli api --host 127.0.0.1 --port 8000
```

After `make install` (or `pip install -e .`), you can also use:

```bash
manga-recs --help
```

## Configuration

This project uses config files so you can change runtime behavior **without editing Python code**.

- Base config: `configs/base.toml` (committed, shared defaults)
- Local override: `configs/local.toml` (ignored by git)
- Example override file: `configs/local.example.toml`

Why config exists:

- Separate code from environment/runtime choices (bucket, pull limits, API thresholds)
- Keep team defaults in one place
- Let each developer or environment override values safely

How it loads:

1. Load `configs/base.toml`
2. Merge `configs/local.toml` if present
3. Apply env var overrides (highest priority)

Create local config:

```bash
cp configs/local.example.toml configs/local.toml
```

Use a different config file temporarily:

```bash
MANGA_RECS_CONFIG=configs/local.toml make run-pipeline
```

Useful environment variable overrides:

- `MANGA_RECS_S3_BUCKET`
- `MANGA_RECS_GRAPHQL_URL`
- `MANGA_RECS_MLFLOW_EXPERIMENT`

Config values are loaded in `src/manga_recs/common/settings.py` and consumed by ingestion, S3 IO, model training, and API/serving modules.

## Frontend

A Next.js React frontend lives in the `frontend/` directory. It provides a simple UI for the FastAPI backend and can be started with:

```bash
cd frontend && npm install && npm run dev
```

The frontend proxies `/api/recommendations` to the backend at `http://localhost:8000` by default (set `BACKEND_URL` in `.env.local` to override).


