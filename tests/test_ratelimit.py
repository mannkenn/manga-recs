"""Tests for the public endpoint's abuse protection."""

from __future__ import annotations

import dataclasses
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from manga_recs.api.ratelimit import SlidingWindowLimiter, client_key


def make_request(host="1.2.3.4", forwarded=None):
    headers = {"X-Forwarded-For": forwarded} if forwarded else {}
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=host))


@pytest.fixture
def api_settings(monkeypatch):
    """Override [api] settings, which are frozen dataclasses.

    Patches every module that holds a reference, since `settings` is bound at
    import time in some places and looked up lazily in others.
    """
    import sys

    from manga_recs.api import main

    # manga_recs.common re-exports the `settings` instance, which shadows the
    # submodule of the same name on the package, so go through sys.modules.
    settings_module = sys.modules["manga_recs.common.settings"]

    def override(**changes):
        base = settings_module.settings
        patched = dataclasses.replace(base, api=dataclasses.replace(base.api, **changes))
        monkeypatch.setattr(settings_module, "settings", patched)
        monkeypatch.setattr(main, "settings", patched)
        return patched

    return override


class TestSlidingWindowLimiter:
    def test_allows_up_to_the_limit(self):
        limiter = SlidingWindowLimiter(limit=3, window_seconds=60)
        assert [limiter.check("a", now=0).allowed for _ in range(3)] == [True] * 3

    def test_rejects_past_the_limit(self):
        limiter = SlidingWindowLimiter(limit=3, window_seconds=60)
        for _ in range(3):
            limiter.check("a", now=0)
        assert limiter.check("a", now=0).allowed is False

    def test_remaining_counts_down(self):
        limiter = SlidingWindowLimiter(limit=3, window_seconds=60)
        assert [limiter.check("a", now=0).remaining for _ in range(3)] == [2, 1, 0]

    def test_clients_have_independent_budgets(self):
        limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
        assert limiter.check("a", now=0).allowed
        assert limiter.check("b", now=0).allowed

    def test_window_slides_rather_than_resetting(self):
        """A fixed window would let a caller send 2x the limit across a boundary."""
        limiter = SlidingWindowLimiter(limit=2, window_seconds=60)
        limiter.check("a", now=0)
        limiter.check("a", now=30)
        assert limiter.check("a", now=59).allowed is False
        # The 0s hit ages out at 60, freeing exactly one slot; the 30s hit does not.
        assert limiter.check("a", now=61).allowed is True
        assert limiter.check("a", now=61).allowed is False

    def test_retry_after_points_past_the_oldest_hit(self):
        limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
        limiter.check("a", now=0)
        decision = limiter.check("a", now=10)
        assert 1 <= decision.retry_after <= 61

    def test_retry_after_is_never_zero(self):
        """A Retry-After of 0 invites an immediate retry, which cannot succeed."""
        limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
        limiter.check("a", now=0)
        assert limiter.check("a", now=59.999).retry_after >= 1

    def test_client_table_is_bounded(self):
        """Otherwise a caller cycling addresses turns a rate limit into an OOM."""
        limiter = SlidingWindowLimiter(limit=5, window_seconds=60, max_clients=10)
        for i in range(500):
            limiter.check(f"client-{i}", now=0)
        assert len(limiter._hits) <= 10

    def test_eviction_drops_the_least_recently_seen(self):
        limiter = SlidingWindowLimiter(limit=5, window_seconds=60, max_clients=2)
        limiter.check("old", now=0)
        limiter.check("mid", now=1)
        limiter.check("new", now=2)
        assert "old" not in limiter._hits
        assert "new" in limiter._hits

    def test_rejects_a_nonsensical_limit(self):
        with pytest.raises(ValueError):
            SlidingWindowLimiter(limit=0, window_seconds=60)

    def test_is_thread_safe(self):
        """Handlers run in a threadpool, so the counter is reachable concurrently."""
        limiter = SlidingWindowLimiter(limit=1000, window_seconds=60)
        allowed = []

        def hammer():
            for _ in range(100):
                allowed.append(limiter.check("shared").allowed)

        threads = [threading.Thread(target=hammer) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(allowed) == 1000


class TestClientKey:
    def test_uses_the_socket_address_by_default(self, api_settings):
        api_settings(trust_forwarded_for=False)
        assert client_key(make_request(host="9.9.9.9", forwarded="1.1.1.1")) == "9.9.9.9"

    def test_ignoring_forwarded_for_prevents_a_header_bypass(self, api_settings):
        """If the header were trusted unconditionally, varying it would reset the
        budget on every request."""
        api_settings(trust_forwarded_for=False)
        keys = {client_key(make_request(host="9.9.9.9", forwarded=f"1.1.1.{i}")) for i in range(50)}
        assert keys == {"9.9.9.9"}

    def test_honours_forwarded_for_when_configured(self, api_settings):
        api_settings(trust_forwarded_for=True)
        assert client_key(make_request(host="10.0.0.1", forwarded="1.1.1.1")) == "1.1.1.1"

    def test_takes_the_original_client_from_a_proxy_chain(self, api_settings):
        api_settings(trust_forwarded_for=True)
        request = make_request(host="10.0.0.1", forwarded="1.1.1.1, 10.0.0.5, 10.0.0.6")
        assert client_key(request) == "1.1.1.1"

    def test_survives_a_missing_client(self, api_settings):
        api_settings(trust_forwarded_for=False)
        assert client_key(SimpleNamespace(headers={}, client=None)) == "unknown"


class TestEndpointEnforcement:
    @pytest.fixture
    def client(self, monkeypatch, api_settings):
        from manga_recs.api import main

        api_settings(rate_limit_enabled=True)
        monkeypatch.setattr(main, "_limiter", SlidingWindowLimiter(limit=3, window_seconds=60))
        with TestClient(main.app) as test_client:
            yield test_client

    def test_returns_429_once_over_budget(self, client):
        payload = {"title": "berserk"}
        statuses = [client.post("/recommendations/", json=payload).status_code for _ in range(5)]
        assert statuses[-1] == 429

    def test_429_carries_retry_after(self, client):
        payload = {"title": "berserk"}
        for _ in range(4):
            response = client.post("/recommendations/", json=payload)
        assert response.status_code == 429
        assert int(response.headers["Retry-After"]) >= 1

    def test_health_is_never_throttled(self, client):
        """A probe hitting a 429 would take the container down for the wrong reason."""
        for _ in range(10):
            client.post("/recommendations/", json={"title": "berserk"})
        assert client.get("/health").status_code == 200

    def test_throttled_requests_still_carry_a_correlation_id(self, client):
        for _ in range(4):
            response = client.post("/recommendations/", json={"title": "berserk"})
        assert response.status_code == 429
        assert response.headers["X-Request-ID"]

    def test_throttled_requests_are_counted(self, client):
        for _ in range(4):
            client.post("/recommendations/", json={"title": "berserk"})
        body = client.get("/metrics").text
        assert "manga_recs_rate_limited_total" in body
        assert 'status="429"' in body

    def test_throttled_requests_keep_their_route_label(self, client):
        """Rejection happens before routing, so the route has to be resolved
        explicitly - otherwise every 429 lands in an 'unmatched' bucket and the
        metric cannot say which endpoint is being hammered."""
        for _ in range(4):
            client.post("/recommendations/", json={"title": "berserk"})
        body = client.get("/metrics").text
        assert 'route="/recommendations/",status="429"' in body
        assert 'route="unmatched",status="429"' not in body

    def test_disabling_the_limiter_lets_everything_through(self, monkeypatch, api_settings):
        from manga_recs.api import main

        api_settings(rate_limit_enabled=False)
        monkeypatch.setattr(main, "_limiter", SlidingWindowLimiter(limit=1, window_seconds=60))
        with TestClient(main.app) as client:
            statuses = [
                client.post("/recommendations/", json={"title": "berserk"}).status_code
                for _ in range(5)
            ]
        assert 429 not in statuses
