"""Unit tests for GraphQL client utilities."""
import pytest
from unittest.mock import Mock, patch
from manga_recs.data_engineering.utils import MangaGraphQLClient, RateLimiter
import time


class TestMangaGraphQLClient:
    """Tests for MangaGraphQLClient class."""

    def test_client_initialization(self):
        """Test client initialization."""
        client = MangaGraphQLClient("https://graphql.anilist.co")
        assert client.url == "https://graphql.anilist.co"
        assert client.timeout == 10

    def test_client_strips_trailing_slash(self):
        """Test that trailing slash is removed from URL."""
        client = MangaGraphQLClient("https://graphql.anilist.co/")
        assert client.url == "https://graphql.anilist.co"

    @patch('manga_recs.data_engineering.utils.requests.Session.post')
    def test_successful_query(self, mock_post):
        """Test successful GraphQL query."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"Page": {"mediaList": []}}}
        mock_post.return_value = mock_response

        client = MangaGraphQLClient("https://graphql.anilist.co")
        result = client.query("query { Page { mediaList } }")

        assert result == {"Page": {"mediaList": []}}
        mock_post.assert_called_once()


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(requests_per_minute=30)
        assert limiter.requests_per_minute == 30

    def test_rate_limiter_wait(self):
        """Test that wait method enforces delay."""
        limiter = RateLimiter(requests_per_minute=120)  # 2 per second
        
        start = time.time()
        limiter.wait()
        limiter.wait()
        elapsed = time.time() - start
        
        # Should have waited at least 0.5 seconds for the second call
        assert elapsed >= 0.4  # Allow small margin
