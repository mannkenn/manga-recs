"""Retry behaviour of the AniList client.

These paths only fire when the upstream API misbehaves, which is exactly when
you cannot debug them interactively, so they are worth pinning down.
"""

import pytest
import requests

from manga_recs.data.utils import GraphQLQueryError, MangaGraphQLClient, RateLimiter

_UNSET = object()


class FakeResponse:
    def __init__(self, status_code=200, payload=_UNSET, text="", headers=None):
        self.status_code = status_code
        # `payload=None` means "body is not JSON"; omitting it means "valid body".
        self._payload = {"data": {"ok": True}} if payload is _UNSET else payload
        self.text = text or ""
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}", response=self)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("manga_recs.data.utils.time.sleep", lambda _: None)


@pytest.fixture
def client():
    return MangaGraphQLClient("https://example.test/graphql")


def _responses(client, monkeypatch, sequence):
    """Drive the client through a scripted sequence of responses or exceptions."""
    calls = {"n": 0}

    def fake_post(*args, **kwargs):
        item = sequence[min(calls["n"], len(sequence) - 1)]
        calls["n"] += 1
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(client.session, "post", fake_post)
    return calls


class TestTransportRetries:
    def test_read_timeout_is_retried_then_succeeds(self, client, monkeypatch):
        calls = _responses(client, monkeypatch, [requests.Timeout("timed out"), FakeResponse()])
        assert client.query("query {}") == {"ok": True}
        assert calls["n"] == 2

    def test_connection_error_is_retried(self, client, monkeypatch):
        calls = _responses(client, monkeypatch, [requests.ConnectionError("reset"), FakeResponse()])
        assert client.query("query {}") == {"ok": True}
        assert calls["n"] == 2

    def test_persistent_timeout_eventually_raises(self, client, monkeypatch):
        calls = _responses(client, monkeypatch, [requests.Timeout("timed out")])
        with pytest.raises(requests.Timeout):
            client.query("query {}", max_retries=3)
        assert calls["n"] == 3


class TestStatusRetries:
    def test_429_is_retried(self, client, monkeypatch):
        calls = _responses(client, monkeypatch, [FakeResponse(status_code=429), FakeResponse()])
        assert client.query("query {}") == {"ok": True}
        assert calls["n"] == 2

    def test_500_is_retried(self, client, monkeypatch):
        calls = _responses(client, monkeypatch, [FakeResponse(status_code=500), FakeResponse()])
        assert client.query("query {}") == {"ok": True}
        assert calls["n"] == 2

    def test_404_is_not_retried(self, client, monkeypatch):
        calls = _responses(client, monkeypatch, [FakeResponse(status_code=404, text="not found")])
        with pytest.raises(requests.HTTPError):
            client.query("query {}")
        assert calls["n"] == 1

    def test_retry_budget_is_respected(self, client, monkeypatch):
        calls = _responses(client, monkeypatch, [FakeResponse(status_code=500)])
        with pytest.raises(requests.HTTPError):
            client.query("query {}", max_retries=2)
        assert calls["n"] == 2


class TestGraphQLErrors:
    def test_graphql_errors_raise_typed_exception(self, client, monkeypatch):
        _responses(
            client,
            monkeypatch,
            [FakeResponse(payload={"errors": [{"message": "Private User"}]})],
        )
        with pytest.raises(GraphQLQueryError) as exc:
            client.query("query {}", max_retries=1)
        assert "Private User" in str(exc.value)

    def test_transient_graphql_error_is_retried(self, client, monkeypatch):
        calls = _responses(
            client,
            monkeypatch,
            [FakeResponse(payload={"errors": [{"message": "Too Many Requests"}]}), FakeResponse()],
        )
        assert client.query("query {}") == {"ok": True}
        assert calls["n"] == 2

    def test_non_json_response_raises(self, client, monkeypatch):
        _responses(client, monkeypatch, [FakeResponse(payload=None, text="<html>502</html>")])
        with pytest.raises(ValueError, match="Non-JSON response"):
            client.query("query {}")


class TestRetryDelay:
    def test_honours_retry_after_header(self, client):
        response = FakeResponse(headers={"Retry-After": "7"})
        assert client._retry_delay(response, attempt=1) == 7.0

    def test_falls_back_to_exponential_backoff(self, client):
        response = FakeResponse()
        assert client._retry_delay(response, attempt=1) == 2.0
        assert client._retry_delay(response, attempt=3) == 8.0

    def test_backoff_is_capped(self, client):
        assert client._retry_delay(FakeResponse(), attempt=20) == 60.0

    def test_ignores_unparseable_retry_after(self, client):
        response = FakeResponse(headers={"Retry-After": "soon"})
        assert client._retry_delay(response, attempt=1) == 2.0


def test_rate_limiter_spaces_calls(monkeypatch):
    slept: list[float] = []
    clock = {"t": 0.0}
    monkeypatch.setattr("manga_recs.data.utils.time.time", lambda: clock["t"])
    monkeypatch.setattr("manga_recs.data.utils.time.sleep", slept.append)

    limiter = RateLimiter(requests_per_minute=30)  # 2s apart
    limiter.wait()
    limiter.wait()

    assert slept and slept[-1] == pytest.approx(2.0)
