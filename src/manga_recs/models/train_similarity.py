"""Train the content-based similarity model over manga feature vectors."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager

import joblib
import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from manga_recs.common.constants import (
    COSINE_SIM_FILENAME,
    FEATURES_STATUS,
    MANGA_FEATURES_PARQUET,
    MODELS_STATUS,
)
from manga_recs.common.paths import MODELS_DIR
from manga_recs.common.settings import settings
from manga_recs.data.load import get_file, put_file
from manga_recs.observability.tracing import configure_tracing, span

logger = logging.getLogger(__name__)

SIM_PATH = MODELS_DIR / COSINE_SIM_FILENAME


def compute_cosine_similarity(df: pd.DataFrame) -> pd.DataFrame:
    """Return an item-by-item cosine similarity matrix indexed by manga id."""
    X = df.drop(columns=["id"])

    sim_matrix = cosine_similarity(X.values)
    np.fill_diagonal(sim_matrix, 0)  # An item is never its own recommendation.

    return pd.DataFrame(sim_matrix, index=df["id"], columns=df["id"])


@contextmanager
def _tracking_run():
    """Start an MLflow run, degrading to a no-op if tracking is unavailable.

    Experiment tracking is valuable but it is not the job: a broken or
    unreachable tracking backend should not stop a model from being produced and
    published. Failures are logged loudly and training continues.
    """
    try:
        mlflow.set_tracking_uri(settings.mlflow.tracking_uri)
        mlflow.set_experiment(settings.mlflow.experiment_name)
        run = mlflow.start_run()
    except Exception as exc:  # noqa: BLE001 - tracking must never block training
        logger.warning(
            "MLflow tracking unavailable (%s); training without it.",
            exc,
            extra={"event": "mlflow.unavailable"},
        )
        yield False
        return

    try:
        with run:
            yield True
    except Exception:
        raise


def _log_param(enabled: bool, key: str, value) -> None:
    if enabled:
        mlflow.log_param(key, value)


def _log_metric(enabled: bool, key: str, value) -> None:
    if enabled:
        mlflow.log_metric(key, value)


def train(partition: str | None = None) -> str:
    """Fit the similarity matrix and publish it to the object store."""
    configure_tracing()
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    feature_path = get_file(MANGA_FEATURES_PARQUET, status=FEATURES_STATUS, partition=partition)

    with _tracking_run() as tracked, span("train.similarity"):
        X = pd.read_parquet(feature_path)

        _log_param(tracked, "model_type", "cosine_similarity")
        _log_param(tracked, "feature_store", "s3_parquet")
        _log_param(tracked, "partition", partition or "latest")
        _log_param(tracked, "include_authors", settings.features.include_authors)
        _log_param(tracked, "author_min_titles", settings.features.author_min_titles)
        _log_metric(tracked, "num_items", X.shape[0])
        _log_metric(tracked, "num_features", X.shape[1] - 1)

        logger.info("Computing similarity over %d items x %d features", X.shape[0], X.shape[1] - 1)
        started = time.perf_counter()
        sim_matrix = compute_cosine_similarity(X)
        train_seconds = time.perf_counter() - started
        _log_metric(tracked, "train_seconds", train_seconds)

        joblib.dump(sim_matrix, SIM_PATH)
        if tracked:
            mlflow.log_artifact(str(SIM_PATH))

        uri = put_file(SIM_PATH, COSINE_SIM_FILENAME, MODELS_STATUS, partition=partition)
        _log_param(tracked, "model_uri", uri)

    logger.info("Trained in %.1fs and published %s", train_seconds, uri)
    return uri


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train()
