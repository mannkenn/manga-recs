"""Shared test fixtures and configuration for pytest."""
import pytest
import pandas as pd
from pathlib import Path


@pytest.fixture
def sample_manga_data():
    """Sample manga metadata for testing."""
    return [
        {
            "id": 1,
            "title": {"romaji": "Test Manga 1"},
            "genres": ["Action", "Adventure"],
            "popularity": 1000,
            "averageScore": 85,
        },
        {
            "id": 2,
            "title": {"romaji": "Test Manga 2"},
            "genres": ["Romance", "Drama"],
            "popularity": 500,
            "averageScore": 75,
        },
    ]


@pytest.fixture
def sample_user_data():
    """Sample user read data for testing."""
    return [
        {
            "userId": 1,
            "mediaId": 1,
            "status": "COMPLETED",
            "score": 9,
            "progress": 10,
            "createdAt": 1609459200,
        },
        {
            "userId": 1,
            "mediaId": 2,
            "status": "READING",
            "score": 7,
            "progress": 5,
            "createdAt": 1609545600,
        },
    ]


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory structure."""
    data_dir = tmp_path / "data"
    (data_dir / "raw").mkdir(parents=True)
    (data_dir / "cleaned").mkdir(parents=True)
    (data_dir / "features").mkdir(parents=True)
    (data_dir / "models").mkdir(parents=True)
    return data_dir


@pytest.fixture
def mock_graphql_client(mocker):
    """Mock GraphQL client for testing."""
    return mocker.Mock()
