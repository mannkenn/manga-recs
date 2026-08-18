"""Measure what author features actually do to the recommender's metrics.

Every arm runs against the same cleaned snapshot and the same holdout seed, so
the only thing that varies is how authors are encoded. Comparing against the
previously published numbers instead would confound the feature change with the
fact that AniList's catalogue drifts between ingests.

    python scripts/author_ablation.py --partition 2026-08-18
"""

from __future__ import annotations

import argparse
import logging
from collections import Counter

import numpy as np
import pandas as pd

from manga_recs.common.constants import (
    CLEANED_MANGA_METADATA_PARQUET,
    CLEANED_STATUS,
    CLEANED_USER_READDATA_PARQUET,
)
from manga_recs.common.settings import settings
from manga_recs.data.load import get_file
from manga_recs.data.transform.feature_engineering import create_manga_features
from manga_recs.models.evaluate import build_positive_interactions, evaluate_all, split_holdout
from manga_recs.models.train_similarity import compute_cosine_similarity
from manga_recs.serving.recommender import Recommender

logger = logging.getLogger(__name__)

# (label, include_authors, author_min_titles)
ARMS = [
    ("no authors (baseline)", False, 0),
    ("authors, min 1 title", True, 1),
    ("authors, min 2 titles", True, 2),
    ("authors, min 3 titles", True, 3),
]


