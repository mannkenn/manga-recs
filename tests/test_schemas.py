"""Tests for the request contract.

These exist because of a silent failure: the browser client sent `topN`, the
model declared `top_n`, and Pydantic dropped the unrecognised key and used the
default. Every request returned five results no matter what was asked for, and
nothing anywhere raised.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from manga_recs.api.main import app
from manga_recs.api.schemas import RecommendationRequest


class TestRecommendationRequest:
    def test_accepts_camel_case_from_the_browser(self):
        assert RecommendationRequest(title="berserk", topN=3).top_n == 3

    def test_accepts_snake_case_from_curl_and_python(self):
        assert RecommendationRequest(title="berserk", top_n=3).top_n == 3

    def test_defaults_when_omitted(self):
        assert RecommendationRequest(title="berserk").top_n == 5

    def test_an_unrecognised_field_is_rejected_rather_than_ignored(self):
        """The whole bug was a dropped key. Silence is the failure mode."""
        with pytest.raises(ValidationError):
            RecommendationRequest(title="berserk", top_nn=3)

    @pytest.mark.parametrize("value", [0, -1, 51])
    def test_out_of_range_counts_are_rejected(self, value):
        with pytest.raises(ValidationError):
            RecommendationRequest(title="berserk", topN=value)

    def test_blank_title_is_rejected(self):
        with pytest.raises(ValidationError):
            RecommendationRequest(title="")


class TestEndpointHonoursTheCount:
    @pytest.fixture
    def client(self):
        with TestClient(app) as test_client:
            yield test_client

    @pytest.mark.parametrize("requested", [1, 3, 7])
    def test_camel_case_count_is_honoured(self, client, requested):
        response = client.post("/recommendations/", json={"title": "berserk", "topN": requested})
        assert response.status_code == 200
        assert len(response.json()["recommendations"]) == requested

    def test_snake_case_count_is_honoured(self, client):
        response = client.post("/recommendations/", json={"title": "berserk", "top_n": 2})
        assert response.status_code == 200
        assert len(response.json()["recommendations"]) == 2

    def test_a_misspelled_field_returns_422(self, client):
        response = client.post("/recommendations/", json={"title": "berserk", "topn": 3})
        assert response.status_code == 422

    def test_the_query_itself_is_never_recommended_back(self, client):
        body = client.post("/recommendations/", json={"title": "berserk", "topN": 5}).json()
        titles = [r["title"] for r in body["recommendations"]]
        assert body["matched_title"] not in titles

    def test_results_are_ordered_by_descending_similarity(self, client):
        body = client.post("/recommendations/", json={"title": "berserk", "topN": 10}).json()
        scores = [r["similarity"] for r in body["recommendations"]]
        assert scores == sorted(scores, reverse=True)
