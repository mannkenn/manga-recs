"""Offline evaluation of the recommender against real user read histories.

The model itself is content-based: it only ever sees item metadata. The user
read lists are therefore genuinely held-out signal, which makes them a fair
way to ask "do items this model calls similar actually get read by the same
people?"

Protocol: for each user with enough positive interactions, hold out a random
fraction of their items, score every catalogue item by its maximum similarity
to the user's remaining items, and measure how much of the held-out set the
top-K recommendations recover. A popularity ranker and a random ranker run
through the identical harness so the numbers have context.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Minimum graded interaction strength that counts as a positive.
#
# Strength is status_weight * normalised_score (see create_user_features), so
# 0.5 admits a completed or currently-reading title at an average-or-better
# rating and excludes planning, dropped, and titles the user finished but rated
# poorly. It replaces a status allowlist OR'd with `score >= 7.0`, which was
# wrong twice over: AniList scores are 0-100, so 7.0 admitted anything rated at
# all, including 104 titles users had explicitly dropped.
POSITIVE_STRENGTH_THRESHOLD = 0.5


@dataclass(frozen=True)
class Metrics:
    strategy: str
    k: int
    users_evaluated: int
    recall_at_k: float
    precision_at_k: float
    ndcg_at_k: float
    catalog_coverage: float

    def as_mlflow_metrics(self) -> dict[str, float]:
        prefix = self.strategy
        return {
            f"{prefix}_recall_at_{self.k}": self.recall_at_k,
            f"{prefix}_precision_at_{self.k}": self.precision_at_k,
            f"{prefix}_ndcg_at_{self.k}": self.ndcg_at_k,
            f"{prefix}_catalog_coverage": self.catalog_coverage,
        }


def build_positive_interactions(user_df: pd.DataFrame) -> pd.DataFrame:
    """Reduce read lists to the (userId, mediaId) pairs we treat as positive.

    Relevance is defined in exactly one place, ``create_user_features``, and this
    thresholds its output. Accepts either the cleaned read lists or the already
    featurised frame, so the evaluation can consume the published
    user_features.parquet rather than reimplementing the definition and drifting
    from it - which is precisely what had happened.
    """
    from manga_recs.data.transform import create_user_features

    df = user_df if "interaction_strength" in user_df.columns else create_user_features(user_df)

    is_positive = df["interaction_strength"] >= POSITIVE_STRENGTH_THRESHOLD
    positives = df.loc[is_positive.fillna(False), ["userId", "mediaId"]].drop_duplicates()

    logger.info("Kept %d positive interactions out of %d total", len(positives), len(df))
    return positives


def split_holdout(
    interactions: pd.DataFrame,
    catalog: set[int],
    min_interactions: int,
    test_fraction: int,
    seed: int,
) -> dict[int, tuple[list[int], list[int]]]:
    """Split each qualifying user's items into (train, test) lists."""
    rng = np.random.default_rng(seed)
    splits: dict[int, tuple[list[int], list[int]]] = {}

    in_catalog = interactions[interactions["mediaId"].isin(catalog)]
    for user_id, group in in_catalog.groupby("userId"):
        items = group["mediaId"].unique()
        if len(items) < min_interactions:
            continue

        n_test = max(1, int(round(len(items) * test_fraction / 100)))
        if n_test >= len(items):
            continue

        shuffled = rng.permutation(items)
        splits[int(user_id)] = (
            [int(i) for i in shuffled[n_test:]],
            [int(i) for i in shuffled[:n_test]],
        )

    logger.info("Built holdout splits for %d users", len(splits))
    return splits


def _ndcg(recommended: np.ndarray, relevant: set[int], k: int) -> float:
    gains = np.array([1.0 if item in relevant else 0.0 for item in recommended[:k]])
    discounts = 1.0 / np.log2(np.arange(2, len(gains) + 2))
    dcg = float((gains * discounts).sum())

    ideal_hits = min(len(relevant), k)
    if ideal_hits == 0:
        return 0.0
    idcg = float((1.0 / np.log2(np.arange(2, ideal_hits + 2))).sum())
    return dcg / idcg if idcg else 0.0


