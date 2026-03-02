from fastapi import FastAPI, HTTPException
from manga_recs.api.schemas import RecommendationResponse, RecommendationRequest
import joblib
import pandas as pd
from rapidfuzz import fuzz, process
from manga_recs.common.constants import (
    CLEANED_MANGA_METADATA_PARQUET,
    CLEANED_STATUS,
    COSINE_SIM_FILENAME,
    MODELS_STATUS,
)
from manga_recs.common.settings import settings
from manga_recs.data.load import s3_load

app = FastAPI(title="Manga Recommendation API")

# Load similarity matrix and metadata at startup
SIM_PATH = s3_load(COSINE_SIM_FILENAME, bucket=settings.s3.bucket, status=MODELS_STATUS)
SIM_MATRIX = joblib.load(SIM_PATH)

METADATA_PATH = s3_load(CLEANED_MANGA_METADATA_PARQUET, bucket=settings.s3.bucket, status=CLEANED_STATUS)
METADATA = pd.read_parquet(METADATA_PATH)

@app.post("/recommendations/", response_model=RecommendationResponse)
def recommend(request: RecommendationRequest):
    title = request.title
    top_n = request.top_n

    # Find manga ID from title using fuzzy matchingq
    titles = METADATA['title'].tolist()
    best_match = process.extractOne(title, titles, scorer=fuzz.ratio)
    if best_match is None or best_match[1] < settings.api.fuzzy_match_threshold:
        raise HTTPException(status_code=404, detail=f"Title '{title}' not found in metadata.")
    matched_title = best_match[0]

    matched = METADATA[METADATA['title'].str.lower() == matched_title.lower()]
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