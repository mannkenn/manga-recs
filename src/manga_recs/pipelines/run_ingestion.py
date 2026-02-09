from manga_recs.data_engineering.ingestion import (
    MangaGraphQLClient,
    fetch_manga_data,
    fetch_user_data,
    RateLimiter,
    s3_dump,
)
from manga_recs.data_engineering.processing.clean import (
    clean_manga_metadata, id_quality, describe_outliers
)
from importlib.resources import files
import json
import os

# GraphQL client
client = MangaGraphQLClient('https://graphql.anilist.co')

# Read graphql queries
manga_query_path = files("manga_recs.data_engineering.ingestion.queries") / "manga_metadata.graphql"
manga_query = manga_query_path.read_text(encoding="utf-8")

user_query_path = files("manga_recs.data_engineering.ingestion.queries") / "user_readdata.graphql"
user_query = user_query_path.read_text(encoding="utf-8")

# Define rate limits
rate_limiter = RateLimiter(30) # currently limit to 30 requests/minute

# Fetch manga data
manga_data = fetch_manga_data(client, manga_query, rate_limiter, popularity=10000) # min popularity of 10000

# Fetch user data
user_data = fetch_user_data(client, user_query, rate_limiter, max_pages=200) # currently testing 200 pages of user read data 

# make folders
os.makedirs("data/raw", exist_ok=True)
os.makedirs("data/clean", exist_ok=True)

# Save manga data to json 
with open("data/raw/manga_metadata.json", "w", encoding="utf-8") as f:
    json.dump(manga_data, f, ensure_ascii=False, indent=4)

    # Save user data to json
    with open("data/raw/user_readdata.json", "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=4)

# Save to s3 bucket 
s3_dump("data/raw/manga_metadata.json", 'manga_metadata.json')
s3_dump("data/raw/user_readdata.json", 'user_readdata.json')

# 2/9/2026: Clean to s3 
clean_manga_df = clean_manga_metadata(manga_data)

# Save clean manga data to json 
clean_manga_records = clean_manga_df.to_dict(orient="records")
with open("data/clean/clean_manga_metadata.json", "w", encoding="utf-8") as f:
    json.dump(clean_manga_records, f, ensure_ascii=False, indent=4)

# Save to s3 bucket, clean
s3_dump("data/clean/clean_manga_metadata.json", "clean_manga_metadata.json", status="clean")