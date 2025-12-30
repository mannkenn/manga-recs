from api_client import MangaGraphQLClient
from pull_manga import fetch_all_pages
from s3 import s3_dump
import json

# GraphQL client
client = MangaGraphQLClient('https://graphql.anilist.co')

# Read query from graphql file
with open("ingestion/queries/manga_metadata.graphql", "r", encoding="utf-8") as f:
    query = f.read()

# Fetch data
data = fetch_all_pages(client, query)

# Save to json 
with open("data/raw/manga_metadata.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

# Save to s3 bucket 
s3_dump("data/raw/manga_metadata.json", 'manga_metadata.json')

