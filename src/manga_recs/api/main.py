"""FastAPI service exposing manga recommendations."""

from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from manga_recs.api.schemas import (
    HealthResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from manga_recs.common.settings import settings
from manga_recs.observability import (
    METRICS_CONTENT_TYPE,
    configure_logging,
    configure_tracing,
    metrics,
    render_metrics,
    request_id_var,
    span,
)
from manga_recs.serving.recommender import TitleNotFoundError, get_recommender

configure_logging()
configure_tracing()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the artifact cache so the first real request is fast, but never fail
    # startup on it: the endpoint loads lazily and the platform health check
    # should be able to report an unhealthy-but-running service.
    with span("startup.preload_artifacts"):
        try:
            recommender = get_recommender()
        except Exception as exc:  # noqa: BLE001 - startup must not crash on storage issues
            metrics.set_model_unavailable()
            logger.warning(
                "Could not preload model artifacts at startup: %s",
                exc,
                extra={"event": "artifacts.preload_failed"},
            )
        else:
            metrics.set_model_info(
                items=int(recommender.sim_matrix.shape[0]),
                artifact_source=recommender.source,
                partition=(recommender.manifest or {}).get("partition"),
            )
            logger.info(
                "Model ready",
                extra={
                    "event": "artifacts.loaded",
                    "artifact_source": recommender.source,
                    "items": int(recommender.sim_matrix.shape[0]),
                },
            )
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


def _route_template(request: Request) -> str:
    """Return the matched route pattern, not the raw path.

    Metric labels must come from a bounded set. Using request.url.path would let
    any caller mint new label values by hitting arbitrary URLs, which is how a
    metrics backend gets flooded with useless series.
    """
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    # Honour an inbound correlation id so a request can be traced across a proxy
    # or a client that already has one, and mint one otherwise.
    incoming = request.headers.get("X-Request-ID")
    request_id = incoming or uuid.uuid4().hex[:16]
    token = request_id_var.set(request_id)

    started = time.perf_counter()
    try:
        # Everything stays inside the span, including the summary log, so that
        # line carries the trace and span ids and is joinable to the trace. Logged
        # after the span closed, it would have neither.
        with span(
            f"{request.method} {request.url.path}",
            **{
                "http.request.method": request.method,
                "url.path": request.url.path,
                "manga_recs.request_id": request_id,
            },
        ) as current:
            response = await call_next(request)
            elapsed = time.perf_counter() - started

            response.headers["X-Response-Time-ms"] = f"{elapsed * 1000:.1f}"
            # Echo the id so a user reporting a slow request can quote something
            # findable in the logs.
            response.headers["X-Request-ID"] = request_id

            route = _route_template(request)
            if current is not None:
                current.set_attribute("http.response.status_code", response.status_code)
                current.set_attribute("http.route", route)

            metrics.record_request(request.method, route, response.status_code, elapsed)

            # Static asset requests would otherwise drown the log during a demo.
            if not route.startswith("/_next") and route != "unmatched":
                logger.info(
                    "request completed",
                    extra={
                        "event": "http.request",
                        "http_method": request.method,
                        "http_route": route,
                        "http_path": request.url.path,
                        "http_status": response.status_code,
                        "duration_ms": round(elapsed * 1000, 2),
                    },
                )
            return response
    finally:
        request_id_var.reset(token)


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    """Prometheus scrape endpoint."""
    return Response(content=render_metrics(), media_type=METRICS_CONTENT_TYPE)


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
        metrics.set_model_unavailable()
        logger.error(
            "Model unavailable",
            extra={"event": "model.unavailable", "error": str(exc)},
        )
        raise HTTPException(status_code=503, detail="Model artifacts unavailable.") from exc

    started = time.perf_counter()
    try:
        match, recommendations = recommender.recommend(request.title, request.top_n)
    except TitleNotFoundError as exc:
        metrics.record_title_not_found()
        # Logged at info, not error: an unmatchable query is a normal outcome,
        # and paging on it would be noise. It is still worth counting, because a
        # rising miss rate is a catalogue-coverage signal.
        logger.info(
            "title not found",
            extra={"event": "recommendation.miss", "query": request.title},
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    elapsed = time.perf_counter() - started
    metrics.observe_recommendation(elapsed)
    metrics.observe_match_score(match.score)

    logger.info(
        "recommendations served",
        extra={
            "event": "recommendation.hit",
            "query": request.title,
            "matched_title": match.title,
            "match_score": match.score,
            "returned": len(recommendations),
            "duration_ms": round(elapsed * 1000, 2),
        },
    )

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
