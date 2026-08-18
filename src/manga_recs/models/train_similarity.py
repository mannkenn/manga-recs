"""Train the content-based similarity model over manga feature vectors."""

from __future__ import annotations

import logging
import time

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

logger = logging.getLogger(__name__)

SIM_PATH = MODELS_DIR / COSINE_SIM_FILENAME


def compute_cosine_similarity(df: pd.DataFrame) -> pd.DataFrame:
    """Return an item-by-item cosine similarity matrix indexed by manga id."""
    X = df.drop(columns=["id"])

    sim_matrix = cosine_similarity(X.values)
    np.fill_diagonal(sim_matrix, 0)  # An item is never its own recommendation.

    return pd.DataFrame(sim_matrix, index=df["id"], columns=df["id"])


def train(partition: str | None = None) -> str:
    """Fit the similarity matrix and publish it to the object store."""
    mlflow.set_experiment(settings.mlflow.experiment_name)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    feature_path = get_file(MANGA_FEATURES_PARQUET, status=FEATURES_STATUS, partition=partition)

    with mlflow.start_run():
        X = pd.read_parquet(feature_path)

        mlflow.log_param("model_type", "cosine_similarity")
        mlflow.log_param("feature_store", "s3_parquet")
        mlflow.log_param("partition", partition or "latest")
        mlflow.log_metric("num_items", X.shape[0])
        mlflow.log_metric("num_features", X.shape[1] - 1)

        logger.info("Computing similarity over %d items x %d features", X.shape[0], X.shape[1] - 1)
        started = time.perf_counter()
        sim_matrix = compute_cosine_similarity(X)
        train_seconds = time.perf_counter() - started
        mlflow.log_metric("train_seconds", train_seconds)

        joblib.dump(sim_matrix, SIM_PATH)
        mlflow.log_artifact(str(SIM_PATH))

        uri = put_file(SIM_PATH, COSINE_SIM_FILENAME, MODELS_STATUS, partition=partition)
        mlflow.log_param("model_uri", uri)

    logger.info("Trained in %.1fs and published %s", train_seconds, uri)
    return uri


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train()
