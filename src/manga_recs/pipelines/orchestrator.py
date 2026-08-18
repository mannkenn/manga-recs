"""Sequential runner for the ingest -> clean -> features pipeline."""

from __future__ import annotations

import logging
import time
from datetime import date

from manga_recs.data.cleaning import clean_data
from manga_recs.data.features import build_features
from manga_recs.data.ingestion import ingest_data
from manga_recs.data.load import PARTITION_FORMAT, describe_backend
from manga_recs.observability.tracing import configure_tracing, span

logger = logging.getLogger(__name__)


def run_pipeline(partition: str | None = None) -> dict[str, dict[str, str]]:
    """Run every data stage against a single partition.

    Pinning one partition for the whole run keeps stages consistent: cleaning
    reads exactly what this run ingested, rather than whichever partition
    happens to be newest.
    """
    configure_tracing()
    partition = partition or date.today().strftime(PARTITION_FORMAT)
    logger.info("Running pipeline for partition %s against %s", partition, describe_backend())

    results: dict[str, dict[str, str]] = {}
    # One span per stage under a single pipeline span, so a slow run shows which
    # stage owns the time. Ingest is network-bound and the others are not, which
    # is exactly the distinction a trace makes obvious and a total duration hides.
    with span("pipeline.run", **{"manga_recs.partition": partition}):
        for name, stage in (
            ("ingest", ingest_data),
            ("clean", clean_data),
            ("features", build_features),
        ):
            started = time.perf_counter()
            with span(f"pipeline.{name}", **{"manga_recs.partition": partition}):
                results[name] = stage(partition=partition)
            elapsed = time.perf_counter() - started
            logger.info(
                "Stage '%s' finished in %.1fs",
                name,
                elapsed,
                extra={
                    "event": "pipeline.stage_complete",
                    "stage": name,
                    "partition": partition,
                    "duration_s": round(elapsed, 2),
                },
            )

    return results
