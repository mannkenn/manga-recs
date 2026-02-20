from sklearn.preprocessing import StandardScaler
import numpy as np
import pandas as pd 
import joblib
from pathlib import Path


def parse_release_year(start_date):
    """Extract release year from startDate"""
    if pd.notna(start_date):
        return start_date.year
    return np.nan

def one_hot_encode_column(df, col, weight_top=None):
    """One-hot encode a column of list-like values.

    If `weight_top` is provided (e.g. [3, 2]) the function will weight the
    first element of each row's list by 3, the second by 2, and all remaining
    elements by 1. This preserves the original ordering of tags within each
    row.
    """
    # Collect all unique classes
    all_values = set()
    for vals in df[col]:
        if vals is None:
            continue
        for v in vals:
            all_values.add(v)

    classes = sorted(all_values)

    # Initialize encoded DataFrame with zeros
    encoded_df = pd.DataFrame(0, index=df.index, columns=classes, dtype=float)

    if weight_top is None:
        # simple binary encoding
        for idx, vals in df[col].items():
            if vals is None:
                continue
            for v in vals:
                encoded_df.at[idx, v] = 1.0
    else:
        # weighted encoding based on position in the list
        for idx, vals in df[col].items():
            if vals is None:
                continue
            for pos, v in enumerate(vals):
                if pos < len(weight_top):
                    weight = float(weight_top[pos])
                else:
                    weight = 1.0
                # If the same tag appears multiple times, keep the max weight
                encoded_df.at[idx, v] = max(encoded_df.at[idx, v], weight)

    return df.join(encoded_df)


def create_manga_features(data, save_dir = 'artifacts/features'):

    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    # Accept either a path-like object or a DataFrame
    if isinstance(data, (str, Path)):
        df = pd.read_parquet(data)
    elif isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        # Fallback: try to read with pandas (will raise a helpful error if unsupported)
        df = pd.read_parquet(data)

    # Drop these for now
    df = df.drop(columns=['title', 'volumes', 'description', 'favourites', 'meanScore'])
    
    # Extract release year
    df['release_year'] = df['startDate'].apply(parse_release_year)
    df = df.drop(columns=['startDate'])

    df = df.dropna()

    # One hot encode tags (weight first tag 3, second tag 2, others 1)
    df_encoded = one_hot_encode_column(df, 'tags', weight_top=[3, 2])
    df_encoded = df_encoded.drop(columns=['tags'])

    # One hot encode genres
    df_encoded = one_hot_encode_column(df_encoded, 'genres')
    df_encoded = df_encoded.drop(columns=['genres'])

    # Log transform
    df_encoded['popularity'] = np.log1p(df_encoded['popularity'])
    df_encoded['chapters'] = np.log1p(df_encoded['chapters'].replace(-1, 0))  # Replace -1 with 0 before log

    # Standardize numerical features
    scaler = StandardScaler()
    num_cols = ['popularity', 'chapters', 'averageScore', 'release_year']
    df_encoded[num_cols] = scaler.fit_transform(df_encoded[num_cols])

    # Save artifacts
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

    # Drop unused columns (assign the result)
    df = df.drop(columns=['priority', 'progress', 'progressVolumes', 'private', 'repeat', 'name'], errors='ignore')
    
    # Map status to numerical representation
    status_map = {
        "COMPLETED": 1.0,
        "CURRENT": 0.8,
        "PAUSED": 0.5,
        "PLANNING": 0.4,
        "DROPPED": 0.1
    }
    
    df['status'] = df['status'].map(status_map)

    df['interaction_strength'] = df['status'] * (df['score'] / 10)

    return df



