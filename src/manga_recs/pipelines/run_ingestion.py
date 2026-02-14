# run_ingestion.py
from manga_recs.data_engineering.extract import fetch_manga_data, fetch_user_data
from manga_recs.data_engineering.load import s3_dump
from manga_recs.data_engineering.utils import MangaGraphQLClient, RateLimiter
from importlib.resources import files
from pathlib import Path
import json

def ingest_data():
    """
    Fetch raw manga and user data from GraphQL and upload to S3.
    Returns local paths to the downloaded files.
    """
    Path("data/raw").mkdir(parents=True, exist_ok=True)

    # GraphQL client
    client = MangaGraphQLClient('https://graphql.anilist.co')

    # Load queries
    manga_query = (files("manga_recs.data_engineering.extract.queries") / "manga_metadata.graphql").read_text(encoding="utf-8")
    user_query = (files("manga_recs.data_engineering.extract.queries") / "user_readdata.graphql").read_text(encoding="utf-8")

    # Rate limiter
    rate_limiter = RateLimiter(30)

    # Fetch data
    manga_data = fetch_manga_data(client, manga_query, rate_limiter, popularity=10000)
    user_data = fetch_user_data(client, user_query, rate_limiter, max_pages=200)

    # Save locally
    manga_path = Path("data/raw/manga_metadata.json")
    user_path = Path("data/raw/user_readdata.json")

    with open(manga_path, "w", encoding="utf-8") as f:
        json.dump(manga_data, f, ensure_ascii=False, indent=4)

    with open(user_path, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=4)

    # Upload to S3
    s3_dump(str(manga_path), manga_path.name, status="raw")
    s3_dump(str(user_path), user_path.name, status="raw")

    return {"manga": manga_path, "user": user_path}


if __name__ == "__main__":
    ingest_data()
