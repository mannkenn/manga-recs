"""Airflow DAG for the manga-recs retraining pipeline.

Each stage is a separate task so a failure is isolated and retryable without
re-running the expensive AniList ingestion. Every task in a given DAG run
operates on the same partition, derived from the logical date, which keeps runs
idempotent: re-running a date overwrites exactly that partition and nothing else.
"""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.decorators import dag, task
from airflow.models import Variable

DEFAULT_ARGS = {
    "owner": "manga-recs",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
}


@dag(
    dag_id="manga_recs_refresh",
    description="Ingest AniList data, rebuild features, retrain and evaluate the recommender",
    schedule="0 6 * * 1",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["manga-recs", "ml"],
)
def manga_recs_refresh():
    @task
    def resolve_partition(**context) -> str:
        """Pin the whole run to one date partition."""
        return context["logical_date"].strftime("%Y-%m-%d")

    @task
    def ingest(partition: str) -> str:
        from manga_recs.data.ingestion import ingest_data

        ingest_data(partition=partition)
        return partition

    @task
    def clean(partition: str) -> str:
        from manga_recs.data.cleaning import clean_data

        clean_data(partition=partition)
        return partition

    @task
    def features(partition: str) -> str:
        from manga_recs.data.features import build_features

        build_features(partition=partition)
        return partition

    @task
    def train(partition: str) -> str:
        from manga_recs.models.train_similarity import train as train_model

        train_model(partition=partition)
        return partition

    @task
    def evaluate(partition: str) -> dict:
        """Score the new model and refuse to promote a regression."""
        from manga_recs.models.evaluate import format_report, run_evaluation

        metrics = run_evaluation(partition=partition)
        content = next(m for m in metrics if m.strategy == "content")
        popularity = next(m for m in metrics if m.strategy == "popularity")

        print(format_report(metrics))

        floor = float(Variable.get("manga_recs_min_recall", default_var=0.0))
        if content.recall_at_k < floor:
            raise ValueError(
                f"recall@{content.k}={content.recall_at_k:.4f} is below the "
                f"configured floor of {floor:.4f}; not promoting this model."
            )
        if content.recall_at_k <= popularity.recall_at_k:
            raise ValueError(
                f"Content model (recall@{content.k}={content.recall_at_k:.4f}) did not beat "
                f"the popularity baseline ({popularity.recall_at_k:.4f})."
            )

        return {"partition": partition, "recall_at_k": content.recall_at_k}

    partition = resolve_partition()
    evaluate(train(features(clean(ingest(partition)))))


manga_recs_refresh()
