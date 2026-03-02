from importlib.resources import files
import json

from manga_recs.common.constants import (
    MANGA_METADATA_JSON,
    RAW_STATUS,
    USER_READDATA_JSON,
)
from manga_recs.common.paths import RAW_DIR
from manga_recs.common.settings import settings
from manga_recs.data.extract import fetch_manga_data, fetch_user_data
from manga_recs.data.load import s3_dump
from manga_recs.data.utils import MangaGraphQLClient, RateLimiter


def ingest_data():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    client = MangaGraphQLClient(settings.api.graphql_url)

    manga_query = (files("manga_recs.data.extract.queries") / "manga_metadata.graphql").read_text(encoding="utf-8")
    user_query = (files("manga_recs.data.extract.queries") / "user_readdata.graphql").read_text(encoding="utf-8")

    rate_limiter = RateLimiter(settings.ingestion.rate_limit)

    manga_data = fetch_manga_data(
        client,
        manga_query,
        rate_limiter,
        popularity=settings.ingestion.popularity_min,
    )
    user_data = fetch_user_data(
        client,
        user_query,
        rate_limiter,
        per_page=settings.ingestion.user_per_page,
        max_pages=settings.ingestion.user_max_pages,
        start_user_id=settings.ingestion.user_start_id,
        end_user_id=settings.ingestion.user_end_id,
    )

    manga_path = RAW_DIR / MANGA_METADATA_JSON
    user_path = RAW_DIR / USER_READDATA_JSON

    with open(manga_path, "w", encoding="utf-8") as f:
        json.dump(manga_data, f, ensure_ascii=False, indent=4)

    with open(user_path, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=4)

    s3_dump(str(manga_path), manga_path.name, status=RAW_STATUS)
    s3_dump(str(user_path), user_path.name, status=RAW_STATUS)

    return {"manga": manga_path, "user": user_path}