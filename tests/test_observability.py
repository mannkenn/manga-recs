"""Tests for logging, metrics, and tracing.

The properties worth protecting: log records are machine-parseable and carry the
correlation id, metric labels stay bounded, and instrumentation degrades quietly
rather than taking a request down with it.
"""

from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from manga_recs.api import main as api_main
from manga_recs.observability import metrics as metrics_module
from manga_recs.observability.logging import JsonFormatter, request_id_var
from manga_recs.observability.tracing import configure_tracing, span
from manga_recs.serving.recommender import Recommender


@pytest.fixture
def client(monkeypatch, similarity_matrix, catalog_metadata) -> TestClient:
    recommender = Recommender(similarity_matrix, catalog_metadata, fuzzy_threshold=70)
    monkeypatch.setattr(api_main, "get_recommender", lambda: recommender)
    with TestClient(api_main.app) as test_client:
        yield test_client


def _record(**kwargs) -> logging.LogRecord:
    defaults = {
        "name": "test",
        "level": logging.INFO,
        "pathname": __file__,
        "lineno": 1,
        "msg": "hello",
        "args": (),
        "exc_info": None,
    }
    defaults.update(kwargs)
    return logging.LogRecord(**defaults)


class TestJsonFormatter:
    def test_emits_single_line_json(self):
        output = JsonFormatter().format(_record())
        assert "\n" not in output
        assert json.loads(output)["message"] == "hello"

    def test_includes_standard_fields(self):
        payload = json.loads(JsonFormatter().format(_record()))
        assert payload["level"] == "INFO"
        assert payload["logger"] == "test"
        assert payload["service"] == "manga-recs"
        assert "timestamp" in payload

    def test_carries_the_request_id_when_set(self):
        token = request_id_var.set("abc123")
        try:
            payload = json.loads(JsonFormatter().format(_record()))
        finally:
            request_id_var.reset(token)
        assert payload["request_id"] == "abc123"

    def test_omits_request_id_outside_a_request(self):
        assert "request_id" not in json.loads(JsonFormatter().format(_record()))

    def test_extra_fields_are_promoted_to_top_level(self):
        record = _record()
        record.event = "recommendation.hit"
        record.match_score = 91.5
        payload = json.loads(JsonFormatter().format(record))
        assert payload["event"] == "recommendation.hit"
        assert payload["match_score"] == 91.5

    def test_exceptions_are_serialised(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = _record(exc_info=sys.exc_info())
        payload = json.loads(JsonFormatter().format(record))
        assert "ValueError: boom" in payload["exception"]

    def test_non_serialisable_values_do_not_raise(self):
        record = _record()
        record.weird = object()
        # Logging must never be the thing that breaks a request.
        assert json.loads(JsonFormatter().format(record))["weird"]


class TestTracing:
    def test_span_without_an_exporter_is_a_no_op_not_an_error(self):
        configure_tracing(exporter="none")
        with span("test.span", **{"attr": "value"}):
            pass

    def test_exceptions_propagate_through_a_span(self):
        configure_tracing(exporter="none")
        with pytest.raises(ValueError, match="boom"):
            with span("test.span"):
                raise ValueError("boom")

    def test_none_attributes_are_skipped(self):
        # set_attribute rejects None, so the wrapper has to filter them.
        with span("test.span", present="yes", absent=None):
            pass


class TestMetricsEndpoint:
    def test_exposes_prometheus_text_format(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_counts_requests_and_records_latency(self, client):
        client.post("/recommendations/", json={"title": "berserk", "top_n": 2})
        body = client.get("/metrics").text
        assert "manga_recs_requests_total" in body
        assert "manga_recs_request_duration_seconds" in body
        assert "manga_recs_recommendation_duration_seconds" in body

    def test_records_match_score_distribution(self, client):
        client.post("/recommendations/", json={"title": "berserk"})
        assert "manga_recs_title_match_score" in client.get("/metrics").text

    def test_counts_misses_separately_from_errors(self, client):
        before = metrics_module.TITLE_NOT_FOUND._value.get()
        client.post("/recommendations/", json={"title": "qqqq zzzz nonexistent"})
        assert metrics_module.TITLE_NOT_FOUND._value.get() == before + 1

    def test_labels_use_the_route_template_not_the_raw_path(self, client):
        """Unbounded label values would flood the metrics backend."""
        client.get("/definitely-not-a-route-12345")
        body = client.get("/metrics").text
        assert "definitely-not-a-route-12345" not in body


class TestRequestCorrelation:
    def test_response_carries_a_request_id(self, client):
        response = client.post("/recommendations/", json={"title": "berserk"})
        assert response.headers["X-Request-ID"]

    def test_inbound_request_id_is_honoured(self, client):
        # Lets a trace survive across a proxy that already assigned an id.
        response = client.post(
            "/recommendations/",
            json={"title": "berserk"},
            headers={"X-Request-ID": "caller-supplied-id"},
        )
        assert response.headers["X-Request-ID"] == "caller-supplied-id"

    def test_ids_differ_between_requests(self, client):
        first = client.get("/health").headers["X-Request-ID"]
        second = client.get("/health").headers["X-Request-ID"]
        assert first != second

    def test_timing_header_is_still_present(self, client):
        response = client.post("/recommendations/", json={"title": "berserk"})
        assert float(response.headers["X-Response-Time-ms"]) >= 0
