from manga_recs.common.constants import (
    CLEANED_MANGA_METADATA_PARQUET,
    CLEANED_STATUS,
    CLEANED_USER_READDATA_PARQUET,
    MANGA_METADATA_JSON,
    RAW_STATUS,
    USER_READDATA_JSON,
)
from manga_recs.common.paths import CLEANED_DIR, RAW_DIR
from manga_recs.common.settings import settings
from manga_recs.data.load import s3_dump, s3_load
from manga_recs.data.transform import clean_manga_metadata, clean_user_readdata
from manga_recs.data.utils import load_json, save_parquet


def clean_data():
    manga_path = RAW_DIR / MANGA_METADATA_JSON
    user_path = RAW_DIR / USER_READDATA_JSON
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)

    print("Downloading raw data from S3...")
    manga_path = s3_load(MANGA_METADATA_JSON, bucket=settings.s3.bucket, status=RAW_STATUS)
    user_path = s3_load(USER_READDATA_JSON, bucket=settings.s3.bucket, status=RAW_STATUS)
    print("Download complete!")

    print("Loading raw data...")
    manga_data = load_json(manga_path)
    user_data = load_json(user_path)
    print(f"Loaded {len(manga_data)} manga records and {len(user_data)} user records")

    print("Cleaning manga metadata...")
    manga_df = clean_manga_metadata(manga_data)
    print(f"Cleaned manga: {len(manga_df)} records")

    print("Cleaning user read data...")
    user_df = clean_user_readdata(user_data)
    print(f"Cleaned user data: {len(user_df)} records")

    manga_output_path = CLEANED_DIR / CLEANED_MANGA_METADATA_PARQUET
    user_output_path = CLEANED_DIR / CLEANED_USER_READDATA_PARQUET

    save_parquet(manga_df, manga_output_path)
    save_parquet(user_df, user_output_path)

    print("Uploading to S3...")
    s3_dump(str(manga_output_path), manga_output_path.name, status=CLEANED_STATUS)
    s3_dump(str(user_output_path), user_output_path.name, status=CLEANED_STATUS)
    print("Upload complete!")

    return {"manga": manga_output_path, "user": user_output_path}