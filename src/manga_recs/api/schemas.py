from pydantic import BaseModel
from typing import List

class RecommendationRequest(BaseModel):
    title: str
    top_n: int = 5

class RecommendationResponse(BaseModel):
    title: str
    recommendations: List[dict]

