from manga_recs.data_engineering.extract import fetch_manga_data, fetch_user_data
from manga_recs.data_engineering.load import s3_dump
from manga_recs.data_engineering.utils import MangaGraphQLClient, RateLimiter
from importlib.resources import files
import json

# GraphQL client
client = MangaGraphQLClient('https://graphql.anilist.co')

# Read graphql queries
manga_query_path = files("manga_recs.data_engineering.extract.queries") / "manga_metadata.graphql"
manga_query = manga_query_path.read_text(encoding="utf-8")

user_query_path = files("manga_recs.data_engineering.extract.queries") / "user_readdata.graphql"
user_query = user_query_path.read_text(encoding="utf-8")

# Define rate limits
rate_limiter = RateLimiter(30) # currently limit to 30 requests/minute

# Fetch manga data
manga_data = fetch_manga_data(client, manga_query, rate_limiter, popularity=10000) # min popularity of 10000

# Fetch user data
user_data = fetch_user_data(client, user_query, rate_limiter, max_pages=200) # currently testing 200 pages of user read data 

# Save manga data to json 
with open("data/raw/manga_metadata.json", "w", encoding="utf-8") as f:
    json.dump(manga_data, f, ensure_ascii=False, indent=4)

# Save user data to json
with open("data/raw/user_readdata.json", "w", encoding="utf-8") as f:
    json.dump(user_data, f, ensure_ascii=False, indent=4)

# Save to s3 bucket 
s3_dump("data/raw/manga_metadata.json", 'manga_metadata.json')
s3_dump("data/raw/user_readdata.json", 'user_readdata.json')

