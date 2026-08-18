from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import MultiLabelBinarizer, StandardScaler


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


def create_user_features(data):
    # Accept either a path-like object or a DataFrame
    if isinstance(data, (str, Path)):
        df = pd.read_parquet(data)
    elif isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        df = pd.read_parquet(data)

    df = df.drop(
        columns=["createdAt", "progress"]
    )  # Drop createdAt since it's not useful for modeling, and progress since it has many nulls
    # Map status to numerical representation
    status_map = {"COMPLETED": 1.0, "CURRENT": 0.8, "PAUSED": 0.5, "PLANNING": 0.4, "DROPPED": 0.1}

    df["status"] = df["status"].map(status_map)

    df["interaction_strength"] = df["status"] * (df["score"] / 10)

    return df
