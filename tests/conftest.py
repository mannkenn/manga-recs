"""Shared fixtures.

Environment defaults are set at import time, before anything from
``manga_recs`` is loaded, because settings are resolved once at module import.
"""

from __future__ import annotations

import os

os.environ.setdefault("AWS_ACCESS_KEY_ID", "minioadmin")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "minioadmin")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("MANGA_RECS_S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("MANGA_RECS_S3_BUCKET", "manga-recs-test")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture
def raw_manga_records() -> list[dict]:
    """AniList-shaped manga payloads, including the awkward cases."""
    return [
        {
            "id": 1,
            "title": {"english": "Berserk", "romaji": "Berserk", "native": "ベルセルク"},
            "description": "A wandering swordsman. (Source: Dark Horse) Note: ongoing.",
            "genres": ["Action", "Drama"],
            "tags": [{"name": "Dark Fantasy"}, {"name": "Violence"}],
            "startDate": {"year": 1989, "month": 8, "day": 25},
            "endDate": {"year": None, "month": None, "day": None},
            "chapters": 374,
            "volumes": 41,
            "popularity": 200000,
            "averageScore": 93,
            "meanScore": 93,
            "favourites": 40000,
            "isAdult": False,
        },
        {
            # No English title: should fall back to romaji.
            "id": 2,
            "title": {"english": None, "romaji": "Vagabond", "native": "バガボンド"},
            "description": "A swordsman's journey.<br>Second line.",
            "genres": ["Action"],
            "tags": [{"name": "Historical"}],
            "startDate": {"year": 1998, "month": 9, "day": 3},
            "endDate": {"year": 2015, "month": 5, "day": 6},
            "chapters": None,
            "volumes": None,
            "popularity": 90000,
            "averageScore": 90,
            "meanScore": 90,
            "favourites": 12000,
            "isAdult": False,
        },
        {
            # Adult content must be dropped.
            "id": 3,
            "title": {"english": "Adult Title", "romaji": "Adult Title", "native": None},
            "description": "Filtered out.",
            "genres": ["Ecchi"],
            "tags": [{"name": "Explicit"}],
            "startDate": {"year": 2010, "month": 1, "day": 1},
            "endDate": {"year": 2012, "month": 1, "day": 1},
            "chapters": 20,
            "volumes": 3,
            "popularity": 5000,
            "averageScore": 60,
            "meanScore": 60,
            "favourites": 100,
            "isAdult": True,
        },
    ]


@pytest.fixture
def raw_user_records() -> list[dict]:
    return [
        {
            "userId": 1,
            "status": "COMPLETED",
            "score": 9,
            "progress": 374,
            "mediaId": 1,
            "createdAt": 1_600_000_000,
        },
        {
            "userId": 1,
            "status": "CURRENT",
            "score": 0,
            "progress": 100,
            "mediaId": 2,
            "createdAt": 1_600_000_100,
        },
        {
            "userId": 2,
            "status": "DROPPED",
            "score": 3,
            "progress": 5,
            "mediaId": 1,
            "createdAt": 1_600_000_200,
        },
        # Unusable: no mediaId, must be dropped.
        {
            "userId": 3,
            "status": "PLANNING",
            "score": None,
            "progress": None,
            "mediaId": None,
            "createdAt": 1_600_000_300,
        },
    ]


@pytest.fixture
def similarity_matrix() -> pd.DataFrame:
    """A tiny, deliberately structured similarity matrix.

    Items 1/2 are near-identical, 3/4 are near-identical, and the two clusters
    barely resemble each other, so correct ranking is unambiguous.
    """
    ids = [1, 2, 3, 4]
    values = np.array(
        [
            [0.0, 0.9, 0.1, 0.05],
            [0.9, 0.0, 0.08, 0.02],
            [0.1, 0.08, 0.0, 0.95],
            [0.05, 0.02, 0.95, 0.0],
        ]
    )
    return pd.DataFrame(values, index=pd.Index(ids, name="id"), columns=ids)


@pytest.fixture
def catalog_metadata() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "title": ["berserk", "vagabond", "goodnight punpun", "solanin"],
            "search_titles": [
                ["berserk", "ベルセルク"],
                ["vagabond", "バガボンド"],
                ["goodnight punpun", "oyasumi punpun", "おやすみプンプン"],
                ["solanin", "ソラニン"],
            ],
            "description": ["a", "b", "c", "d"],
            "tags": [["dark"], ["dark"], ["slice of life"], ["slice of life"]],
            "popularity": [200000, 90000, 80000, 70000],
        }
    )
