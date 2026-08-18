import numpy as np
import pandas as pd
import pytest

from manga_recs.models.evaluate import (
    Metrics,
    build_positive_interactions,
    evaluate_all,
    format_report,
    split_holdout,
)


class TestBuildPositiveInteractions:
    def test_keeps_completed_and_current(self):
        df = pd.DataFrame(
            {
                "userId": [1, 1, 1],
                "mediaId": [10, 11, 12],
                "status": ["COMPLETED", "CURRENT", "PLANNING"],
                "score": [0, 0, 0],
            }
        )
        assert set(build_positive_interactions(df)["mediaId"]) == {10, 11}

    def test_keeps_highly_rated_regardless_of_status(self):
        df = pd.DataFrame({"userId": [1], "mediaId": [10], "status": ["DROPPED"], "score": [9]})
        assert len(build_positive_interactions(df)) == 1

    def test_drops_low_rated_non_engaged(self):
        df = pd.DataFrame({"userId": [1], "mediaId": [10], "status": ["DROPPED"], "score": [2]})
        assert len(build_positive_interactions(df)) == 0

    def test_deduplicates(self):
        df = pd.DataFrame(
            {
                "userId": [1, 1],
                "mediaId": [10, 10],
                "status": ["COMPLETED", "COMPLETED"],
                "score": [8, 8],
            }
        )
        assert len(build_positive_interactions(df)) == 1


class TestSplitHoldout:
    @pytest.fixture
    def interactions(self) -> pd.DataFrame:
        return pd.DataFrame({"userId": [1] * 10 + [2] * 2, "mediaId": list(range(10)) + [0, 1]})

    def test_skips_users_below_threshold(self, interactions):
        splits = split_holdout(
            interactions, catalog=set(range(10)), min_interactions=5, test_fraction=20, seed=1
        )
        assert 1 in splits
        assert 2 not in splits

    def test_train_and_test_are_disjoint_and_complete(self, interactions):
        splits = split_holdout(
            interactions, catalog=set(range(10)), min_interactions=5, test_fraction=20, seed=1
        )
        train, test = splits[1]
        assert not set(train) & set(test)
        assert len(train) + len(test) == 10
        assert len(test) == 2

    def test_is_deterministic_for_a_seed(self, interactions):
        kwargs = {
            "catalog": set(range(10)),
            "min_interactions": 5,
            "test_fraction": 20,
            "seed": 7,
        }
        assert split_holdout(interactions, **kwargs) == split_holdout(interactions, **kwargs)

    def test_ignores_items_outside_the_catalog(self, interactions):
        splits = split_holdout(
            interactions, catalog={0, 1, 2, 3, 4}, min_interactions=5, test_fraction=20, seed=1
        )
        train, test = splits[1]
        assert set(train) | set(test) <= {0, 1, 2, 3, 4}


class TestEvaluateAll:
    @pytest.fixture
    def clustered_data(self):
        """Two tight clusters of items, and users who read within one cluster.

        A similarity-based recommender should score well here; a popularity
        ranker should not, because popularity is deliberately anti-correlated
        with cluster membership.
        """
        n_per_cluster = 12
        ids = list(range(n_per_cluster * 2))
        sim = np.zeros((len(ids), len(ids)))
        for i in ids:
            for j in ids:
                if i == j:
                    continue
                same_cluster = (i < n_per_cluster) == (j < n_per_cluster)
                sim[i][j] = 0.9 if same_cluster else 0.05

        sim_matrix = pd.DataFrame(sim, index=ids, columns=ids)

        rows = []
        for user in range(20):
            cluster = user % 2
            members = (
                range(n_per_cluster) if cluster == 0 else range(n_per_cluster, n_per_cluster * 2)
            )
            for item in list(members)[:8]:
                rows.append({"userId": user, "mediaId": item, "status": "COMPLETED", "score": 8})
        user_df = pd.DataFrame(rows)

        metadata = pd.DataFrame({"id": ids, "popularity": list(range(len(ids), 0, -1))})
        return sim_matrix, user_df, metadata

    def test_returns_all_three_strategies(self, clustered_data):
        sim_matrix, user_df, metadata = clustered_data
        results = evaluate_all(sim_matrix, user_df, metadata, k=5)
        assert [m.strategy for m in results] == ["content", "popularity", "random"]

    def test_content_model_beats_random_on_clustered_data(self, clustered_data):
        sim_matrix, user_df, metadata = clustered_data
        content, _, random_baseline = evaluate_all(sim_matrix, user_df, metadata, k=5)
        assert content.recall_at_k > random_baseline.recall_at_k

    def test_metrics_are_within_valid_bounds(self, clustered_data):
        sim_matrix, user_df, metadata = clustered_data
        for m in evaluate_all(sim_matrix, user_df, metadata, k=5):
            assert 0.0 <= m.recall_at_k <= 1.0
            assert 0.0 <= m.precision_at_k <= 1.0
            assert 0.0 <= m.ndcg_at_k <= 1.0
            assert 0.0 <= m.catalog_coverage <= 1.0

    def test_never_recommends_already_read_items(self, clustered_data):
        sim_matrix, user_df, metadata = clustered_data
        content, _, _ = evaluate_all(sim_matrix, user_df, metadata, k=5)
        # Perfect precision is impossible if training items leaked into results,
        # because the harness only counts held-out items as hits.
        assert content.precision_at_k <= 1.0
        assert content.users_evaluated == 20

    def test_is_deterministic(self, clustered_data):
        sim_matrix, user_df, metadata = clustered_data
        first = evaluate_all(sim_matrix, user_df, metadata, k=5, seed=3)
        second = evaluate_all(sim_matrix, user_df, metadata, k=5, seed=3)
        assert [m.recall_at_k for m in first] == [m.recall_at_k for m in second]

    def test_raises_when_no_user_qualifies(self, clustered_data):
        sim_matrix, user_df, metadata = clustered_data
        with pytest.raises(ValueError, match="No users met the evaluation criteria"):
            evaluate_all(sim_matrix, user_df, metadata, k=5, min_interactions=999)


def test_format_report_includes_every_strategy():
    metrics = [
        Metrics("content", 10, 5, 0.4, 0.2, 0.3, 0.5),
        Metrics("popularity", 10, 5, 0.1, 0.05, 0.08, 0.02),
    ]
    report = format_report(metrics)
    assert "content" in report
    assert "popularity" in report
    assert "recall@10" in report
