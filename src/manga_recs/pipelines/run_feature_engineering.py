from manga_recs.data_engineering.utils import load_parquet, save_parquet
from manga_recs.data_engineering.load import s3_dump
from manga_recs.data_engineering.transform.feature_engineering import create_manga_features, create_user_features
from pathlib import Path

input_dir = "data/cleaned"
output_dir = "data/features"

# Create output directory
Path(output_dir).mkdir(parents=True, exist_ok=True)

# Load cleaned data
print("Loading cleaned data...")
manga_data = load_parquet(Path(input_dir) / "cleaned_manga_metadata.parquet")
user_data = load_parquet(Path(input_dir) / "cleaned_user_readdata.parquet")
print(f"Loaded {len(manga_data)} manga records and {len(user_data)} user records")

# Create features
print("Creating features...")
manga_features = create_manga_features(Path(input_dir) / "cleaned_manga_metadata.parquet")

# Save features
print("Saving features to parquet...")
manga_output_path = Path(output_dir) / "manga_features.parquet"
save_parquet(manga_features, manga_output_path)

# Upload to S3
print("Uploading to S3...")
s3_dump(str(manga_output_path), "manga_features.parquet", status='features')