def _score_metrics(
    strategy: str,
    k: int,
    per_user_recommendations: dict[int, np.ndarray],
    splits: dict[int, tuple[list[int], list[int]]],
    catalog_size: int,
) -> Metrics:
    recalls: list[float] = []
    precisions: list[float] = []
    ndcgs: list[float] = []
    recommended_items: set[int] = set()

    for user_id, recommended in per_user_recommendations.items():
        relevant = set(splits[user_id][1])
        hits = sum(1 for item in recommended[:k] if item in relevant)

        recalls.append(hits / len(relevant))
        precisions.append(hits / k)
        ndcgs.append(_ndcg(recommended, relevant, k))
        recommended_items.update(int(i) for i in recommended[:k])

    return Metrics(
        strategy=strategy,
        k=k,
        users_evaluated=len(per_user_recommendations),
        recall_at_k=float(np.mean(recalls)) if recalls else 0.0,
        precision_at_k=float(np.mean(precisions)) if precisions else 0.0,
        ndcg_at_k=float(np.mean(ndcgs)) if ndcgs else 0.0,
        catalog_coverage=len(recommended_items) / catalog_size if catalog_size else 0.0,
    )


def evaluate_all(
    sim_matrix: pd.DataFrame,
    user_df: pd.DataFrame,
    metadata: pd.DataFrame,
    k: int = 10,
    min_interactions: int = 5,
    test_fraction: int = 20,
    seed: int = 42,
) -> list[Metrics]:
    """Run the content model plus both baselines through the same harness."""
    item_ids = sim_matrix.index.to_numpy()
    catalog = {int(i) for i in item_ids}
    position = {int(item): idx for idx, item in enumerate(item_ids)}
    similarity = sim_matrix.to_numpy(dtype=np.float32)

    interactions = build_positive_interactions(user_df)
    splits = split_holdout(interactions, catalog, min_interactions, test_fraction, seed)
    if not splits:
        raise ValueError(
            "No users met the evaluation criteria. Lower evaluation.min_user_interactions "
            "or ingest a wider range of user ids."
        )

    popularity_order = (
        metadata.set_index("id")["popularity"]
        .reindex(item_ids)
        .fillna(0)
        .to_numpy()
        .argsort()[::-1]
    )
    rng = np.random.default_rng(seed)

    content: dict[int, np.ndarray] = {}
    popular: dict[int, np.ndarray] = {}
    random_recs: dict[int, np.ndarray] = {}

    for user_id, (train_items, _) in splits.items():
        train_positions = [position[i] for i in train_items]

        # Score each candidate by its strongest link to anything the user read.
        scores = similarity[train_positions].max(axis=0)
        scores[train_positions] = -np.inf
        top = np.argpartition(-scores, min(k, len(scores) - 1))[:k]
        content[user_id] = item_ids[top[np.argsort(-scores[top])]]

        seen = set(train_positions)
        popular[user_id] = item_ids[[p for p in popularity_order if p not in seen][:k]]
        random_recs[user_id] = item_ids[
            rng.choice(
                [p for p in range(len(item_ids)) if p not in seen],
                size=min(k, len(item_ids) - len(seen)),
                replace=False,
            )
        ]

    return [
        _score_metrics("content", k, content, splits, len(catalog)),
        _score_metrics("popularity", k, popular, splits, len(catalog)),
        _score_metrics("random", k, random_recs, splits, len(catalog)),
    ]


def metrics_to_json(metrics: list[Metrics]) -> str:
    return json.dumps([asdict(m) for m in metrics], indent=2)


