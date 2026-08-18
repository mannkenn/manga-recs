import json
import logging
from collections.abc import Sequence
from importlib.resources import files

from manga_recs.common.constants import (
    DATASETS,
    MANGA_METADATA_JSON,
    RAW_STATUS,
    USER_READDATA_JSON,
)
from manga_recs.common.paths import RAW_DIR
from manga_recs.common.settings import settings
from manga_recs.data.extract import fetch_manga_data, fetch_user_data
from manga_recs.data.load import put_file
from manga_recs.data.utils import MangaGraphQLClient, RateLimiter

logger = logging.getLogger(__name__)


def ingest_data(
    partition: str | None = None,
    datasets: Sequence[str] = DATASETS,
) -> dict[str, str]:
    """Fetch manga metadata and user read lists from AniList into raw storage.

    ``datasets`` selects which to fetch. The two are independent, and the user
    read lists dominate the runtime by orders of magnitude: manga metadata is
    about 20 paged requests, while user data walks a 500-id range. A change that
    only affects the media schema therefore has no business re-scanning every
    user, so it can be re-ingested on its own.
    """
    unknown = [name for name in datasets if name not in DATASETS]
    if unknown:
        raise ValueError(f"Unknown dataset(s) {unknown}; expected any of {list(DATASETS)}.")
    if not datasets:
        raise ValueError("No datasets selected for ingestion.")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    client = MangaGraphQLClient(settings.api.graphql_url)
    rate_limiter = RateLimiter(settings.ingestion.rate_limit)
    results: dict[str, str] = {}

    if "manga" in datasets:
        manga_query = (
            files("manga_recs.data.extract.queries") / "manga_metadata.graphql"
        ).read_text(encoding="utf-8")
        manga_data = fetch_manga_data(
            client,
            manga_query,
            rate_limiter,
            popularity=settings.ingestion.popularity_min,
        )
        if not manga_data:
            raise ValueError("AniList returned no manga records; refusing to overwrite raw data.")

        logger.info("Fetched %d manga records", len(manga_data))
        manga_path = RAW_DIR / MANGA_METADATA_JSON
        with open(manga_path, "w", encoding="utf-8") as f:
            json.dump(manga_data, f, ensure_ascii=False, indent=4)
        results["manga"] = put_file(
            manga_path, MANGA_METADATA_JSON, RAW_STATUS, partition=partition
        )

    if "users" in datasets:
        user_query = (files("manga_recs.data.extract.queries") / "user_readdata.graphql").read_text(
            encoding="utf-8"
        )
        user_data = fetch_user_data(
            client,
            user_query,
            rate_limiter,
            per_page=settings.ingestion.user_per_page,
            max_pages=settings.ingestion.user_max_pages,
            start_user_id=settings.ingestion.user_start_id,
            end_user_id=settings.ingestion.user_end_id,
            max_retries=settings.ingestion.user_max_retries,
        )
        if not user_data:
            raise ValueError("AniList returned no user records; refusing to overwrite raw data.")

        logger.info("Fetched %d user records", len(user_data))
        user_path = RAW_DIR / USER_READDATA_JSON
        with open(user_path, "w", encoding="utf-8") as f:
            json.dump(user_data, f, ensure_ascii=False, indent=4)
        results["user"] = put_file(user_path, USER_READDATA_JSON, RAW_STATUS, partition=partition)

    return results
