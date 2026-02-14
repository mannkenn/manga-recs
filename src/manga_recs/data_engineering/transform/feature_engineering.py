from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import MultiLabelBinarizer
import numpy as np
import pandas as pd 


def parse_release_year(start_date):
    """Extract release year from startDate"""
    if pd.notna(start_date):
        return start_date.year
    return np.nan

def one_hot_encode_column(df, col):
    mlb = MultiLabelBinarizer()
    encoded = mlb.fit_transform(df[col])
    encoded_df = pd.DataFrame(encoded, columns=mlb.classes_, index=df.index)
    return df.join(encoded_df)


def create_manga_features(data):
    df = pd.read_parquet(data)

    # Drop these for now
    df = df.drop(columns=['title', 'volumes', 'description', 'favourites', 'meanScore'])
    
    # Extract release year
    df['release_year'] = df['startDate'].apply(parse_release_year)
    df = df.drop(columns=['startDate'])

    df = df.dropna()

    # One hot encode tags
    df_encoded = one_hot_encode_column(df, 'tags')
    df_encoded = df_encoded.drop(columns=['tags'])

    # One hot encode genres
    df_encoded = one_hot_encode_column(df_encoded, 'genres')
    df_encoded = df_encoded.drop(columns=['genres'])

    # Convert bool to numeric
    df_encoded['isAdult'] = df_encoded['isAdult'].astype(int)

    # Log transform
    df_encoded['popularity'] = np.log1p(df_encoded['popularity'])
    df_encoded['chapters'] = np.log1p(df_encoded['chapters'].replace(-1, 0))  # Replace -1 with 0 before log

    # Standardize numerical features
    scaler = StandardScaler()
    num_cols = ['popularity', 'chapters', 'averageScore', 'release_year']
    df_encoded[num_cols] = scaler.fit_transform(df_encoded[num_cols])

    return df_encoded

def one_hot_encode_simple(df, col):
    """One-hot encode a single-value column using pandas.get_dummies"""
    encoded = pd.get_dummies(df[col], prefix=col)
    return df.join(encoded).drop(columns=[col])

def create_user_features(data):
    df = pd.read_parquet(data)

    df.drop(columns =['priority', 'progressVolumes', 'private', 'repeat', 'name'])
    df_encoded = one_hot_encode_simple(df, 'status')

    