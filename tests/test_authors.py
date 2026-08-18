"""Tests for author extraction from the AniList staff connection.

The risk here is not parsing - it is including the wrong people. AniList credits
every translator, letterer, and per-edition editor on the same connection, so a
naive "take all staff" would link unrelated titles that happen to share an
English publisher's translator.
"""

from __future__ import annotations

import pandas as pd
import pytest

from manga_recs.data.transform.clean import (
    clean_manga_metadata,
    extract_author_names,
    is_author_role,
    normalize_staff_role,
)
from manga_recs.data.transform.feature_engineering import one_hot_encode_column


def staff(*pairs):
    """Build a staff connection in AniList's shape."""
    return {
        "edges": [
            {"role": role, "node": {"id": index, "name": {"full": name}}}
            for index, (role, name) in enumerate(pairs)
        ]
    }


class TestNormalizeStaffRole:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Story & Art", "story & art"),
            ("Story & Art (vols 1-41)", "story & art"),
            ("Translator (English: vols 5-8, 10-)", "translator"),
            ("  Art  ", "art"),
            ("Original Story", "original story"),
        ],
    )
    def test_strips_qualifiers_and_lowercases(self, raw, expected):
        assert normalize_staff_role(raw) == expected

    def test_non_strings_are_empty(self):
        assert normalize_staff_role(None) == ""
        assert normalize_staff_role(42) == ""


class TestIsAuthorRole:
    @pytest.mark.parametrize(
        "role",
        ["Story & Art", "Story", "Art", "Original Story", "Story & Art (vols 1-41)"],
    )
    def test_authoring_roles_are_accepted(self, role):
        assert is_author_role(role)

    @pytest.mark.parametrize(
        "role",
        [
            "Translator",
            "Translator (French)",
            "Lettering",
            "Assistant",
            "Editing",
            "Editor",
            "Character Design",
            "Supervisor (vols 41- )",
            "Touch-Up Art & Lettering",
            "Coloring",
        ],
    )
    def test_production_roles_are_rejected(self, role):
        """These are the roles that would otherwise pollute the feature."""
        assert not is_author_role(role)

    def test_unknown_roles_are_rejected_by_default(self):
        # An allowlist, so a role AniList invents later cannot silently leak in.
        assert not is_author_role("Interpretive Dance Consultant")


class TestExtractAuthorNames:
    def test_extracts_the_creator(self):
        assert extract_author_names(staff(("Story & Art", "Kentarou Miura"))) == ["kentarou miura"]

    def test_keeps_separate_story_and_art_credits(self):
        result = extract_author_names(staff(("Story", "Tsugumi Ohba"), ("Art", "Takeshi Obata")))
        assert result == ["tsugumi ohba", "takeshi obata"]

    def test_excludes_translators_and_letterers(self):
        result = extract_author_names(
            staff(
                ("Story & Art", "Inio Asano"),
                ("Translator (English)", "Some Translator"),
                ("Lettering", "Some Letterer"),
                ("Editing", "Some Editor"),
            )
        )
        assert result == ["inio asano"]

    def test_deduplicates_a_creator_credited_twice(self):
        result = extract_author_names(staff(("Story", "Naoki Urasawa"), ("Art", "Naoki Urasawa")))
        assert result == ["naoki urasawa"]

    def test_title_with_no_authoring_staff_yields_empty(self):
        assert extract_author_names(staff(("Translator", "Someone"))) == []

    @pytest.mark.parametrize("value", [None, {}, {"edges": None}, 42, "", []])
    def test_malformed_input_yields_empty_rather_than_raising(self, value):
        assert extract_author_names(value) == []

    def test_bare_string_is_wrapped(self):
        assert extract_author_names("Kentarou Miura") == ["kentarou miura"]

    def test_missing_node_or_name_is_skipped(self):
        edges = {
            "edges": [
                {"role": "Story & Art"},  # no node
                {"role": "Story & Art", "node": {}},  # no name
                {"role": "Story & Art", "node": {"name": {"full": "  "}}},  # blank
                {"role": "Story & Art", "node": {"name": {"full": "Real Author"}}},
            ]
        }
        assert extract_author_names(edges) == ["real author"]


class TestCleaningIntegration:
    def _record(self, **overrides):
        record = {
            "title": {"english": "Berserk", "romaji": "Berserk", "native": "ベルセルク"},
            "tags": [{"name": "Seinen"}],
            "genres": ["Action"],
            "popularity": 1000,
            "chapters": 100,
            "averageScore": 90,
            "startDate": {"month": 8, "year": 1989},
            "endDate": {"month": None, "year": None},
            "favourites": 10,
            "meanScore": 90,
            "isAdult": False,
            "id": 1,
            "volumes": 41,
            "description": "A knight.",
            "staff": staff(("Story & Art", "Kentarou Miura"), ("Translator", "Nope")),
        }
        record.update(overrides)
        return record

    def test_authors_column_is_produced_and_staff_dropped(self):
        cleaned = clean_manga_metadata([self._record()])
        assert cleaned["authors"].iloc[0] == ["kentarou miura"]
        # Raw staff has served its purpose and would bloat the parquet.
        assert "staff" not in cleaned.columns

    def test_data_ingested_before_staff_existed_still_cleans(self):
        """An older raw partition has no `staff` key at all."""
        record = self._record()
        del record["staff"]
        cleaned = clean_manga_metadata([record])
        assert cleaned["authors"].iloc[0] == []


class TestAuthorEncoding:
    def test_min_frequency_drops_single_credit_authors(self):
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "authors": [["prolific"], ["prolific"], ["one hit"]],
            }
        )
        encoded = one_hot_encode_column(df, "authors", prefix="author:", min_frequency=2)
        assert "author:prolific" in encoded.columns
        assert "author:one hit" not in encoded.columns

    def test_min_frequency_of_one_keeps_everything(self):
        df = pd.DataFrame({"id": [1, 2], "authors": [["a"], ["b"]]})
        encoded = one_hot_encode_column(df, "authors", prefix="author:", min_frequency=1)
        assert {"author:a", "author:b"} <= set(encoded.columns)

    def test_prefix_prevents_collision_with_a_tag_of_the_same_name(self):
        df = pd.DataFrame(
            {"id": [1, 2], "tags": [["clamp"], ["clamp"]], "authors": [["clamp"], ["clamp"]]}
        )
        encoded = one_hot_encode_column(df, "tags")
        encoded = one_hot_encode_column(encoded, "authors", prefix="author:", min_frequency=1)
        assert "clamp" in encoded.columns
        assert "author:clamp" in encoded.columns

    def test_titles_without_authors_get_all_zeros(self):
        df = pd.DataFrame({"id": [1, 2], "authors": [["shared"], []]})
        encoded = one_hot_encode_column(df, "authors", prefix="author:", min_frequency=1)
        assert encoded.loc[1, "author:shared"] == 0
