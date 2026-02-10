from manga_recs.data_engineering.utils import load_json, save_parquet
from manga_recs.data_engineering.load import s3_dump
from manga_recs.data_engineering.transform.clean import clean_manga_metadata, clean_user_readdata
from pathlib import Path

input_dir = "data/raw"
output_dir = "data/cleaned"

# Create output directory
Path(output_dir).mkdir(parents=True, exist_ok=True)

# Load raw data
print("Loading raw data...")
manga_data = load_json(Path(input_dir) / "manga_metadata.json")
user_data = load_json(Path(input_dir) / "user_readdata.json")
print(f"Loaded {len(manga_data)} manga records and {len(user_data)} user records")

# Clean data
print("Cleaning manga metadata...")
manga_df = clean_manga_metadata(manga_data)
print(f"Cleaned manga: {len(manga_df)} records")

print("Cleaning user read data...")
user_df = clean_user_readdata(user_data)
print(f"Cleaned user data: {len(user_df)} records")

# Save cleaned data
print("Saving cleaned data to parquet...")
manga_output_path = Path(output_dir) / "cleaned_manga_metadata.parquet"
user_output_path = Path(output_dir) / "cleaned_user_readdata.parquet"

save_parquet(manga_df, manga_output_path)
print(f"Saved manga metadata to {manga_output_path}")

save_parquet(user_df, user_output_path)
print(f"Saved user data to {user_output_path}")

# Upload to S3
print("Uploading to S3...")
s3_dump(str(manga_output_path), "cleaned_manga_metadata.parquet", status='cleaned')
s3_dump(str(user_output_path), "cleaned_user_readdata.parquet", status='cleaned')
print("Upload complete!")