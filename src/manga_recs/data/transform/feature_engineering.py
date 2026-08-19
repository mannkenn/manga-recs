import logging
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import MultiLabelBinarizer, StandardScaler

logger = logging.getLogger(__name__)


def parse_release_year(start_date):
    """Extract release year from startDate"""
    if pd.notna(start_date):
        return start_date.year
    return np.nan


def one_hot_encode_column(df, col, prefix=None, min_frequency=1):
    """One-hot encode a column of label lists.

    ``min_frequency`` drops labels appearing on fewer than that many rows, which
    matters for high-cardinality columns such as authors.

    A label set on exactly one title cannot link two titles - the only vector it
    appears in is the one excluded from its own results - but it is not inert
    either: it enlarges that title's vector norm and so lowers its cosine
    similarity to everything, which demotes obscure titles. Measured on this
    catalogue that effect *improves* top-K metrics, and it does so whether or not
    the labels are the real ones (see scripts/author_ablation.py). Keeping the
    floor configurable rather than tuning it to the metric is deliberate: the
    apparent gain is a property of the encoding, not of the labels.

    ``prefix`` namespaces the generated columns. Without it, a person sharing a
    name with a genre or tag would collide into one column.
    """
    labels = df[col].apply(lambda value: list(value) if _is_listlike(value) else [])

    if min_frequency > 1:
        counts = Counter(label for row in labels for label in row)
        keep = {label for label, count in counts.items() if count >= min_frequency}
        labels = labels.apply(lambda row: [label for label in row if label in keep])

    mlb = MultiLabelBinarizer()
    encoded = mlb.fit_transform(labels)
    columns = [f"{prefix}{name}" for name in mlb.classes_] if prefix else list(mlb.classes_)
    encoded_df = pd.DataFrame(encoded, columns=columns, index=df.index)
    return df.join(encoded_df)


def _is_listlike(value) -> bool:
    return hasattr(value, "__iter__") and not isinstance(value, str)


def create_manga_features(
    data,
    save_dir: str | Path | None = None,
    include_authors: bool = True,
    author_min_titles: int = 2,
):
    """Build the model-ready feature matrix.

    ``save_dir`` defaults to None so this stays a pure transform. It previously
    wrote the scaler and column list into a hardcoded ``artifacts/features/``
    every time it was called, including from tests and from the pipeline, which
    made a transform quietly mutate the working tree. Callers that want the
    fitted scaler persisted now ask for it.

    ``author_min_titles`` defaults to 2 because an author credited on a single
    title cannot create a similarity edge; see one_hot_encode_column.
    """
    # Accept either a path-like object or a DataFrame
    if isinstance(data, (str, Path)):
        df = pd.read_parquet(data)
    elif isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        # Fallback: try to read with pandas (will raise a helpful error if unsupported)
        df = pd.read_parquet(data)

    # Identity/display columns that carry no modelling signal.
    df = df.drop(
        columns=["title", "search_titles", "volumes", "description", "favourites", "meanScore"],
        errors="ignore",
    )

    # Extract release year
    df["release_year"] = df["startDate"].apply(parse_release_year)
    df = df.drop(columns=["startDate"])

    if not include_authors and "authors" in df.columns:
        df = df.drop(columns=["authors"])

    # dropna would treat an empty author list as present, but a genuinely missing
    # numeric field still drops the row, which is the intent.
    df = df.dropna()

    # One hot encode tags
    df_encoded = one_hot_encode_column(df, "tags")
    df_encoded = df_encoded.drop(columns=["tags"])

    # One hot encode genres
    df_encoded = one_hot_encode_column(df_encoded, "genres")
    df_encoded = df_encoded.drop(columns=["genres"])

    # One hot encode authors. Namespaced, because a creator's name could
    # otherwise collide with a tag or genre of the same spelling.
    if include_authors and "authors" in df_encoded.columns:
        df_encoded = one_hot_encode_column(
            df_encoded, "authors", prefix="author:", min_frequency=author_min_titles
        )
        df_encoded = df_encoded.drop(columns=["authors"])

    # Log transform
    df_encoded["popularity"] = np.log1p(df_encoded["popularity"])
    df_encoded["chapters"] = np.log1p(
        df_encoded["chapters"].replace(-1, 0)
    )  # Replace -1 with 0 before log

    # Standardize numerical features
    scaler = StandardScaler()
    num_cols = ["popularity", "chapters", "averageScore", "release_year"]
    df_encoded[num_cols] = scaler.fit_transform(df_encoded[num_cols])

    if save_dir is not None:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(scaler, save_dir / "scaler.pkl")
        joblib.dump(df_encoded.columns.tolist(), save_dir / "feature_columns.pkl")

    return df_encoded


