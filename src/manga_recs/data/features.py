import logging

from manga_recs.common.constants import (
    CLEANED_MANGA_METADATA_PARQUET,
    CLEANED_STATUS,
    CLEANED_USER_READDATA_PARQUET,
    FEATURES_STATUS,
    MANGA_FEATURES_PARQUET,
    USER_FEATURES_PARQUET,
)
from manga_recs.common.paths import FEATURES_DIR
from manga_recs.data.load import get_file, put_file
from manga_recs.data.quality import check_frame
from manga_recs.data.transform import create_manga_features, create_user_features
from manga_recs.data.utils import load_parquet, save_parquet

logger = logging.getLogger(__name__)


def build_features(partition: str | None = None) -> dict[str, str]:
    """Turn cleaned Parquet into model-ready feature matrices."""
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)

    manga_clean_path = get_file(
        CLEANED_MANGA_METADATA_PARQUET, status=CLEANED_STATUS, partition=partition
    )
    user_clean_path = get_file(
        CLEANED_USER_READDATA_PARQUET, status=CLEANED_STATUS, partition=partition
    )

    manga_data = load_parquet(str(manga_clean_path))
    user_data = load_parquet(str(user_clean_path))
    logger.info("Loaded %d manga records and %d user records", len(manga_data), len(user_data))

    manga_features = check_frame(
        create_manga_features(manga_data),
        name="manga_features",
        required_columns=("id",),
        non_null_columns=("id",),
        unique_columns=("id",),
    )
    user_features = check_frame(
        create_user_features(user_data),
        name="user_features",
        required_columns=("userId", "mediaId", "interaction_strength"),
    )

    manga_output_path = FEATURES_DIR / MANGA_FEATURES_PARQUET
    user_output_path = FEATURES_DIR / USER_FEATURES_PARQUET

    save_parquet(manga_features, manga_output_path)
    save_parquet(user_features, user_output_path)

    logger.info(
        "Built manga features: %d items x %d features",
        manga_features.shape[0],
        manga_features.shape[1] - 1,
    )

    return {
        "manga": put_file(
            manga_output_path, MANGA_FEATURES_PARQUET, FEATURES_STATUS, partition=partition
        ),
        "user": put_file(
            user_output_path, USER_FEATURES_PARQUET, FEATURES_STATUS, partition=partition
        ),
    }
