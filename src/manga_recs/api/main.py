from fastapi import FastAPI, HTTPException
from schemas import RecommendationResponse, RecommendationRequest
import joblib
import pandas as pd
from pathlib import Path

app = FastAPI(title="Manga Recommendation API")

# Load similarity matrix and metadata at startup
BASE_DIR = Path(__file__).resolve().parents[3]

SIM_PATH = BASE_DIR / "artifacts" / "models" / "cosine_sim.pkl"
SIM_MATRIX = joblib.load(SIM_PATH)

METADATA_PATH = BASE_DIR / "data" / "cleaned" / "cleaned_manga_metadata.parquet"
METADATA = pd.read_parquet(METADATA_PATH)

@app.post("/recommendations/", response_model=RecommendationResponse)
def recommend(request: RecommendationRequest):
    title = request.title
    top_n = request.top_n

    # Find manga ID from title
    matched = METADATA[METADATA['title'].str.lower() == title.lower()]
    if matched.empty:
        raise HTTPException(status_code=404, detail=f"Title '{title}' not found in metadata.")
    
    manga_id = matched['id'].iloc[0]
    
    if manga_id not in SIM_MATRIX.index:
        raise HTTPException(status_code=404, detail=f"Manga ID {manga_id} (from title '{title}') not found in similarity matrix.")

    # Get similarity scores for this manga
    similarities = SIM_MATRIX.loc[manga_id]

    # Get top-N
    top_similarities = similarities.sort_values(ascending=False).head(top_n)

    # Get metadata for recommended manga
    recs = METADATA[METADATA['id'].isin(top_similarities.index)][['id', 'title', 'description', 'tags']]

    # Merge similarity scores
    recs = recs.set_index('id').join(top_similarities.rename("similarity"))
    recs['similarity'] = recs['similarity'].round(2)

    # Conert dtypes for JSON serialization
    recs['similarity'] = recs['similarity'].apply(float)
    recs['tags'] = recs['tags'].apply(lambda x: list(x) if isinstance(x, (list, pd.Series)) else str(x))

    recs = recs.sort_values(by="similarity", ascending=False)
    
    return RecommendationResponse(title=title, recommendations=recs.reset_index().to_dict(orient='records'))