import pandas as pd
import pytest

from manga_recs.data.quality import DataQualityError, check_frame


@pytest.fixture
def frame() -> pd.DataFrame:
    return pd.DataFrame({"id": [1, 2, 3], "title": ["a", "b", "c"]})


def test_passing_frame_is_returned_unchanged(frame):
    result = check_frame(frame, "items", required_columns=("id", "title"), unique_columns=("id",))
    pd.testing.assert_frame_equal(result, frame)


def test_empty_frame_is_rejected():
    with pytest.raises(DataQualityError, match="at least 1 rows"):
        check_frame(pd.DataFrame({"id": []}), "items")


def test_missing_column_is_reported():
    with pytest.raises(DataQualityError, match="missing required columns"):
        check_frame(pd.DataFrame({"id": [1]}), "items", required_columns=("id", "title"))


def test_nulls_in_key_column_are_reported():
    df = pd.DataFrame({"id": [1, None, 3]})
    with pytest.raises(DataQualityError, match="null values"):
        check_frame(df, "items", non_null_columns=("id",))


def test_duplicates_are_reported():
    df = pd.DataFrame({"id": [1, 1, 2]})
    with pytest.raises(DataQualityError, match="duplicate values"):
        check_frame(df, "items", unique_columns=("id",))


def test_all_problems_reported_together():
    df = pd.DataFrame({"id": [1, 1]})
    with pytest.raises(DataQualityError) as exc:
        check_frame(df, "items", required_columns=("title",), unique_columns=("id",))

    message = str(exc.value)
    assert "missing required columns" in message
    assert "duplicate values" in message
