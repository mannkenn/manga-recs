"""Inference engine shared by the HTTP API and the CLI.

Keeping a single implementation here means the API and the command line cannot
drift apart in how they match titles or rank results.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from functools import lru_cache

import joblib
import pandas as pd
from rapidfuzz import fuzz, process

from manga_recs.common.settings import settings
from manga_recs.serving import artifacts

logger = logging.getLogger(__name__)

RESULT_COLUMNS = ["id", "title", "description", "genres", "tags"]

# Parquet round-trips these as numpy arrays, which are not JSON serialisable.
LIST_COLUMNS = ("genres", "tags")


def _as_list(value) -> list[str]:
    if value is None or isinstance(value, str):
        return []
    if hasattr(value, "__iter__"):
        return [str(item) for item in value]
    return []


class TitleNotFoundError(LookupError):
    """Raised when a query title cannot be resolved to a known manga."""


@dataclass(frozen=True)
class TitleMatch:
    manga_id: int
    title: str
    score: float


class Recommender:
    """Content-based recommender backed by a precomputed similarity matrix."""

    def __init__(
        self,
        sim_matrix: pd.DataFrame,
        metadata: pd.DataFrame,
        fuzzy_threshold: int | None = None,
        source: str = "memory",
        manifest: dict | None = None,
    ) -> None:
        self.sim_matrix = sim_matrix
        self.metadata = metadata
        self.fuzzy_threshold = (
            settings.api.fuzzy_match_threshold if fuzzy_threshold is None else fuzzy_threshold
        )
        # Where this model came from, surfaced on /health so a deployed instance
        # can say whether it is serving baked-in or freshly fetched artifacts.
        self.source = source
        self.manifest = manifest
        self._search_titles, self._title_rows = self._build_search_index(metadata)

    @staticmethod
    def _build_search_index(metadata: pd.DataFrame) -> tuple[list[str], list[int]]:
        """Flatten every title variant into a searchable list plus its source row.

        Each manga contributes its English, romaji, and native names, so a query
        matches whichever form the user happens to know.
        """
        search_titles: list[str] = []
        title_rows: list[int] = []

        has_variants = "search_titles" in metadata.columns
        for row, (_, record) in enumerate(metadata.iterrows()):
            variants = list(record["search_titles"]) if has_variants else []
            if not variants:
                display = record.get("title")
                variants = [display] if isinstance(display, str) and display else []

            for variant in variants:
                search_titles.append(str(variant).lower())
                title_rows.append(row)

        return search_titles, title_rows

    @classmethod
    def load(cls, source: str | None = None, partition: str | None = None) -> Recommender:
        """Load a recommender from wherever the configured artifact source points.

        Defaults to the baked-in bundle when one is present, so a deployed
        container serves without credentials or network access.
        """
        resolved = artifacts.resolve(source=source, partition=partition)
        sim_matrix = joblib.load(resolved.model_path)
        metadata = pd.read_parquet(resolved.metadata_path)
        logger.info(
            "Loaded recommender from %s: %d items in similarity matrix, %d metadata rows",
            resolved.source,
            sim_matrix.shape[0],
            len(metadata),
        )
        return cls(sim_matrix, metadata, source=resolved.source, manifest=resolved.manifest)

    @classmethod
    def from_store(cls, partition: str | None = None) -> Recommender:
        """Load the newest published model and metadata from the object store."""
        return cls.load(source="object_store", partition=partition)

    def match_title(self, title: str) -> TitleMatch:
        """Resolve a free-text title to a manga id using fuzzy matching.

        Uses ``token_sort_ratio`` rather than ``WRatio``. WRatio scores partial
        substring hits generously, which over a 2,500-entry title index means a
        one-character query matches something at 90 and junk like "nonexistent"
        matches "existence". token_sort_ratio stays length-aware while still
        tolerating word-order differences.
        """
        best = process.extractOne(title.lower(), self._search_titles, scorer=fuzz.token_sort_ratio)
        if best is None or best[1] < self.fuzzy_threshold:
            raise TitleNotFoundError(f"No manga matching '{title}'.")

        _, score, position = best
        record = self.metadata.iloc[self._title_rows[position]]
        manga_id = int(record["id"])

        # Report the display title even when the query matched a romaji variant.
        display_title = record["title"] if isinstance(record["title"], str) else best[0]

        if manga_id not in self.sim_matrix.index:
            raise TitleNotFoundError(
                f"'{display_title}' has no entry in the similarity matrix; "
                "it may have been filtered out during feature engineering."
            )
        return TitleMatch(manga_id=manga_id, title=display_title, score=float(score))

    def recommend(self, title: str, top_n: int | None = None) -> tuple[TitleMatch, list[dict]]:
        """Return the matched title and its ``top_n`` most similar manga."""
        top_n = top_n or settings.recommendation.default_top_n
        match = self.match_title(title)

        similarities = (
            self.sim_matrix.loc[match.manga_id]
            .drop(index=match.manga_id, errors="ignore")
            .sort_values(ascending=False)
            .head(top_n)
        )

        available = [col for col in RESULT_COLUMNS if col in self.metadata.columns]
        recs = self.metadata[self.metadata["id"].isin(similarities.index)][available]
        recs = recs.set_index("id").join(similarities.rename("similarity"))
        recs["similarity"] = recs["similarity"].astype(float).round(4)
        for column in LIST_COLUMNS:
            if column in recs.columns:
                recs[column] = recs[column].apply(_as_list)
        recs = recs.sort_values(by="similarity", ascending=False)

        return match, recs.reset_index().to_dict(orient="records")


@lru_cache(maxsize=1)
def get_recommender() -> Recommender:
    """Process-wide cached recommender."""
    return Recommender.load()


def get_top_n_recommendations_by_title(title: str, top_n: int = 5) -> list[dict]:
    """Convenience wrapper returning just the recommendation records."""
    _, recommendations = get_recommender().recommend(title, top_n)
    return recommendations


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Get top-N manga recommendations by title")
    parser.add_argument(
        "--title", required=True, help="Manga title to generate recommendations for"
    )
    parser.add_argument(
        "--top-n",
        "--top_n",
        dest="top_n",
        type=int,
        default=settings.recommendation.default_top_n,
        help="Number of recommendations to return",
    )
    args = parser.parse_args()

    match, recommendations = get_recommender().recommend(args.title, args.top_n)
    print(f"Matched '{args.title}' -> '{match.title}' (score {match.score:.0f})\n")
    for rank, rec in enumerate(recommendations, start=1):
        print(f"{rank}. {rec['title']}  (similarity {rec['similarity']:.3f})")


if __name__ == "__main__":
    main()
