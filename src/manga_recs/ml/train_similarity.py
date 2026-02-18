import pandas as pd
import joblib
import mlflow
import os
import numpy as np

from manga_recs.data_engineering.load.s3 import s3_dump, s3_load
from sklearn.metrics.pairwise import cosine_similarity

# paths
FEATURE_PATH = s3_load("manga_features.parquet", bucket="manga-recs", status="features")
MODEL_DIR = "artifacts/models"
os.makedirs(MODEL_DIR, exist_ok=True)
SIM_PATH = os.path.join(MODEL_DIR, "cosine_sim.pkl")


def compute_cosine_similarity(df):

    X = df.copy()
    X = X.drop(columns=['id'])

    sim_matrix = cosine_similarity(X.values)
    np.fill_diagonal(sim_matrix, 0)  # Exclude self-similarity

    cos_sim_df = pd.DataFrame(sim_matrix, index=df['id'], columns=df['id'])

    return cos_sim_df


def train():

    with mlflow.start_run():
        
        mlflow.set_experiment("manga_cosine_recommender")
        mlflow.log_param("model_type", "cosine_similarity")
        mlflow.log_param("feature_store", "s3_parquet")
        
        print("Loading features from S3")
        X = pd.read_parquet(FEATURE_PATH)

        mlflow.log_metric("num_items", X.shape[0])
        mlflow.log_metric("num_features", X.shape[1])

        print("Computing similarity matrix...")

        sim_matrix = compute_cosine_similarity(X)

        joblib.dump(sim_matrix, SIM_PATH)

        mlflow.log_artifact(SIM_PATH)
        
        s3_dump(SIM_PATH, "cosine_sim.pkl", bucket="manga-recs", status="models")
        print("Uploaded similarity matrix to S3.")

        print("Training complete and logged!")

if __name__ == "__main__":
    train()


