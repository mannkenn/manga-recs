import pandas as pd
import joblib
import argparse
from manga_recs.data_engineering.load.s3 import s3_load

# Paths
MODEL_PATH = s3_load("cosine_sim.pkl", bucket="manga-recs", status="models")
METADATA_PATH = s3_load("cleaned_manga_metadata.parquet", bucket="manga-recs", status="cleaned")

# Load similarity matrix + metadata
SIM_MATRIX = joblib.load(MODEL_PATH)
METADATA = pd.read_parquet(METADATA_PATH)

def get_top_n_recommendations_by_title(title, top_n=5):
    """Return top-N manga recommendations given a manga title."""
    
    # Find manga ID from title
    matched = METADATA[METADATA['title'].str.lower() == title.lower()]
    if matched.empty:
        raise ValueError(f"Title '{title}' not found in metadata.")
    
    manga_id = matched['id'].iloc[0]
    
    if manga_id not in SIM_MATRIX.index:
        raise ValueError(f"Manga ID {manga_id} (from title '{title}') not found in similarity matrix.")

    # Get similarity scores for this manga
    similarities = SIM_MATRIX.loc[manga_id]

    # Exclude itself and get top-N
    top_similarities = similarities.drop(manga_id, errors='ignore').sort_values(ascending=False).head(top_n)

    # Get metadata for recommended manga
    recs = METADATA[METADATA['id'].isin(top_similarities.index)][['id', 'title', 'description', 'tags']]

    # Merge similarity scores
    recs = recs.set_index('id').join(top_similarities.rename("similarity"))
    recs['similarity'] = recs['similarity'].round(2)

    recs = recs.sort_values(by="similarity", ascending=False)
    return recs.reset_index().to_dict(orient='records')


def main():
    parser = argparse.ArgumentParser(description="Get top-N manga recommendations by title")
    parser.add_argument("--title", type=str, required=True, help="Manga title to generate recommendations for")
    parser.add_argument("--top_n", type=int, default=5, help="Number of recommendations to return")
    args = parser.parse_args()

    recommendations = get_top_n_recommendations_by_title(title=args.title, top_n=args.top_n)
    for rec in recommendations:
        print(rec)


if __name__ == "__main__":
    main()
