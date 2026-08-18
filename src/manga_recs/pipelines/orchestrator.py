"""Sequential runner for the ingest -> clean -> features pipeline."""

from __future__ import annotations

import logging
import time
from datetime import date

from manga_recs.data.cleaning import clean_data
from manga_recs.data.features import build_features
from manga_recs.data.ingestion import ingest_data
from manga_recs.data.load import PARTITION_FORMAT, describe_backend

logger = logging.getLogger(__name__)


def run_pipeline(partition: str | None = None) -> dict[str, dict[str, str]]:
    """Run every data stage against a single partition.

    Pinning one partition for the whole run keeps stages consistent: cleaning
    reads exactly what this run ingested, rather than whichever partition
    happens to be newest.
    """
    partition = partition or date.today().strftime(PARTITION_FORMAT)
    logger.info("Running pipeline for partition %s against %s", partition, describe_backend())

    results: dict[str, dict[str, str]] = {}
    for name, stage in (
        ("ingest", ingest_data),
        ("clean", clean_data),
        ("features", build_features),
    ):
        started = time.perf_counter()
        results[name] = stage(partition=partition)
        logger.info("Stage '%s' finished in %.1fs", name, time.perf_counter() - started)

    return results
