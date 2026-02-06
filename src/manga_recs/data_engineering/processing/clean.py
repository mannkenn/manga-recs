import numpy as np
import pandas as pd


def coerce_int_series(s: pd.Series) -> pd.Series:
    """
    Convert a series to numeric, round, and return pandas nullable Int64.
    This avoids crashing on NaNs (regular int can't hold NaN).
    """
    s_num = pd.to_numeric(s, errors="coerce")
    return s_num.round().astype("Int64")


def log_transform(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """
    Changes columns in place: adds log1p versions of the specified columns. Useful for things like popularity that are skewed.
    """
    out = df.copy()
    for col in cols:
        # ensure numeric; log1p works with 0+; negatives become NaN
        x = pd.to_numeric(out[col], errors="coerce")
        x = x.where(x >= 0)  # optional safety: drop negatives
        out[f"{col}_log"] = np.log1p(x)
    return out


def extract_year_month(df: pd.DataFrame, src_col: str, prefix: str) -> pd.DataFrame:
    """
    Extract year/month from a column that contains dicts like {"year": 2001, "month": 7}.
    Adds columns: <prefix>_year and <prefix>_month as nullable Int64.
    """
    out = df.copy()

    def get_key(d, key):
        return d.get(key) if isinstance(d, dict) else pd.NA

    out[f"{prefix}_year"] = out[src_col].apply(lambda d: get_key(d, "year")).astype("Int64")
    out[f"{prefix}_month"] = out[src_col].apply(lambda d: get_key(d, "month")).astype("Int64")
    return out


def id_quality(df: pd.DataFrame, id_col: str = "id") -> dict[str, int]:
    """
    Return counts of missing IDs and duplicated IDs.
    """
    missing = int(df[id_col].isna().sum())
    dupes = int(df[id_col].duplicated().sum())
    return {"missing_ids": missing, "duplicate_ids": dupes}

def title_to_string(title_dict) :
    """
    Drop the language in title, e.g. english: monster -> monster
    """
    if isinstance(title_dict, dict):
        return title_dict.get("english") or title_dict.get("native") or pd.NA
    if isinstance(title_dict, str):
        return title_dict.strip() or pd.NA
    return pd.NA


def extract_tag_categories(tags_obj):
    """
    Drop evertyhing but the relevant tags. Also checks to make sure idempotent, e.g. running more than once doesnt change
    """
    if tags_obj is None or tags_obj is pd.NA:
        return pd.NA

    # already cleaned: list of strings
    if isinstance(tags_obj, list) and all(isinstance(x, str) for x in tags_obj):
        seen = set()
        out = []
        for x in tags_obj:
            x = x.strip()
            if x and x not in seen:
                seen.add(x)
                out.append(x)
        return out if out else pd.NA

    # raw: list of dicts
    if not isinstance(tags_obj, list):
        return pd.NA

    seen = set()
    cats = []
    for item in tags_obj:
        if isinstance(item, dict):
            cat = item.get("category")
            if isinstance(cat, str):
                cat = cat.strip()
                if cat and cat not in seen:
                    seen.add(cat)
                    cats.append(cat)

    return cats if cats else pd.NA

# main function, clean metadata using helpers above

def clean_manga_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply your notebook cleaning steps to manga metadata.
    Returns a new DataFrame (does not mutate input).
    """
    out = df.copy()

    # chapters/volumes -> nullable ints (safe with NaNs)
    out["chapters"] = coerce_int_series(out.get("chapters"))
    out["volumes"]  = coerce_int_series(out.get("volumes"))

    # go dict > relevant info for title and tags, i.e. extract title and category 
    out["title"] = out["title"].apply(title_to_string)
    out["tags"] = out["tags"].apply(extract_tag_categories)

    # log transforms for skew
    out = log_transform(out, ["popularity", "favourites"])

    # extract dates
    if "startDate" in out.columns:
        out = extract_year_month(out, "startDate", "start")
    else:
        out["start_year"] = pd.Series(pd.NA, index=out.index, dtype="Int64")
        out["start_month"] = pd.Series(pd.NA, index=out.index, dtype="Int64")

    if "endDate" in out.columns:
        out = extract_year_month(out, "endDate", "end")
    else:
        out["end_year"] = pd.Series(pd.NA, index=out.index, dtype="Int64")
        out["end_month"] = pd.Series(pd.NA, index=out.index, dtype="Int64")

    # checkw heter manga is finished or not 
    out["is_finished"] = out["end_year"].notna()

    return out


def describe_outliers(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """
    Provides some metrics to help identify outliers
    """
    return df[cols].describe(percentiles=[0.01, 0.05, 0.95, 0.99])