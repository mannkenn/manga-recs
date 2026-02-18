import pandas as pd
import joblib
from pathlib import Path
from manga_recs.data_engineering.load.s3 import s3_load

# Paths
MODEL_PATH = s3_load("cosine_sim.pkl", bucket="manga-recs", status="models")
METADATA_PATH = s3_load("cleaned_manga_metadata.parquet", bucket="manga-recs", status="cleaned")


# Load similarity matrix
def load_model():
    return joblib.load(MODEL_PATH)

# Load cleaned metadata
def load_metadata():
    return pd.read_parquet(METADATA_PATH)

def get_top_n_recommendations(manga_id, top_n=5):
    sim_matrix = load_model()
    metadata = load_metadata()

    # Map manga_id to row index in X using metadata
    sim_matrix.iloc[manga_id]  # Ensure manga_id is valid

    
   
    
    return recommendations

# test
if __name__ == "__main__":
    recommendations = get_top_n_recommendations(manga_id=1, top_n=5)
    print(recommendations)
