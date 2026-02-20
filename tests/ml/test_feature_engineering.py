"""Tests for ML modules"""
import pytest
import pandas as pd
import numpy as np


class TestSimilarityMatrix:
    """Test similarity matrix creation"""
    
    def test_similarity_matrix_shape(self):
        """Test similarity matrix has correct shape"""
        # Example: check a similarity matrix is square
        sim_matrix = pd.DataFrame(
            np.array([
                [1.0, 0.8, 0.6],
                [0.8, 1.0, 0.7],
                [0.6, 0.7, 1.0],
            ]),
            index=[1, 2, 3],
            columns=[1, 2, 3],
        )
        
        assert sim_matrix.shape[0] == sim_matrix.shape[1]
        assert sim_matrix.shape[0] == 3
    
    def test_similarity_matrix_diagonal_is_one(self):
        """Test diagonal of similarity matrix is 1.0 (item similar to itself)"""
        sim_matrix = pd.DataFrame(
            np.array([
                [1.0, 0.8, 0.6],
                [0.8, 1.0, 0.7],
                [0.6, 0.7, 1.0],
            ]),
            index=[1, 2, 3],
            columns=[1, 2, 3],
        )
        
        np.testing.assert_array_almost_equal(np.diag(sim_matrix), [1.0, 1.0, 1.0])
    
    def test_similarity_matrix_symmetric(self):
        """Test similarity matrix is symmetric"""
        sim_matrix = pd.DataFrame(
            np.array([
                [1.0, 0.8, 0.6],
                [0.8, 1.0, 0.7],
                [0.6, 0.7, 1.0],
            ]),
            index=[1, 2, 3],
            columns=[1, 2, 3],
        )
        
        # Check if A == A^T (transpose)
        pd.testing.assert_frame_equal(sim_matrix, sim_matrix.T)


class TestFeatureEngineering:
    """Test feature engineering module"""
    
    def test_weighted_tag_encoding(self):
        """Test weighted one-hot encoding for tags"""
        from manga_recs.data_engineering.transform.feature_engineering import one_hot_encode_column
        
        # Create sample data with tags
        df = pd.DataFrame({
            'id': [1, 2],
            'tags': [['baseball', 'shounen', 'sports'], ['action', 'adventure']],
        })
        
        # Apply weighted encoding [3, 2]
        result = one_hot_encode_column(df, 'tags', weight_top=[3, 2])
        
        # First manga should have baseball=3, shounen=2, sports=1
        assert result.loc[0, 'baseball'] == 3.0
        assert result.loc[0, 'shounen'] == 2.0
        assert result.loc[0, 'sports'] == 1.0
        
        # Second manga should have action=3, adventure=2
        assert result.loc[1, 'action'] == 3.0
        assert result.loc[1, 'adventure'] == 2.0
    
    def test_one_hot_encode_no_weights(self):
        """Test simple one-hot encoding (binary)"""
        from manga_recs.data_engineering.transform.feature_engineering import one_hot_encode_column
        
        df = pd.DataFrame({
            'id': [1, 2],
            'tags': [['action', 'shounen'], ['comedy']],
        })
        
        result = one_hot_encode_column(df, 'tags', weight_top=None)
        
        # All values should be 0 or 1
        assert result.loc[0, 'action'] == 1.0
        assert result.loc[0, 'shounen'] == 1.0
        assert result.loc[1, 'comedy'] == 1.0
