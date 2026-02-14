from pathlib import Path
from manga_recs.data_engineering.utils import load_parquet, save_parquet
from manga_recs.data_engineering.load import s3_dump, s3_load
from manga_recs.data_engineering.transform import create_manga_features, create_user_features

def build_features():

    # Input and output paths
    input_dir = Path("data/cleaned")    
    manga_clean_path = input_dir / "cleaned_manga_metadata.parquet"
    user_clean_path = input_dir / "cleaned_user_readdata.parquet"
    output_dir = Path("data/features")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Download cleaned data from S3
    print("Downloading cleaned data from S3...")
    manga_clean_path = s3_load("cleaned_manga_metadata.parquet", bucket="manga-recs", status="cleaned")
    user_clean_path = s3_load("cleaned_user_readdata.parquet", bucket="manga-recs", status="cleaned")
    print("Download complete!")

    # Load cleaned data
    print("Loading cleaned data...")
    manga_data = load_parquet(manga_clean_path)
    user_data = load_parquet(user_clean_path)
    print(f"Loaded {len(manga_data)} manga records and {len(user_data)} user records")

    # Create features
    print("Creating features...")
    manga_features = create_manga_features(manga_data)
    user_features = create_user_features(user_data)

    # Save features locally
    manga_output_path = output_dir / "manga_features.parquet"
    user_output_path = output_dir / "user_features.parquet"

    save_parquet(manga_features, manga_output_path)
    save_parquet(user_features, user_output_path)

    # Upload to S3
    print("Uploading features to S3...")
    s3_dump(str(manga_output_path), manga_output_path.name, status="features")
    s3_dump(str(user_output_path), user_output_path.name, status="features")
    print("Upload complete!")

    # Return paths for downstream usage
    return {
        "manga": manga_output_path,
        "user": user_output_path
    }

if __name__ == "__main__":
    build_features()
