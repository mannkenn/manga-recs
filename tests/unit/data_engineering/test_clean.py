"""Unit tests for data cleaning functions."""
import pytest
import pandas as pd
from manga_recs.data_engineering.transform.clean import (
    clean_manga_metadata,
    clean_user_readdata,
)


class TestCleanMangaMetadata:
    """Tests for clean_manga_metadata function."""

    def test_clean_manga_metadata_basic(self, sample_manga_data):
        """Test basic manga metadata cleaning."""
        result = clean_manga_metadata(sample_manga_data)
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "id" in result.columns
        assert "title" in result.columns

    def test_clean_manga_metadata_empty_list(self):
        """Test cleaning with empty input."""
        result = clean_manga_metadata([])
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


class TestCleanUserReadData:
    """Tests for clean_user_readdata function."""

    def test_clean_user_readdata_basic(self, sample_user_data):
        """Test basic user read data cleaning."""
        result = clean_user_readdata(sample_user_data)
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "userId" in result.columns
        assert "mediaId" in result.columns
        assert "status" in result.columns

    def test_clean_user_readdata_types(self, sample_user_data):
        """Test that data types are correctly converted."""
        result = clean_user_readdata(sample_user_data)
        
        assert result["userId"].dtype == "int64"
        assert result["mediaId"].dtype == "int64"
        assert result["status"].dtype == "string"

    def test_clean_user_readdata_removes_null_ids(self, sample_user_data):
        """Test that rows with null user/media IDs are removed."""
        # Add a record with null mediaId
        data_with_null = sample_user_data + [
            {"userId": 2, "mediaId": None, "status": "COMPLETED", "score": 8}
        ]
        result = clean_user_readdata(data_with_null)
        
        # Should only have 2 valid records
        assert len(result) == 2
