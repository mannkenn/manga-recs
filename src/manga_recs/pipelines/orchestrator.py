from manga_recs.data.cleaning import clean_data
from manga_recs.data.features import build_features
from manga_recs.data.ingestion import ingest_data


def run_pipeline():
    ingest_data()
    clean_data()
    build_features()