from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

# Must happen before any settings are resolved so that .env participates in the
# same precedence chain as the real environment.
load_dotenv()


@dataclass(frozen=True)
class PathsSettings:
    data_dir: Path
    artifacts_dir: Path


@dataclass(frozen=True)
class StorageSettings:
    """Connection details for an S3-compatible object store.

    ``endpoint_url`` is what makes this portable: leave it unset for AWS S3, or
    point it at Cloudflare R2 / MinIO to run the exact same code path elsewhere.
    """

    bucket: str
    endpoint_url: str | None
    region: str
    force_path_style: bool


@dataclass(frozen=True)
class ApiSettings:
    graphql_url: str
    fuzzy_match_threshold: int


@dataclass(frozen=True)
class IngestionSettings:
    rate_limit: int
    popularity_min: int
    user_start_id: int
    user_end_id: int
    user_max_pages: int
    user_per_page: int
    user_max_retries: int


@dataclass(frozen=True)
class MlflowSettings:
    experiment_name: str


@dataclass(frozen=True)
class RecommendationSettings:
    default_top_n: int


@dataclass(frozen=True)
class EvaluationSettings:
    min_user_interactions: int
    test_fraction: int
    k: int
    random_seed: int


@dataclass(frozen=True)
class Settings:
    paths: PathsSettings
    storage: StorageSettings
    api: ApiSettings
    ingestion: IngestionSettings
    mlflow: MlflowSettings
    recommendation: RecommendationSettings
    evaluation: EvaluationSettings


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _config_root() -> Path:
    """Resolve the directory holding ``configs/``.

    Walks up from this file so the CLI, pytest, and Airflow workers all find the
    same config regardless of their working directory.
    """

    for candidate in [Path.cwd(), *Path(__file__).resolve().parents]:
        if (candidate / "configs" / "base.toml").exists():
            return candidate
    return Path.cwd()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    base_path = _config_root() / "configs" / "base.toml"
    if not base_path.exists():
        raise FileNotFoundError(f"Missing required config file: {base_path}")

    base_config = _load_toml(base_path)

    override_path = os.getenv("MANGA_RECS_CONFIG")
    if override_path:
        override_file = Path(override_path)
    else:
        override_file = base_path.parent / "local.toml"

    override_config: dict[str, Any] = {}
    if override_file.exists():
        override_config = _load_toml(override_file)

    config = _deep_merge(base_config, override_config)

    paths = config.get("paths", {})
    storage = config.get("storage", {})
    api = config.get("api", {})
    ingestion = config.get("ingestion", {})
    mlflow = config.get("mlflow", {})
    recommendation = config.get("recommendation", {})
    evaluation = config.get("evaluation", {})

    endpoint_url = (
        _first_env(
            "MANGA_RECS_S3_ENDPOINT_URL",
            "AWS_ENDPOINT_URL_S3",
        )
        or storage.get("endpoint_url")
        or None
    )

    root = _config_root()

    return Settings(
        paths=PathsSettings(
            data_dir=root / Path(paths.get("data_dir", "data")),
            artifacts_dir=root / Path(paths.get("artifacts_dir", "artifacts")),
        ),
        storage=StorageSettings(
            bucket=_first_env("MANGA_RECS_S3_BUCKET", "MANGA_RECS_STORAGE_BUCKET")
            or storage.get("bucket", "manga-recs"),
            endpoint_url=endpoint_url,
            region=_first_env("AWS_DEFAULT_REGION", "AWS_REGION") or storage.get("region", "auto"),
            # Non-AWS stores (MinIO, and R2 on custom domains) generally require
            # path-style addressing, so default it on whenever an endpoint is set.
            force_path_style=_env_bool(
                "MANGA_RECS_S3_FORCE_PATH_STYLE",
                bool(storage.get("force_path_style", endpoint_url is not None)),
            ),
        ),
        api=ApiSettings(
            graphql_url=os.getenv(
                "MANGA_RECS_GRAPHQL_URL", api.get("graphql_url", "https://graphql.anilist.co")
            ),
            fuzzy_match_threshold=int(api.get("fuzzy_match_threshold", 70)),
        ),
        ingestion=IngestionSettings(
            rate_limit=int(ingestion.get("rate_limit", 10)),
            popularity_min=int(ingestion.get("popularity_min", 10000)),
            user_start_id=int(ingestion.get("user_start_id", 1001)),
            user_end_id=int(ingestion.get("user_end_id", 1500)),
            user_max_pages=int(ingestion.get("user_max_pages", 200)),
            user_per_page=int(ingestion.get("user_per_page", 50)),
            user_max_retries=int(ingestion.get("user_max_retries", 3)),
        ),
        mlflow=MlflowSettings(
            experiment_name=os.getenv(
                "MANGA_RECS_MLFLOW_EXPERIMENT",
                mlflow.get("experiment_name", "manga_cosine_recommender"),
            ),
        ),
        recommendation=RecommendationSettings(
            default_top_n=int(recommendation.get("default_top_n", 5)),
        ),
        evaluation=EvaluationSettings(
            min_user_interactions=int(evaluation.get("min_user_interactions", 5)),
            test_fraction=int(evaluation.get("test_fraction", 20)),
            k=int(evaluation.get("k", 10)),
            random_seed=int(evaluation.get("random_seed", 42)),
        ),
    )


settings = get_settings()
