from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import MultiLabelBinarizer
import numpy as np
import pandas as pd 


def parse_release_year(start_date):
    """Extract release year from startDate"""
    if pd.notna(start_date):
        return start_date.year
    return np.nan

def one_hot_encode_tags(tags):
    """One-hot encode the list of tags"""
    if isinstance(tags, list):
        mlb = MultiLabelBinarizer()
        return mlb.fit_transform([tags])[0]
    return np.zeros(0)  # Return empty array if no tags


def create_manga_features(data):

    df = pd.read_parquet(data)

    # Extract release year
    df['release_year'] = df['startDate'].apply(parse_release_year)