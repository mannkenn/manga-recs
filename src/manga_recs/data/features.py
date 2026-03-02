from manga_recs.common.constants import (
    CLEANED_MANGA_METADATA_PARQUET,
    CLEANED_STATUS,
    CLEANED_USER_READDATA_PARQUET,
    FEATURES_STATUS,
    MANGA_FEATURES_PARQUET,
    USER_FEATURES_PARQUET,
)
from manga_recs.common.paths import CLEANED_DIR, FEATURES_DIR
from manga_recs.common.settings import settings
from manga_recs.data.load import s3_dump, s3_load
from manga_recs.data.transform import create_manga_features, create_user_features
from manga_recs.data.utils import load_parquet, save_parquet


def build_features():
    manga_clean_path = CLEANED_DIR / CLEANED_MANGA_METADATA_PARQUET
    user_clean_path = CLEANED_DIR / CLEANED_USER_READDATA_PARQUET
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)

    print("Downloading cleaned data from S3...")
    manga_clean_path = s3_load(CLEANED_MANGA_METADATA_PARQUET, bucket=settings.s3.bucket, status=CLEANED_STATUS)
    user_clean_path = s3_load(CLEANED_USER_READDATA_PARQUET, bucket=settings.s3.bucket, status=CLEANED_STATUS)
    print("Download complete!")

    print("Loading cleaned data...")
    manga_data = load_parquet(manga_clean_path)
    user_data = load_parquet(user_clean_path)
    print(f"Loaded {len(manga_data)} manga records and {len(user_data)} user records")

    print("Creating features...")
    manga_features = create_manga_features(manga_data)
    user_features = create_user_features(user_data)

    manga_output_path = FEATURES_DIR / MANGA_FEATURES_PARQUET
    user_output_path = FEATURES_DIR / USER_FEATURES_PARQUET

    save_parquet(manga_features, manga_output_path)
    save_parquet(user_features, user_output_path)

    print("Uploading features to S3...")
    s3_dump(str(manga_output_path), manga_output_path.name, status=FEATURES_STATUS)
    s3_dump(str(user_output_path), user_output_path.name, status=FEATURES_STATUS)
    print("Upload complete!")

    return {"manga": manga_output_path, "user": user_output_path}