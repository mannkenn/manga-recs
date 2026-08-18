"""FastAPI service exposing manga recommendations."""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from manga_recs.api.schemas import (
    HealthResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from manga_recs.common.settings import settings
from manga_recs.serving.recommender import TitleNotFoundError, get_recommender

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the artifact cache so the first real request is fast, but never fail
    # startup on it: the endpoint loads lazily and the platform health check
    # should be able to report an unhealthy-but-running service.
    try:
        get_recommender()
    except Exception as exc:  # noqa: BLE001 - startup must not crash on storage issues
        logger.warning("Could not preload model artifacts at startup: %s", exc)
    yield


app = FastAPI(
    title="Manga Recommendation API",
    description="Content-based manga recommendations from AniList metadata.",
    version="1.0.0",
    lifespan=lifespan,
)

# Comma-separated allowlist; defaults to "*" so local development just works.
_cors_origins = os.getenv("MANGA_RECS_CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.1f}"
    logger.info(
        "%s %s -> %s in %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe that also reports whether the model is resident."""
    try:
        recommender = get_recommender()
    except Exception as exc:  # noqa: BLE001 - report unhealthy rather than raising
        return HealthResponse(status="degraded", model_loaded=False, detail=str(exc))
    return HealthResponse(
        status="ok",
        model_loaded=True,
        items=int(recommender.sim_matrix.shape[0]),
        artifact_source=recommender.source,
        model_partition=(recommender.manifest or {}).get("partition"),
    )


@app.post("/recommendations/", response_model=RecommendationResponse)
def recommend(request: RecommendationRequest) -> RecommendationResponse:
    try:
        recommender = get_recommender()
    except Exception as exc:  # noqa: BLE001
        logger.error("Model unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Model artifacts unavailable.") from exc

    try:
        match, recommendations = recommender.recommend(request.title, request.top_n)
    except TitleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RecommendationResponse(
        title=request.title,
        matched_title=match.title,
        match_score=match.score,
        recommendations=recommendations,
    )


# Mounted last on purpose: Starlette matches routes in registration order, so
# every API route above still wins over this catch-all. Serving the UI from the
# same origin as the API is what collapses the deployment to one container and
# removes CORS from the picture entirely.
if settings.serving.static_dir is not None:
    app.mount(
        "/",
        StaticFiles(directory=settings.serving.static_dir, html=True),
        name="ui",
    )
    logger.info("Serving frontend from %s", settings.serving.static_dir)
else:
    logger.info("No built frontend found; running API-only.")
