import pandas as pd
import joblib
import mlflow
import numpy as np

from manga_recs.common.constants import (
    COSINE_SIM_FILENAME,
    FEATURES_STATUS,
    MANGA_FEATURES_PARQUET,
    MODELS_STATUS,
)
from manga_recs.common.paths import MODELS_DIR
from manga_recs.common.settings import settings
from manga_recs.data.load.s3 import s3_dump, s3_load
from sklearn.metrics.pairwise import cosine_similarity

# paths
FEATURE_PATH = s3_load(MANGA_FEATURES_PARQUET, bucket=settings.s3.bucket, status=FEATURES_STATUS)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
SIM_PATH = MODELS_DIR / COSINE_SIM_FILENAME


def compute_cosine_similarity(df):

    X = df.copy()
    X = X.drop(columns=['id'])

    sim_matrix = cosine_similarity(X.values)
    np.fill_diagonal(sim_matrix, 0)  # Exclude self-similarity

    cos_sim_df = pd.DataFrame(sim_matrix, index=df['id'], columns=df['id'])

    return cos_sim_df


def train():

    with mlflow.start_run():
        
        mlflow.set_experiment(settings.mlflow.experiment_name)
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
        
        s3_dump(str(SIM_PATH), COSINE_SIM_FILENAME, bucket=settings.s3.bucket, status=MODELS_STATUS)
        print("Uploaded similarity matrix to S3.")

        print("Training complete and logged!")

if __name__ == "__main__":
    train()


