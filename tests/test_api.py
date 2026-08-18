import pytest
from fastapi.testclient import TestClient

from manga_recs.api import main as api_main
from manga_recs.serving.recommender import Recommender


@pytest.fixture
def client(monkeypatch, similarity_matrix, catalog_metadata) -> TestClient:
    """Client backed by an in-memory model, so no object store is involved."""
    recommender = Recommender(similarity_matrix, catalog_metadata, fuzzy_threshold=70)
    monkeypatch.setattr(api_main, "get_recommender", lambda: recommender)
    with TestClient(api_main.app) as test_client:
        yield test_client


@pytest.fixture
def broken_client(monkeypatch) -> TestClient:
    """Client where artifacts cannot be loaded at all."""

    def explode():
        raise RuntimeError("object store unreachable")

    monkeypatch.setattr(api_main, "get_recommender", explode)
    with TestClient(api_main.app) as test_client:
        yield test_client


class TestHealth:
    def test_reports_ok_and_item_count(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert body["model_loaded"] is True
        assert body["items"] == 4

    def test_reports_which_artifact_source_answered(self, client):
        # A deployed instance has to be able to prove whether it is serving the
        # artifacts baked into its image or something fetched at runtime.
        assert client.get("/health").json()["artifact_source"] == "memory"

    def test_reports_degraded_when_model_missing(self, broken_client):
        response = broken_client.get("/health")
        # Still 200: the process is alive and should say it is unhealthy rather
        # than fail the platform's liveness probe and get restarted forever.
        assert response.status_code == 200

        body = response.json()
        assert body["status"] == "degraded"
        assert body["model_loaded"] is False
        assert body["items"] is None
        # The reason has to reach the operator, not just the logs.
        assert "object store unreachable" in body["detail"]


class TestRecommendations:
    def test_returns_recommendations(self, client):
        response = client.post("/recommendations/", json={"title": "berserk", "top_n": 2})
        assert response.status_code == 200

        body = response.json()
        assert body["title"] == "berserk"
        assert body["matched_title"] == "berserk"
        assert len(body["recommendations"]) == 2
        assert body["recommendations"][0]["id"] == 2

    def test_surfaces_the_fuzzy_matched_title(self, client):
        body = client.post("/recommendations/", json={"title": "bersrek"}).json()
        assert body["matched_title"] == "berserk"
        assert body["match_score"] < 100

    def test_unknown_title_is_404(self, client):
        response = client.post("/recommendations/", json={"title": "qqqq zzzz nonexistent"})
        assert response.status_code == 404

    def test_missing_model_is_503(self, broken_client):
        response = broken_client.post("/recommendations/", json={"title": "berserk"})
        assert response.status_code == 503

    @pytest.mark.parametrize(
        "payload",
        [
            {},  # no title
            {"title": ""},  # empty title
            {"title": "berserk", "top_n": 0},  # below minimum
            {"title": "berserk", "top_n": 1000},  # above maximum
        ],
    )
    def test_invalid_payloads_are_rejected(self, client, payload):
        assert client.post("/recommendations/", json=payload).status_code == 422

    def test_response_includes_timing_header(self, client):
        response = client.post("/recommendations/", json={"title": "berserk"})
        assert "X-Response-Time-ms" in response.headers
