"""pytest fixtures and shared test config"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path


@pytest.fixture
def sample_metadata():
    """Sample manga metadata for testing"""
    return pd.DataFrame({
        'id': [1, 2, 3],
        'title': ['Naruto', 'One Piece', 'Bleach'],
        'description': ['Ninja story', 'Pirate story', 'Soul reaper story'],
        'tags': [['action', 'shounen'], ['adventure', 'shounen'], ['action', 'dark']],
    })


@pytest.fixture
def sample_similarity_matrix(sample_metadata):
    """Sample similarity matrix for testing"""
    df = pd.DataFrame(
        np.array([
            [1.0, 0.8, 0.6],
            [0.8, 1.0, 0.7],
            [0.6, 0.7, 1.0],
        ]),
        index=sample_metadata['id'],
        columns=sample_metadata['id'],
    )
    return df


@pytest.fixture
def recommendation_request():
    """Sample recommendation request"""
    return {
        "title": "Naruto",
        "top_n": 2
    }
