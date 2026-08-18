"""Minimal data quality gates run between pipeline stages.

The point is to fail loudly at the stage that produced bad data, rather than
letting an empty or malformed frame flow downstream and surface as a confusing
error during training or serving.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


class DataQualityError(ValueError):
    """Raised when a dataset fails its quality checks."""


def check_frame(
    df: pd.DataFrame,
    name: str,
    required_columns: tuple[str, ...] = (),
    min_rows: int = 1,
    non_null_columns: tuple[str, ...] = (),
    unique_columns: tuple[str, ...] = (),
) -> pd.DataFrame:
    """Assert basic invariants on ``df`` and return it unchanged."""
    problems: list[str] = []

    if len(df) < min_rows:
        problems.append(f"expected at least {min_rows} rows, got {len(df)}")

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        problems.append(f"missing required columns: {missing}")

    for col in non_null_columns:
        if col in df.columns:
            null_count = int(df[col].isna().sum())
            if null_count:
                problems.append(f"column '{col}' has {null_count} null values")

    for col in unique_columns:
        if col in df.columns:
            duplicates = int(df[col].duplicated().sum())
            if duplicates:
                problems.append(f"column '{col}' has {duplicates} duplicate values")

    if problems:
        raise DataQualityError(f"Data quality check failed for {name}: " + "; ".join(problems))

    logger.info("Quality check passed for %s (%d rows, %d columns)", name, len(df), df.shape[1])
    return df
