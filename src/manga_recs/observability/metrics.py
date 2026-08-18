"""Prometheus metrics.

Each of these exists to answer a specific question during an incident, rather
than because it was easy to collect:

``requests_total``
    Traffic and error rate. Rate of the 5xx slice over the total is the
    first-line "is it broken" signal.
``request_duration_seconds``
    End-to-end latency, so p95 and p99 are computable. Labelled by route
    template, never by raw path, because unbounded label values are how a
    metrics backend gets destroyed.
``recommendation_duration_seconds``
    Just the model work: fuzzy match plus ranking, with HTTP overhead excluded.
    Splitting this from request duration is what distinguishes "the model got
    slow" from "something in front of the model got slow".
``title_match_score``
    Distribution of fuzzy-match confidence on successful lookups. The most
    interesting signal here: if this distribution drifts down, users are asking
    for titles the catalogue does not really contain, which is a staleness
    problem in the pipeline rather than an error in the service. Nothing in an
    error rate would show it.
``title_not_found_total``
    Outright misses. Read together with match_score: a rising miss rate with a
    healthy score distribution means new titles, whereas both degrading means
    the catalogue is wrong.
``model_items``
    Catalogue size currently loaded. A sudden drop means a bad pipeline run got
    published, and this is the cheapest possible tripwire for it.
``model_info``
    Which artifact source and partition are live, so a graph can be correlated
    with a deploy or a refresh.
"""

from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

METRICS_CONTENT_TYPE = CONTENT_TYPE_LATEST

# A dedicated registry rather than the global default, so importing this module
# cannot collide with another library's collectors and tests can reason about it.
REGISTRY = CollectorRegistry()

REQUESTS_TOTAL = Counter(
    "manga_recs_requests_total",
    "HTTP requests handled.",
    labelnames=("method", "route", "status"),
    registry=REGISTRY,
)

REQUEST_DURATION = Histogram(
    "manga_recs_request_duration_seconds",
    "End-to-end HTTP request latency.",
    labelnames=("method", "route"),
    # Tightened around the low end: served from memory, this endpoint should sit
    # in single-digit milliseconds, and the default buckets would put almost
    # every request in one bucket and hide all real variation.
    buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    registry=REGISTRY,
)

RECOMMENDATION_DURATION = Histogram(
    "manga_recs_recommendation_duration_seconds",
    "Time spent in fuzzy matching and ranking, excluding HTTP overhead.",
    buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
    registry=REGISTRY,
)

TITLE_MATCH_SCORE = Histogram(
    "manga_recs_title_match_score",
    "Fuzzy match confidence for resolved titles (0-100).",
    buckets=(65, 70, 75, 80, 85, 90, 95, 100),
    registry=REGISTRY,
)

TITLE_NOT_FOUND = Counter(
    "manga_recs_title_not_found_total",
    "Lookups that matched no catalogue title.",
    registry=REGISTRY,
)

MODEL_ITEMS = Gauge(
    "manga_recs_model_items",
    "Items in the loaded similarity matrix.",
    registry=REGISTRY,
)

MODEL_LOADED = Gauge(
    "manga_recs_model_loaded",
    "1 when model artifacts are resident, 0 otherwise.",
    registry=REGISTRY,
)

MODEL_INFO = Gauge(
    "manga_recs_model_info",
    "Labels describing the loaded model; the value is always 1.",
    labelnames=("artifact_source", "partition"),
    registry=REGISTRY,
)


def record_request(method: str, route: str, status: int, duration_seconds: float) -> None:
    REQUESTS_TOTAL.labels(method=method, route=route, status=str(status)).inc()
    REQUEST_DURATION.labels(method=method, route=route).observe(duration_seconds)


def observe_recommendation(duration_seconds: float) -> None:
    RECOMMENDATION_DURATION.observe(duration_seconds)


def observe_match_score(score: float) -> None:
    TITLE_MATCH_SCORE.observe(score)


def record_title_not_found() -> None:
    TITLE_NOT_FOUND.inc()


def set_model_info(*, items: int, artifact_source: str, partition: str | None) -> None:
    MODEL_LOADED.set(1)
    MODEL_ITEMS.set(items)
    MODEL_INFO.labels(artifact_source=artifact_source, partition=partition or "unknown").set(1)


def set_model_unavailable() -> None:
    MODEL_LOADED.set(0)


def render_metrics() -> bytes:
    return generate_latest(REGISTRY)