# How strongly each list status implies the user actually valued the title.
# REPEATING is a re-read, which is at least as strong a signal as finishing once.
STATUS_WEIGHTS = {
    "COMPLETED": 1.0,
    "REPEATING": 1.0,
    "CURRENT": 0.8,
    "PAUSED": 0.5,
    "PLANNING": 0.4,
    "DROPPED": 0.1,
}

# AniList uses 0 to mean "not rated", not "rated zero".
UNRATED = 0.0


def create_user_features(data):
    """Reduce raw read lists to a graded (user, item, strength) interaction table.

    ``interaction_strength`` is ``status_weight * score``, on [0, 1]. Three
    details it has to get right, each of which was previously wrong and each of
    which silently destroys the signal rather than raising:

    - A score of 0 on AniList means unrated, not "rated zero". Multiplying by it
      zeroed 61% of all rows, including 2,624 titles users had *completed*, and
      made an unrated favourite indistinguishable from an untouched title.
      Unrated scores are imputed with the median rating instead, which places
      them at the population average rather than the floor.
    - ``score`` is returned in whichever format each user chose - this catalogue
      spans 0-3, 0-5, 0-10 and 0-100 across 272 users - so it is not comparable
      across users until normalised. The query now requests POINT_100; this
      rescales defensively so older partitions do not silently skew.
    - A status missing from the weight table produced NaN, quietly dropping the
      row downstream. REPEATING hit this. Unknown statuses now warn.
    """
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        df = pd.read_parquet(data)

    # createdAt is not predictive and progress is mostly null.
    df = df.drop(columns=[c for c in ("createdAt", "progress") if c in df.columns])

    status = df["status"].astype("string").str.upper()
    unknown = set(status.dropna().unique()) - STATUS_WEIGHTS.keys()
    if unknown:
        logger.warning(
            "Unweighted AniList statuses treated as neutral: %s", ", ".join(sorted(unknown))
        )

    status_weight = status.map(STATUS_WEIGHTS).astype(float)
    # An unrecognised status should not delete the interaction.
    status_weight = status_weight.fillna(min(STATUS_WEIGHTS.values()))

    score = _normalize_scores(df["score"])

    df["status"] = status_weight
    df["score"] = score
    df["interaction_strength"] = (status_weight * score).clip(0.0, 1.0)

    return df


def _normalize_scores(raw: pd.Series) -> pd.Series:
    """Put scores on [0, 1], imputing unrated entries with the median rating.

    The scale is inferred from the observed maximum rather than assumed, so a
    partition ingested before the query pinned POINT_100 still normalises
    correctly instead of collapsing every 0-10 rating to near zero.
    """
    score = pd.to_numeric(raw, errors="coerce")
    rated = score[score.notna() & (score > UNRATED)]

    if rated.empty:
        # No ratings anywhere, so the rating carries no information and the
        # status weight is the entire signal. Returning zeros here instead would
        # wipe out every interaction in the partition.
        return pd.Series(1.0, index=raw.index)

    upper = float(rated.max())
    scale = next((bound for bound in (3.0, 5.0, 10.0, 100.0) if upper <= bound), 100.0)
    if scale != 100.0:
        logger.warning(
            "Scores top out at %g, so they are not on AniList's POINT_100 scale; "
            "normalising by %g. Re-ingest to get server-side normalisation.",
            upper,
            scale,
        )

    normalized = (score / scale).where(score > UNRATED)
    median = float(normalized.median())
    logger.info(
        "Imputed %d unrated scores with the median rating (%.2f)",
        int(normalized.isna().sum()),
        median,
    )
    return normalized.fillna(median)
