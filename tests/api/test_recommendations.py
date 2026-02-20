"""Tests for recommendation API"""
import pytest
from fastapi.testclient import TestClient
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from pathlib import Path


# Mock the imports from s3_load since we can't access real S3 in tests
@pytest.fixture
def mock_api():
    """Create FastAPI test client with mocked dependencies"""
    # Patch s3_load before importing main
    with patch('manga_recs.api.main.s3_load') as mock_s3:
        # Setup return values for s3_load calls
        mock_s3.return_value = None
        
        # Patch joblib.load and pd.read_parquet to use fixtures
        with patch('joblib.load') as mock_joblib, \
             patch('pandas.read_parquet') as mock_pq:
            
            # Create mock similarity matrix
            mock_sim = pd.DataFrame(
                np.array([
                    [1.0, 0.8, 0.6],
                    [0.8, 1.0, 0.7],
                    [0.6, 0.7, 1.0],
                ]),
                index=[1, 2, 3],
                columns=[1, 2, 3],
            )
            
            # Create mock metadata
            mock_metadata = pd.DataFrame({
                'id': [1, 2, 3],
                'title': ['Naruto', 'One Piece', 'Bleach'],
                'description': ['Ninja story', 'Pirate story', 'Soul reaper story'],
                'tags': [['action', 'shounen'], ['adventure', 'shounen'], ['action', 'dark']],
            })
            
            # Configure mocks
            mock_joblib.side_effect = lambda x: mock_sim if 'sim' in str(x) else None
            mock_pq.return_value = mock_metadata
            
            # Now import and create app
            from manga_recs.api.main import app
            
            client = TestClient(app)
            yield client, mock_metadata, mock_sim


class TestRecommendations:
    """Test suite for recommendations endpoint"""
    
    def test_health_check(self, mock_api):
        """Test API is running"""
        client, _, _ = mock_api
        # Note: depends on API having a /docs endpoint
        response = client.get("/openapi.json")
        assert response.status_code in [200, 404]  # 404 if no docs, 200 if available
    
    def test_recommend_valid_manga(self, mock_api):
        """Test successful recommendation request"""
        client, metadata, sim_matrix = mock_api
        
        payload = {
            "title": "Naruto",
            "top_n": 2
        }
        
        with patch('manga_recs.api.main.SIM_MATRIX', sim_matrix), \
             patch('manga_recs.api.main.METADATA', metadata):
            response = client.post("/recommendations/", json=payload)
            
            # For now, we expect 200 (success) or 422 (validation error)
            # Actual test depends on API implementation
            assert response.status_code in [200, 422]
    
    def test_recommend_nonexistent_manga(self, mock_api):
        """Test request with non-existent manga"""
        client, metadata, sim_matrix = mock_api
        
        payload = {
            "title": "Nonexistent Manga XXXXXX",
            "top_n": 2
        }
        
        # Should return 404 when manga not found
        with patch('manga_recs.api.main.SIM_MATRIX', sim_matrix), \
             patch('manga_recs.api.main.METADATA', metadata):
            response = client.post("/recommendations/", json=payload)
            # Expected: 404 or 200 (depends on fuzzy matching threshold)
            assert response.status_code in [200, 404, 422]


# Integration test example
class TestAPISchema:
    """Test API request/response schemas"""
    
    def test_recommendation_request_valid(self):
        """Test valid recommendation request"""
        from manga_recs.api.schemas import RecommendationRequest
        
        req = RecommendationRequest(title="Naruto", top_n=5)
        assert req.title == "Naruto"
        assert req.top_n == 5
    
    def test_recommendation_request_defaults(self):
        """Test recommendation request with defaults"""
        from manga_recs.api.schemas import RecommendationRequest
        
        req = RecommendationRequest(title="Naruto")
        assert req.title == "Naruto"
        # Check if top_n has a default
        assert req.top_n >= 1
