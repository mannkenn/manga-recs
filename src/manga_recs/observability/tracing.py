"""OpenTelemetry tracing setup.

The exporter defaults to ``none``: spans are created and carry attributes, but
nothing is shipped anywhere and no collector needs to exist. That keeps the
public demo from depending on external infrastructure while leaving the
instrumentation in place, so enabling a real backend is an environment variable
rather than a code change.

    MANGA_RECS_TRACE_EXPORTER=console          # print spans to stdout
    MANGA_RECS_TRACE_EXPORTER=otlp \
        OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

SERVICE_NAME = "manga-recs"

_configured = False


def _resolve_exporter() -> str:
    return os.getenv("MANGA_RECS_TRACE_EXPORTER", "none").strip().lower()


def configure_tracing(exporter: str | None = None) -> None:
    """Install a tracer provider. Safe to call more than once."""
    global _configured
    if _configured:
        return

    exporter = (exporter or _resolve_exporter()).strip().lower()

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
    except ImportError:
        # Without the SDK the API's default no-op tracer is used, which is a
        # perfectly acceptable degraded state.
        logger.info("OpenTelemetry SDK not installed; tracing disabled.")
        _configured = True
        return

    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": os.getenv("MANGA_RECS_VERSION", "dev"),
            "deployment.environment": os.getenv("MANGA_RECS_ENV", "local"),
        }
    )
    provider = TracerProvider(resource=resource)

    if exporter == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        logger.info("Tracing enabled with the console exporter.")
    elif exporter == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        except ImportError:
            logger.warning(
                "MANGA_RECS_TRACE_EXPORTER=otlp but the OTLP exporter is not installed. "
                "Install the 'otlp' extra. Continuing without an exporter."
            )
        else:
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
            logger.info(
                "Tracing enabled with the OTLP exporter -> %s",
                os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "default endpoint"),
            )
    else:
        # Spans are still created and still parent each other; they are simply
        # not exported. Nothing downstream has to care.
        logger.info(
            "Tracing instrumented but no exporter configured (set MANGA_RECS_TRACE_EXPORTER)."
        )

    trace.set_tracer_provider(provider)
    _configured = True


def tracer():
    """Return a tracer, falling back to a no-op if the API is unavailable."""
    from opentelemetry import trace

    return trace.get_tracer(SERVICE_NAME)


@contextmanager
def span(name: str, **attributes: Any):
    """Start a span with attributes, recording any exception that escapes.

    Wrapped so call sites in the pipeline and the serving path do not each need
    to handle a missing OpenTelemetry install.
    """
    try:
        from opentelemetry import trace
    except ImportError:
        yield None
        return

    with tracer().start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        try:
            yield current
        except Exception as exc:
            current.record_exception(exc)
            current.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            raise
