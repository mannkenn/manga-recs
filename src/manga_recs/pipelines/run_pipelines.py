from .run_ingestion import ingest_data
from .run_clean import clean_data
from .run_feature_engineering import build_features

def run_pipeline():
    # raw_paths = ingest_data()          # Step 1
    cleaned_paths = clean_data()       # Step 2
    feature_paths = build_features()   # Step 3

if __name__ == "__main__":
    run_pipeline()