def format_report(metrics: list[Metrics]) -> str:
    """Render a compact comparison table for logs and the README."""
    k = metrics[0].k if metrics else 0
    header = (
        f"{'strategy':<12}{'recall@' + str(k):>12}{'precision@' + str(k):>14}"
        f"{'ndcg@' + str(k):>12}{'coverage':>11}"
    )
    lines = [header, "-" * len(header)]
    for m in metrics:
        lines.append(
            f"{m.strategy:<12}{m.recall_at_k:>12.4f}{m.precision_at_k:>14.4f}"
            f"{m.ndcg_at_k:>12.4f}{m.catalog_coverage:>11.4f}"
        )
    if metrics:
        lines.append(f"\nUsers evaluated: {metrics[0].users_evaluated}")
    return "\n".join(lines)


def run_evaluation(partition: str | None = None) -> list[Metrics]:
    """Load published artifacts, evaluate them, and record the results."""
    import joblib
    import mlflow

    from manga_recs.common.constants import (
        CLEANED_MANGA_METADATA_PARQUET,
        CLEANED_STATUS,
        CLEANED_USER_READDATA_PARQUET,
        COSINE_SIM_FILENAME,
        EVALUATION_METRICS_JSON,
        FEATURES_STATUS,
        METRICS_STATUS,
        MODELS_STATUS,
        USER_FEATURES_PARQUET,
    )
    from manga_recs.common.paths import MODELS_DIR
    from manga_recs.common.settings import settings
    from manga_recs.data.load import get_file, put_file

    sim_matrix = joblib.load(get_file(COSINE_SIM_FILENAME, MODELS_STATUS, partition=partition))

    # Prefer the published interaction table: it is the artifact the features
    # stage exists to produce, and reading it here means the graded strengths
    # that define relevance are computed once rather than re-derived. Older
    # partitions predate it, so fall back to the cleaned read lists.
    try:
        user_df = pd.read_parquet(
            get_file(USER_FEATURES_PARQUET, FEATURES_STATUS, partition=partition)
        )
    except Exception as exc:  # noqa: BLE001 - any retrieval failure is a fallback
        logger.info("No published user features (%s); deriving them from cleaned data.", exc)
        user_df = pd.read_parquet(
            get_file(CLEANED_USER_READDATA_PARQUET, CLEANED_STATUS, partition=partition)
        )
    metadata = pd.read_parquet(
        get_file(CLEANED_MANGA_METADATA_PARQUET, CLEANED_STATUS, partition=partition)
    )

    metrics = evaluate_all(
        sim_matrix=sim_matrix,
        user_df=user_df,
        metadata=metadata,
        k=settings.evaluation.k,
        min_interactions=settings.evaluation.min_user_interactions,
        test_fraction=settings.evaluation.test_fraction,
        seed=settings.evaluation.random_seed,
    )

    report = format_report(metrics)
    logger.info("Evaluation results:\n%s", report)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = MODELS_DIR / EVALUATION_METRICS_JSON
    metrics_path.write_text(metrics_to_json(metrics), encoding="utf-8")

    # Same reasoning as training: a tracking backend that is missing or in a
    # deprecated mode must not throw away a completed evaluation. The metrics are
    # already written to disk and published below regardless.
    try:
        mlflow.set_tracking_uri(settings.mlflow.tracking_uri)
        mlflow.set_experiment(settings.mlflow.experiment_name)
        with mlflow.start_run(run_name="evaluation"):
            mlflow.log_param("k", settings.evaluation.k)
            mlflow.log_param("test_fraction", settings.evaluation.test_fraction)
            mlflow.log_param("min_user_interactions", settings.evaluation.min_user_interactions)
            mlflow.log_param("include_authors", settings.features.include_authors)
            mlflow.log_metric("users_evaluated", metrics[0].users_evaluated)
            for entry in metrics:
                mlflow.log_metrics(entry.as_mlflow_metrics())
            mlflow.log_artifact(str(metrics_path))
    except Exception as exc:  # noqa: BLE001 - never lose results to tracking
        logger.warning(
            "MLflow tracking unavailable (%s); metrics were still written and published.",
            exc,
            extra={"event": "mlflow.unavailable"},
        )

    put_file(metrics_path, EVALUATION_METRICS_JSON, METRICS_STATUS, partition=partition)
    return metrics
