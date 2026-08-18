import logging

from manga_recs.common.constants import (
    CLEANED_MANGA_METADATA_PARQUET,
    CLEANED_STATUS,
    CLEANED_USER_READDATA_PARQUET,
    MANGA_METADATA_JSON,
    RAW_STATUS,
    USER_READDATA_JSON,
)
from manga_recs.common.paths import CLEANED_DIR
from manga_recs.data.load import get_file, put_file
from manga_recs.data.quality import check_frame
from manga_recs.data.transform import clean_manga_metadata, clean_user_readdata
from manga_recs.data.utils import load_json, save_parquet

logger = logging.getLogger(__name__)


def clean_data(partition: str | None = None) -> dict[str, str]:
    """Read raw JSON, normalize it, and write validated Parquet back to storage."""
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)

    manga_path = get_file(MANGA_METADATA_JSON, status=RAW_STATUS, partition=partition)
    user_path = get_file(USER_READDATA_JSON, status=RAW_STATUS, partition=partition)

    manga_data = load_json(str(manga_path))
    user_data = load_json(str(user_path))
    logger.info("Loaded %d manga records and %d user records", len(manga_data), len(user_data))

    manga_df = check_frame(
        clean_manga_metadata(manga_data),
        name="cleaned_manga_metadata",
        required_columns=("id", "title", "tags", "genres", "popularity"),
        non_null_columns=("id", "title"),
        unique_columns=("id",),
    )
    user_df = check_frame(
        clean_user_readdata(user_data),
        name="cleaned_user_readdata",
        required_columns=("userId", "mediaId", "status", "score"),
        non_null_columns=("userId", "mediaId"),
    )

    manga_output_path = CLEANED_DIR / CLEANED_MANGA_METADATA_PARQUET
    user_output_path = CLEANED_DIR / CLEANED_USER_READDATA_PARQUET

    save_parquet(manga_df, manga_output_path)
    save_parquet(user_df, user_output_path)

    return {
        "manga": put_file(
            manga_output_path, CLEANED_MANGA_METADATA_PARQUET, CLEANED_STATUS, partition=partition
        ),
        "user": put_file(
            user_output_path, CLEANED_USER_READDATA_PARQUET, CLEANED_STATUS, partition=partition
        ),
    }
