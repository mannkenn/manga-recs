from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="Manga title to search for")
    top_n: int = Field(default=5, ge=1, le=50, description="How many recommendations to return")


class Recommendation(BaseModel):
    id: int
    title: str
    description: str | None = None
    genres: list[str] = []
    tags: list[str] = []
    similarity: float


class RecommendationResponse(BaseModel):
    title: str
    matched_title: str
    match_score: float
    recommendations: list[Recommendation]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    items: int | None = None
    # Which artifact source answered, so a deployed instance can prove whether
    # it is serving baked-in artifacts or something fetched at runtime.
    artifact_source: str | None = None
    model_partition: str | None = None
    detail: str | None = None
