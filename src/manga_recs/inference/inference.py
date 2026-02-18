import pandas as pd
import joblib
from pathlib import Path
from manga_recs.data_engineering.load.s3 import s3_load

# Paths
MODEL_PATH = s3_load("cosine_sim.pkl", bucket="manga-recs", status="models")
METADATA_PATH = s3_load("cleaned_manga_metadata.parquet", bucket="manga-recs", status="cleaned")

# Load similarity matrix + metadata
SIM_MATRIX = joblib.load(MODEL_PATH)
METADATA = pd.read_parquet(METADATA_PATH)

def get_top_n_recommendations(manga_id, top_n=5):

    # Get row index for the given manga_id
    similarities = SIM_MATRIX.loc[manga_id]  # Ensure manga_id is valid

    # Get top N most similar
    top_similarities = similarities.sort_values(ascending=False).head(top_n)

    # Get the corresponding metadata for these manga IDs
    recs = METADATA[METADATA['id'].isin(top_similarities.index)][['id', 'title', 'description', 'tags']]

    # Merge similarity scores into metadata
    recs = recs.set_index('id')  # set 'id' as index to match top_similarities
    recs = recs.join(top_similarities.rename("similarity"))  # add similarity column
    recs['similarity'] = recs['similarity'].round(2)  # round similarity for better readability

    return recs.reset_index().to_dict(orient='records')

# test
if __name__ == "__main__":
    recommendations = get_top_n_recommendations(manga_id=30002, top_n=5)
    print(recommendations)
