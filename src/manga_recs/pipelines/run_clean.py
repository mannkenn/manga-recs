from pathlib import Path
from manga_recs.data_engineering.utils import load_json, save_parquet
from manga_recs.data_engineering.load import s3_dump, s3_load
from manga_recs.data_engineering.transform import clean_manga_metadata, clean_user_readdata

def clean_data():

    # Input and output
    input_dir = Path("data/raw")
    manga_path = input_dir / "manga_metadata.json"
    user_path = input_dir / "user_readdata.json"
    output_dir = Path("data/cleaned")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Download raw data from S3
    print("Downloading raw data from S3...")
    manga_path = s3_load("manga_metadata.json", bucket="manga-recs", status="raw")
    user_path = s3_load("user_readdata.json", bucket="manga-recs", status="raw")
    print("Download complete!")

    # Load raw data
    print("Loading raw data...")
    manga_data = load_json(manga_path)
    user_data = load_json(user_path)
    print(f"Loaded {len(manga_data)} manga records and {len(user_data)} user records")

    # Clean
    print("Cleaning manga metadata...")
    manga_df = clean_manga_metadata(manga_data)
    print(f"Cleaned manga: {len(manga_df)} records")

    print("Cleaning user read data...")
    user_df = clean_user_readdata(user_data)
    print(f"Cleaned user data: {len(user_df)} records")

    # Save locally
    manga_output_path = output_dir / "cleaned_manga_metadata.parquet"
    user_output_path = output_dir / "cleaned_user_readdata.parquet"

    save_parquet(manga_df, manga_output_path)
    save_parquet(user_df, user_output_path)

    # Upload to S3
    print("Uploading to S3...")
    s3_dump(str(manga_output_path), manga_output_path.name, status="cleaned")
    s3_dump(str(user_output_path), user_output_path.name, status="cleaned")
    print("Upload complete!")

    # Return paths for downstream usage
    return {
        "manga": manga_output_path,
        "user": user_output_path
    }

if __name__ == "__main__":
    clean_data()
