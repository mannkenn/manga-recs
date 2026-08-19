from pydantic import BaseModel, ConfigDict, Field


class RecommendationRequest(BaseModel):
    # The browser client sends camelCase. Without the alias, Pydantic found no
    # `top_n`, silently fell back to the default, and every request got five
    # results however many were asked for - the UI's count control did nothing.
    #
    # populate_by_name keeps snake_case working for curl and the Python client.
    # extra="forbid" is the other half of the fix: a field the server does not
    # recognise now fails with a 422 instead of being quietly dropped, which is
    # how this went unnoticed in the first place.
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    title: str = Field(min_length=1, max_length=200, description="Manga title to search for")
    top_n: int = Field(
        default=5,
        ge=1,
        le=50,
        alias="topN",
        description="How many recommendations to return",
    )


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