def _shuffled_authors(manga: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """Same author columns, but assigned to the wrong titles.

    A control for the following confound: a one-hot column set on a single title
    inflates that title's vector norm, which lowers its cosine similarity to
    everything and quietly demotes obscure titles. That alone could improve
    top-K metrics without any real author signal. Shuffling preserves the exact
    column structure and sparsity while destroying the author-to-title mapping,
    so whatever survives the shuffle is structure rather than signal.
    """
    shuffled = manga.copy()
    shuffled["authors"] = (
        manga["authors"].sample(frac=1.0, random_state=seed).reset_index(drop=True).values
    )
    return shuffled


def _per_user_recall(
    sim: pd.DataFrame, manga: pd.DataFrame, users: pd.DataFrame
) -> dict[int, float]:
    """Recall@k for each evaluated user, so arms can be compared pairwise.

    Mirrors the scoring in evaluate.evaluate_all; kept separate because that
    function intentionally returns aggregates only.
    """
    item_ids = sim.index.to_numpy()
    catalog = {int(i) for i in item_ids}
    position = {int(item): idx for idx, item in enumerate(item_ids)}
    similarity = sim.to_numpy(dtype=np.float32)
    k = settings.evaluation.k

    interactions = build_positive_interactions(users)
    splits = split_holdout(
        interactions,
        catalog,
        settings.evaluation.min_user_interactions,
        settings.evaluation.test_fraction,
        settings.evaluation.random_seed,
    )

    out: dict[int, float] = {}
    for user_id, (train_items, test_items) in splits.items():
        train_positions = [position[i] for i in train_items]
        scores = similarity[train_positions].max(axis=0)
        scores[train_positions] = -np.inf
        top = np.argpartition(-scores, min(k, len(scores) - 1))[:k]
        recommended = item_ids[top[np.argsort(-scores[top])]]

        relevant = set(test_items)
        hits = sum(1 for item in recommended[:k] if item in relevant)
        out[user_id] = hits / len(relevant)
    return out


def _report_paired(
    treatment_label: str,
    control_label: str,
    treatment: dict[int, float],
    control: dict[int, float],
    iterations: int = 10000,
    seed: int = 7,
) -> None:
    shared = sorted(set(treatment) & set(control))
    diffs = np.array([treatment[u] - control[u] for u in shared])

    rng = np.random.default_rng(seed)
    means = np.array(
        [diffs[rng.integers(0, len(diffs), len(diffs))].mean() for _ in range(iterations)]
    )
    low, high = np.percentile(means, [2.5, 97.5])
    verdict = "significant" if (low > 0 or high < 0) else "not separable"
    print(
        f"  {treatment_label:<24} vs {control_label:<24} "
        f"mean diff {diffs.mean():+.4f}  95% CI [{low:+.4f}, {high:+.4f}]  {verdict}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partition", required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    manga = pd.read_parquet(
        get_file(CLEANED_MANGA_METADATA_PARQUET, CLEANED_STATUS, partition=args.partition)
    )
    users = pd.read_parquet(
        get_file(CLEANED_USER_READDATA_PARQUET, CLEANED_STATUS, partition=args.partition)
    )

    print(f"\nSnapshot {args.partition}: {len(manga)} titles, {len(users)} user rows")
    have_authors = manga["authors"].apply(len).gt(0).sum() if "authors" in manga.columns else 0
    print(f"Titles with >=1 extracted author: {have_authors}/{len(manga)}\n")

    header = f"{'arm':<24}{'features':>10}{'recall@10':>11}{'precision@10':>14}{'ndcg@10':>10}{'coverage':>10}"
    print(header)
    print("-" * len(header))

    arms = list(ARMS) + [
        ("SHUFFLED authors, min 1", True, 1),
        ("SHUFFLED authors, min 2", True, 2),
    ]

    rows = []
    for label, include_authors, min_titles in arms:
        source = _shuffled_authors(manga) if label.startswith("SHUFFLED") else manga
        features = create_manga_features(
            source,
            include_authors=include_authors,
            author_min_titles=min_titles,
        )
        sim = compute_cosine_similarity(features)
        metrics = evaluate_all(
            sim,
            users,
            manga,
            k=settings.evaluation.k,
            min_interactions=settings.evaluation.min_user_interactions,
            test_fraction=settings.evaluation.test_fraction,
            seed=settings.evaluation.random_seed,
        )
        content = next(m for m in metrics if m.strategy == "content")
        n_features = features.shape[1] - 1
        rows.append((label, n_features, content))
        print(
            f"{label:<24}{n_features:>10}{content.recall_at_k:>11.4f}"
            f"{content.precision_at_k:>14.4f}{content.ndcg_at_k:>10.4f}"
            f"{content.catalog_coverage:>10.4f}"
        )

    base = rows[0][2]
    print("\nDelta vs the no-authors arm on the same snapshot:")
    for label, n_features, content in rows[1:]:
        print(
            f"  {label:<24} recall {content.recall_at_k - base.recall_at_k:+.4f}"
            f"   precision {content.precision_at_k - base.precision_at_k:+.4f}"
            f"   ndcg {content.ndcg_at_k - base.ndcg_at_k:+.4f}"
            f"   (+{n_features - rows[0][1]} columns)"
        )
    print(f"\nUsers evaluated: {base.users_evaluated}")

    # With 189 users, differences of a hundredth of a point are easy to
    # over-read. Pair the per-user recalls and bootstrap the mean difference so
    # each comparison comes with an interval instead of a single number.
    print("\n" + "=" * 79)
    print("Paired per-user recall@10, bootstrapped 95% CI on the mean difference")
    print("=" * 79)

    recalls = {}
    for label, include_authors, min_titles in arms:
        source = _shuffled_authors(manga) if label.startswith("SHUFFLED") else manga
        features = create_manga_features(
            source, include_authors=include_authors, author_min_titles=min_titles
        )
        recalls[label] = _per_user_recall(compute_cosine_similarity(features), manga, users)

    baseline_label = arms[0][0]
    comparisons = [(label, baseline_label) for label, _, _ in arms[1:]]
    comparisons += [
        ("authors, min 1 title", "SHUFFLED authors, min 1"),
        ("authors, min 2 titles", "SHUFFLED authors, min 2"),
    ]

    for treatment, control in comparisons:
        _report_paired(treatment, control, recalls[treatment], recalls[control])

    print(
        "\nA CI spanning zero means the arms are not separable at this sample size.\n"
        "Comparing a real-author arm against its shuffled twin is the test that\n"
        "matters: the shuffle keeps the column structure and destroys the signal,\n"
        "so any difference there is attributable to authors and nothing else."
    )

    _report_author_reach(manga)
    _report_same_author_retrieval(manga)


def _report_author_reach(manga: pd.DataFrame) -> None:
    """How much of the similarity matrix author features can even touch.

    Bounds the effect size before interpreting any of it. A feature that can
    only alter a fraction of a percent of the item pairs cannot move an
    aggregate metric, regardless of how good the signal is on those pairs.
    """
    counts = Counter(author for authors in manga["authors"] for author in authors)
    repeated = {name: n for name, n in counts.items() if n >= 2}
    linked = sum(n * (n - 1) // 2 for n in repeated.values())
    total = len(manga) * (len(manga) - 1) // 2

    print("\n" + "=" * 79)
    print("Reach of the author feature")
    print("=" * 79)
    print(f"  {len(counts)} distinct authors, {len(repeated)} credited on 2+ titles")
    print(f"  title pairs sharing an author: {linked} of {total} ({linked / total * 100:.3f}%)")
    print("  Most prolific:", ", ".join(f"{n}x {a}" for a, n in counts.most_common(5)))


def _report_same_author_retrieval(manga: pd.DataFrame) -> None:
    """Measure the thing the author feature is actually for.

    recall@10 against user holdouts asks "did we predict what they read next".
    It is not an instrument for "does this surface more work by this creator",
    which is the question authors are supposed to answer. Measure that directly.
    """
    # Coerce to sets up front: the parquet round-trip yields numpy arrays, which
    # are ambiguous in a boolean context.
    by_title = {
        title: set(authors) for title, authors in zip(manga["title"], manga["authors"], strict=True)
    }

    recommenders = {}
    for label, include in (("without authors", False), ("with authors", True)):
        features = create_manga_features(manga, include_authors=include, author_min_titles=2)
        recommenders[label] = Recommender(compute_cosine_similarity(features), manga)

    in_matrix = set(manga[manga["id"].isin(recommenders["with authors"].sim_matrix.index)]["title"])
    queries = [
        title
        for title in in_matrix
        if by_title[title]
        and any(other != title and by_title[title] & by_title[other] for other in in_matrix)
    ]

    print("\n" + "=" * 79)
    print("Same-author retrieval: titles by the query's creator surfaced in the top 10")
    print("=" * 79)
    print(f"  Over the {len(queries)} titles that have a same-author sibling in the catalogue:")
    for label, recommender in recommenders.items():
        hits = 0
        for title in queries:
            author = by_title[title]
            _, recs = recommender.recommend(title, top_n=10)
            hits += sum(1 for rec in recs if author & by_title.get(rec["title"], set()))
        print(f"    {label:<16} {hits} surfaced")
    print(
        "\n  This is where the feature earns its place. It is invisible to recall@10\n"
        "  because same-author pairs are a rounding error in the matrix above."
    )


if __name__ == "__main__":
    main()
