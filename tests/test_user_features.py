"""Tests for the graded user-item interaction table.

Every bug this guards against failed silently rather than raising: a zeroed
score, an unmapped status, a mis-scaled rating. None of them would have shown up
as an error, only as a quietly worse metric.
"""

from __future__ import annotations

import pandas as pd
import pytest

from manga_recs.data.transform.feature_engineering import create_user_features
from manga_recs.models.evaluate import (
    POSITIVE_STRENGTH_THRESHOLD,
    build_positive_interactions,
)


def reads(*rows):
    """Build a cleaned read-list frame from (status, score) pairs."""
    return pd.DataFrame(
        {
            "userId": [1] * len(rows),
            "mediaId": list(range(100, 100 + len(rows))),
            "status": [status for status, _ in rows],
            "score": [score for _, score in rows],
            "createdAt": [0] * len(rows),
            "progress": [None] * len(rows),
        }
    )


class TestInteractionStrength:
    def test_unrated_completion_is_not_zero(self):
        """The original bug: score 0 means unrated, and multiplying by it
        made a finished-but-unrated title look like no interaction at all."""
        df = create_user_features(reads(("COMPLETED", 0), ("COMPLETED", 80)))
        assert df["interaction_strength"].iloc[0] > 0

    def test_unrated_is_imputed_to_the_median_rating(self):
        df = create_user_features(reads(("COMPLETED", 40), ("COMPLETED", 60), ("COMPLETED", 0)))
        # Median of the rated entries is 0.5, and COMPLETED weighs 1.0.
        assert df["interaction_strength"].iloc[2] == pytest.approx(0.5)

    def test_repeating_is_weighted_rather_than_dropped(self):
        """REPEATING was absent from the status map and became NaN."""
        df = create_user_features(reads(("REPEATING", 80)))
        assert df["interaction_strength"].notna().all()
        assert df["interaction_strength"].iloc[0] == pytest.approx(0.8)

    def test_unknown_status_warns_and_survives(self, caplog):
        df = create_user_features(reads(("SOMETHING_NEW", 80)))
        assert df["interaction_strength"].notna().all()
        assert "SOMETHING_NEW" in caplog.text

    def test_strength_stays_within_unit_range(self):
        df = create_user_features(
            reads(("COMPLETED", 100), ("DROPPED", 100), ("PLANNING", 0), ("CURRENT", 50))
        )
        assert df["interaction_strength"].between(0.0, 1.0).all()

    def test_status_ordering_is_preserved_at_equal_scores(self):
        df = create_user_features(
            reads(("COMPLETED", 80), ("CURRENT", 80), ("PAUSED", 80), ("DROPPED", 80))
        )
        strengths = df["interaction_strength"].tolist()
        assert strengths == sorted(strengths, reverse=True)

    def test_a_disliked_completion_ranks_below_a_liked_one(self):
        df = create_user_features(reads(("COMPLETED", 20), ("COMPLETED", 95)))
        assert df["interaction_strength"].iloc[0] < df["interaction_strength"].iloc[1]

    def test_all_unrated_does_not_divide_by_zero(self):
        df = create_user_features(reads(("COMPLETED", 0), ("DROPPED", 0)))
        assert df["interaction_strength"].notna().all()

    def test_case_insensitive_status(self):
        lower = create_user_features(reads(("completed", 80)))
        upper = create_user_features(reads(("COMPLETED", 80)))
        assert lower["interaction_strength"].iloc[0] == upper["interaction_strength"].iloc[0]

    def test_optional_columns_may_be_absent(self):
        df = reads(("COMPLETED", 80)).drop(columns=["createdAt", "progress"])
        assert create_user_features(df)["interaction_strength"].iloc[0] > 0

    def test_input_frame_is_not_mutated(self):
        original = reads(("COMPLETED", 80))
        before = original.copy()
        create_user_features(original)
        pd.testing.assert_frame_equal(original, before)


class TestScoreScaleNormalisation:
    def test_a_ten_point_partition_is_rescaled_not_crushed(self):
        """A pre-POINT_100 partition tops out at 10. Dividing it by 100 would
        make a perfect score look like a 0.1."""
        df = create_user_features(reads(("COMPLETED", 9), ("COMPLETED", 10)))
        assert df["interaction_strength"].iloc[1] == pytest.approx(1.0)

    def test_a_hundred_point_partition_is_divided_by_a_hundred(self):
        df = create_user_features(reads(("COMPLETED", 50), ("COMPLETED", 100)))
        assert df["interaction_strength"].iloc[0] == pytest.approx(0.5)

    def test_rescaling_warns_so_a_stale_partition_is_visible(self, caplog):
        create_user_features(reads(("COMPLETED", 9), ("COMPLETED", 10)))
        assert "POINT_100" in caplog.text


class TestPositiveInteractions:
    def test_threshold_admits_engaged_titles(self):
        df = reads(("COMPLETED", 90), ("CURRENT", 80))
        assert len(build_positive_interactions(df)) == 2

    def test_threshold_excludes_dropped_and_planning(self):
        df = reads(("COMPLETED", 90), ("DROPPED", 90), ("PLANNING", 90))
        positives = build_positive_interactions(df)
        assert positives["mediaId"].tolist() == [100]

    def test_a_low_rated_completion_is_not_a_positive(self):
        """The old rule counted every COMPLETED title regardless of rating."""
        df = reads(("COMPLETED", 90), ("COMPLETED", 10))
        assert build_positive_interactions(df)["mediaId"].tolist() == [100]

    def test_accepts_an_already_featurised_frame(self):
        """The evaluation reads the published artifact; it must not re-derive."""
        raw = reads(("COMPLETED", 90), ("DROPPED", 10))
        from_raw = build_positive_interactions(raw)
        from_features = build_positive_interactions(create_user_features(raw))
        pd.testing.assert_frame_equal(
            from_raw.reset_index(drop=True), from_features.reset_index(drop=True)
        )

    def test_duplicate_pairs_collapse(self):
        df = reads(("COMPLETED", 90), ("COMPLETED", 90))
        df["mediaId"] = [100, 100]
        assert len(build_positive_interactions(df)) == 1

    def test_threshold_is_the_documented_boundary(self):
        assert 0.0 < POSITIVE_STRENGTH_THRESHOLD < 1.0
