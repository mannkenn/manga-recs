import pytest

from manga_recs.serving.recommender import Recommender, TitleNotFoundError


@pytest.fixture
def recommender(similarity_matrix, catalog_metadata) -> Recommender:
    return Recommender(similarity_matrix, catalog_metadata, fuzzy_threshold=65)


class TestTitleMatching:
    def test_exact_title_matches(self, recommender):
        match = recommender.match_title("berserk")
        assert match.manga_id == 1
        assert match.score == 100

    def test_matching_is_case_insensitive(self, recommender):
        assert recommender.match_title("BERSERK").manga_id == 1

    def test_typos_still_match(self, recommender):
        assert recommender.match_title("bersrek").manga_id == 1

    def test_unrelated_query_raises(self, recommender):
        with pytest.raises(TitleNotFoundError):
            recommender.match_title("zzzzzzzzzz nonexistent qqqq")

    def test_romaji_variant_resolves_to_the_same_manga(self, recommender):
        """Users search by the Japanese name as often as the English one."""
        english = recommender.match_title("goodnight punpun")
        romaji = recommender.match_title("oyasumi punpun")
        assert romaji.manga_id == english.manga_id == 3

    def test_native_script_variant_matches(self, recommender):
        assert recommender.match_title("ベルセルク").manga_id == 1

    def test_match_reports_the_display_title_not_the_variant(self, recommender):
        match = recommender.match_title("oyasumi punpun")
        assert match.title == "goodnight punpun"

    def test_falls_back_to_title_when_variants_absent(self, similarity_matrix, catalog_metadata):
        legacy = catalog_metadata.drop(columns=["search_titles"])
        recommender = Recommender(similarity_matrix, legacy, fuzzy_threshold=65)
        assert recommender.match_title("berserk").manga_id == 1

    @pytest.mark.parametrize(
        "junk",
        [
            "a",  # a single character must not match a long title
            "q",
            "the",
            "asdfghjkl",
            "zzzz qqqq nonexistent",  # substring 'existen' must not pull in a real title
            "my favourite book ever",
        ],
    )
    def test_junk_queries_are_rejected(self, recommender, junk):
        """Guards the partial-substring behaviour that made WRatio unusable here."""
        with pytest.raises(TitleNotFoundError):
            recommender.match_title(junk)


class TestRecommend:
    def test_returns_requested_number(self, recommender):
        _, recs = recommender.recommend("berserk", top_n=2)
        assert len(recs) == 2

    def test_never_recommends_the_query_itself(self, recommender):
        _, recs = recommender.recommend("berserk", top_n=3)
        assert 1 not in [r["id"] for r in recs]

    def test_ranks_the_most_similar_item_first(self, recommender):
        # Items 1 and 2 are the tightly-coupled pair in the fixture matrix.
        _, recs = recommender.recommend("berserk", top_n=3)
        assert recs[0]["id"] == 2

        _, recs = recommender.recommend("oyasumi punpun", top_n=3)
        assert recs[0]["id"] == 4

    def test_results_are_sorted_by_descending_similarity(self, recommender):
        _, recs = recommender.recommend("berserk", top_n=3)
        scores = [r["similarity"] for r in recs]
        assert scores == sorted(scores, reverse=True)

    def test_reports_which_title_was_matched(self, recommender):
        match, _ = recommender.recommend("bersrek", top_n=1)
        assert match.title == "berserk"

    def test_tags_are_plain_lists_for_json(self, recommender):
        _, recs = recommender.recommend("berserk", top_n=2)
        assert all(isinstance(r["tags"], list) for r in recs)

    def test_top_n_larger_than_catalog_is_safe(self, recommender):
        _, recs = recommender.recommend("berserk", top_n=99)
        assert len(recs) == 3  # everything except the query itself
