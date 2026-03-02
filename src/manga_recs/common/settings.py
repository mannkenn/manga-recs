from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


@dataclass(frozen=True)
class PathsSettings:
    data_dir: Path
    artifacts_dir: Path


@dataclass(frozen=True)
class S3Settings:
    bucket: str


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


@dataclass(frozen=True)
class MlflowSettings:
    experiment_name: str


@dataclass(frozen=True)
class RecommendationSettings:
    default_top_n: int


@dataclass(frozen=True)
class Settings:
    paths: PathsSettings
    s3: S3Settings
    api: ApiSettings
    ingestion: IngestionSettings
    mlflow: MlflowSettings
    recommendation: RecommendationSettings


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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    base_path = Path("configs/base.toml")
    if not base_path.exists():
        raise FileNotFoundError(f"Missing required config file: {base_path}")

    base_config = _load_toml(base_path)

    override_path = os.getenv("MANGA_RECS_CONFIG")
    if override_path:
        override_file = Path(override_path)
    else:
        override_file = Path("configs/local.toml")

    override_config: dict[str, Any] = {}
    if override_file.exists():
        override_config = _load_toml(override_file)

    config = _deep_merge(base_config, override_config)

    paths = config.get("paths", {})
    s3 = config.get("s3", {})
    api = config.get("api", {})
    ingestion = config.get("ingestion", {})
    mlflow = config.get("mlflow", {})
    recommendation = config.get("recommendation", {})

    return Settings(
        paths=PathsSettings(
            data_dir=Path(paths.get("data_dir", "data")),
            artifacts_dir=Path(paths.get("artifacts_dir", "artifacts")),
        ),
        s3=S3Settings(
            bucket=os.getenv("MANGA_RECS_S3_BUCKET", s3.get("bucket", "manga-recs")),
        ),
        api=ApiSettings(
            graphql_url=os.getenv("MANGA_RECS_GRAPHQL_URL", api.get("graphql_url", "https://graphql.anilist.co")),
            fuzzy_match_threshold=int(api.get("fuzzy_match_threshold", 70)),
        ),
        ingestion=IngestionSettings(
            rate_limit=int(ingestion.get("rate_limit", 10)),
            popularity_min=int(ingestion.get("popularity_min", 10000)),
            user_start_id=int(ingestion.get("user_start_id", 1001)),
            user_end_id=int(ingestion.get("user_end_id", 1500)),
            user_max_pages=int(ingestion.get("user_max_pages", 200)),
            user_per_page=int(ingestion.get("user_per_page", 50)),
        ),
        mlflow=MlflowSettings(
            experiment_name=os.getenv("MANGA_RECS_MLFLOW_EXPERIMENT", mlflow.get("experiment_name", "manga_cosine_recommender")),
        ),
        recommendation=RecommendationSettings(
            default_top_n=int(recommendation.get("default_top_n", 5)),
        ),
    )


settings = get_settings()