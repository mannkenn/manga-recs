from api_client import MangaGraphQLClient
from pull_manga import fetch_manga_data
from pull_userdata import fetch_user_data
from rate_limiter import RateLimiter
from s3 import s3_dump
import json

# GraphQL client
client = MangaGraphQLClient('https://graphql.anilist.co')

# Read queries from graphql files
with open("ingestion/queries/manga_metadata.graphql", "r", encoding="utf-8") as f:
    manga_query = f.read()

with open("ingestion/queries/user_readdata.graphql", "r", encoding="utf-8") as f:
    user_query = f.read()

# Define rate limits
rate_limiter = RateLimiter (30) # currently limit to 30 requests/minute

# Fetch manga data
manga_data = fetch_manga_data(client, manga_query, rate_limiter)

# Fetch user data
user_data = fetch_user_data(client, user_query, rate_limiter)

# Save manga data to json 
with open("data/raw/manga_metadata.json", "w", encoding="utf-8") as f:
    json.dump(manga_data, f, ensure_ascii=False, indent=4)

# Save user data to json
with open("data/raw/user_readdata.json", "w", encoding="utf-8") as f:
    json.dump(user_data, f, ensure_ascii=False, indent=4)

# Save to s3 bucket 
s3_dump("data/raw/manga_metadata.json", 'manga_metadata.json')
s3_dump("data/raw/user_readdata.json", 'user_readdata.json')

