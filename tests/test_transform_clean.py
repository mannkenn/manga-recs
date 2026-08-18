import pandas as pd
import pytest

from manga_recs.data.quality import DataQualityError, check_frame
from manga_recs.data.transform.clean import (
    clean_description,
    clean_manga_metadata,
    clean_user_readdata,
    extract_english_title,
    extract_search_titles,
    extract_tag_names,
    has_end_date,
    parse_date_to_datetime,
)


class TestExtractEnglishTitle:
    def test_prefers_english(self):
        assert extract_english_title({"english": "Berserk", "romaji": "Beruseruku"}) == "berserk"

    def test_falls_back_to_romaji_then_native(self):
        assert extract_english_title({"english": None, "romaji": "Vagabond"}) == "vagabond"
        assert (
            extract_english_title({"english": None, "romaji": None, "native": "ベルセルク"})
            == "ベルセルク"
        )

    def test_handles_plain_string_and_missing(self):
        assert extract_english_title("Naruto") == "naruto"
        assert extract_english_title(None) is None
        assert extract_english_title({"english": None, "romaji": None, "native": None}) is None


class TestExtractSearchTitles:
    def test_keeps_every_variant(self):
        title = {
            "english": "Goodnight Punpun",
            "romaji": "Oyasumi Punpun",
            "native": "おやすみプンプン",
        }
        assert extract_search_titles(title) == [
            "goodnight punpun",
            "oyasumi punpun",
            "おやすみプンプン",
        ]

    def test_skips_missing_variants(self):
        assert extract_search_titles({"english": None, "romaji": "Vagabond", "native": None}) == [
            "vagabond"
        ]

    def test_deduplicates_identical_variants(self):
        title = {"english": "Berserk", "romaji": "Berserk", "native": "ベルセルク"}
        assert extract_search_titles(title) == ["berserk", "ベルセルク"]

    def test_handles_bare_string_and_junk(self):
        assert extract_search_titles("Naruto") == ["naruto"]
        assert extract_search_titles(None) == []
        assert extract_search_titles({"english": "   "}) == []


class TestExtractTagNames:
    def test_extracts_and_lowercases(self):
        assert extract_tag_names([{"name": "Dark Fantasy"}, {"name": "Gore"}]) == [
            "dark fantasy",
            "gore",
        ]

    def test_returns_empty_list_for_unusable_input(self):
        assert extract_tag_names([]) == []
        assert extract_tag_names(None) == []
        assert extract_tag_names([{"notname": "x"}]) == []

    def test_wraps_bare_string(self):
        assert extract_tag_names("Action") == ["action"]


class TestHasEndDate:
    def test_complete_date_is_one(self):
        assert has_end_date({"year": 2015, "month": 5, "day": 6}) == 1

    def test_any_none_is_zero(self):
        assert has_end_date({"year": None, "month": None, "day": None}) == 0
        assert has_end_date({"year": 2015, "month": None, "day": 6}) == 0

    def test_non_dict_is_zero(self):
        assert has_end_date(None) == 0


class TestParseDate:
    def test_parses_year_month(self):
        assert parse_date_to_datetime({"year": 1989, "month": 8}) == pd.Timestamp("1989-08-01")

    def test_missing_parts_yield_nat(self):
        assert pd.isna(parse_date_to_datetime({"year": 1989, "month": None}))
        assert pd.isna(parse_date_to_datetime(None))

    def test_invalid_month_does_not_raise(self):
        assert pd.isna(parse_date_to_datetime({"year": 1989, "month": 99}))


class TestCleanDescription:
    def test_strips_source_attribution(self):
        assert "Source" not in clean_description("A story. (Source: VIZ Media)")

    def test_strips_html_breaks_and_collapses_whitespace(self):
        assert clean_description("Line one.<br>Line two.") == "Line one. Line two."
        assert clean_description("too    many spaces") == "too many spaces"

    def test_passes_through_non_strings(self):
        assert clean_description(None) is None
        assert clean_description(42) == 42


class TestCleanMangaMetadata:
    def test_drops_adult_titles(self, raw_manga_records):
        df = clean_manga_metadata(raw_manga_records)
        assert 3 not in df["id"].tolist()
        assert len(df) == 2

    def test_removes_helper_columns(self, raw_manga_records):
        df = clean_manga_metadata(raw_manga_records)
        assert "isAdult" not in df.columns
        assert "endDate" not in df.columns
        assert "has_end_date" in df.columns

    def test_fills_missing_chapter_and_volume_counts(self, raw_manga_records):
        df = clean_manga_metadata(raw_manga_records)
        vagabond = df[df["id"] == 2].iloc[0]
        assert vagabond["chapters"] == -1
        assert vagabond["volumes"] == -1

    def test_normalizes_titles_and_tags(self, raw_manga_records):
        df = clean_manga_metadata(raw_manga_records)
        assert df[df["id"] == 1].iloc[0]["title"] == "berserk"
        assert df[df["id"] == 2].iloc[0]["title"] == "vagabond"
        assert df[df["id"] == 1].iloc[0]["tags"] == ["dark fantasy", "violence"]

    def test_retains_alternate_titles_for_search(self, raw_manga_records):
        df = clean_manga_metadata(raw_manga_records)
        assert df[df["id"] == 1].iloc[0]["search_titles"] == ["berserk", "ベルセルク"]
        assert "バガボンド" in df[df["id"] == 2].iloc[0]["search_titles"]

    def test_ongoing_series_flagged_without_end_date(self, raw_manga_records):
        df = clean_manga_metadata(raw_manga_records)
        assert df[df["id"] == 1].iloc[0]["has_end_date"] == 0
        assert df[df["id"] == 2].iloc[0]["has_end_date"] == 1


class TestCleanUserReadData:
    def test_drops_rows_without_joinable_ids(self, raw_user_records):
        df = clean_user_readdata(raw_user_records)
        assert len(df) == 3
        assert df["mediaId"].notna().all()

    def test_ids_are_integers(self, raw_user_records):
        df = clean_user_readdata(raw_user_records)
        assert df["userId"].dtype == "int64"
        assert df["mediaId"].dtype == "int64"

    def test_status_uppercased_and_dates_parsed(self, raw_user_records):
        df = clean_user_readdata(raw_user_records)
        assert set(df["status"]) <= {"COMPLETED", "CURRENT", "DROPPED", "PLANNING"}
        assert pd.api.types.is_datetime64_any_dtype(df["createdAt"])

    def test_missing_columns_are_synthesized(self):
        df = clean_user_readdata([{"userId": 1, "mediaId": 5}])
        assert {"status", "score", "progress", "createdAt"} <= set(df.columns)

    def test_empty_input_yields_empty_frame_for_the_quality_gate_to_reject(self):
        """Transforms stay total; enforcing non-emptiness is the gate's job."""
        df = clean_user_readdata([])
        assert df.empty

        with pytest.raises(DataQualityError):
            check_frame(df, "cleaned_user_readdata")
