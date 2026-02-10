from manga_recs.data_engineering.utils import load_json, save_json
from manga_recs.data_engineering.load import s3_dump
import pandas as pd
from pathlib import Path
from typing import Any, Dict, List

def extract_english_title(title):
    if isinstance(title, dict):
        # Prefer 'english' then fallback to other common keys
        extracted =  title.get('english') or title.get('romaji') or title.get('native') or None
        if extracted:
            return extracted.lower()
        return None
    elif isinstance(title, str):
            return title.lower()
    return None

def extract_tag_names(tags):
    if isinstance(tags, list) and tags:
        names = [t.get('name') for t in tags if isinstance(t, dict) and t.get('name')]
        if names:
            return [n.lower() for n in names]

    # If tags is a single string, return it as a single-item list (lowercased)
    if isinstance(tags, str):
        return [tags.lower()]

    # Return empty list when no tags are available
    return []

def has_end_date(end_date):
    """Check if endDate contains None values"""
    if isinstance(end_date, dict):
        # If any value in the dict is None, return 0, otherwise 1
        return int(not any(v is None for v in end_date.values()))
    return 0  # If it's not a dict or is None itself

def parse_date_to_datetime(date_dict):
    """Convert date dict with month and year to datetime"""
    if isinstance(date_dict, dict) and date_dict.get('month') and date_dict.get('year'):
        try:
            return pd.to_datetime(f"{int(date_dict['year'])}-{int(date_dict['month'])}-01")
        except:
            return pd.NaT
    return pd.NaT

def clean_manga_metadata(data: List[Dict]) -> pd.DataFrame:

    """Clean manga metadata."""
    df = pd.DataFrame(data)
    # Extract English title, tag names, and end date presence, and convert dates to datetime
    df['title'] = df['title'].apply(extract_english_title)
    df['tags'] = df['tags'].apply(extract_tag_names)
    df['has_end_date'] = df['endDate'].apply(has_end_date)
    df['startDate'] = df['startDate'].apply(parse_date_to_datetime)
    df = df.drop(columns=['endDate'])
    
    return df

def clean_user_readdata(data: List[Dict]) -> pd.DataFrame:
    """Clean user read data."""
    df = pd.DataFrame(data)
    df['name'] = df['user'].apply(lambda x: x.get('name') if isinstance(x, dict) else None)
    df = df.drop(columns=['notes'])

    return df