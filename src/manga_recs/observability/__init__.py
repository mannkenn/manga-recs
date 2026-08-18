"""Instrumentation for the service and the pipeline.

Three signals, all inert until configured:

``logs``
    JSON to stdout, every line carrying the request id and, when a span is
    active, the trace and span ids. That is what makes a log line joinable to a
    trace instead of merely adjacent to one.
``traces``
    OpenTelemetry spans. The exporter defaults to ``none``, so nothing is
    emitted and nothing is required to be running; pointing it at a collector is
    an environment variable.
``metrics``
    A Prometheus endpoint at ``/metrics``.

Defaulting the exporter to a no-op is deliberate: the demo must never depend on
a collector being reachable, but the instrumentation has to already be in the
code so that turning it on is configuration rather than a rewrite.
"""

from manga_recs.observability import metrics
from manga_recs.observability.logging import (
    configure_logging,
    get_request_id,
    request_id_var,
)
from manga_recs.observability.metrics import (
    METRICS_CONTENT_TYPE,
    observe_match_score,
    observe_recommendation,
    record_request,
    render_metrics,
    set_model_info,
)
from manga_recs.observability.tracing import configure_tracing, span, tracer

__all__ = [
    "METRICS_CONTENT_TYPE",
    "configure_logging",
    "configure_tracing",
    "get_request_id",
    "metrics",
    "observe_match_score",
    "observe_recommendation",
    "record_request",
    "render_metrics",
    "request_id_var",
    "set_model_info",
    "span",
    "tracer",
]
