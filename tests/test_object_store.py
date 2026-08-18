"""Integration tests for the object store, run against MinIO.

These exercise the real boto3 code path rather than a mock, which is the whole
point: the bugs worth catching here are endpoint, addressing-style, and
partition-resolution bugs that a mock would happily paper over.

Start the dependency with ``docker compose up -d minio minio-init``.
"""

from __future__ import annotations

import socket
from dataclasses import replace

import pytest

from manga_recs.common.settings import settings
from manga_recs.data.load import (
    ObjectStoreError,
    ensure_bucket,
    get_file,
    latest_partition,
    list_partitions,
    put_file,
)
from manga_recs.data.load import object_store as object_store_module


def _minio_reachable() -> bool:
    endpoint = settings.storage.endpoint_url
    if not endpoint:
        return False
    host, _, port = endpoint.split("//", 1)[1].partition(":")
    try:
        with socket.create_connection((host, int(port or 80)), timeout=1):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _minio_reachable(),
    reason="MinIO not running; start it with `docker compose up -d minio minio-init`",
)


@pytest.fixture(scope="module", autouse=True)
def bucket():
    ensure_bucket()


@pytest.fixture(autouse=True)
def download_dir(tmp_path, monkeypatch):
    """Point downloads at a temp dir instead of the working tree's ``data/``.

    ``get_file`` caches under ``settings.paths.data_dir``, so without this the
    suite scatters fixture files through the real data directory - including
    into ``data/raw/``, where a stray partition would be visible to the
    pipeline's own "latest partition" resolution.
    """
    redirected = replace(settings, paths=replace(settings.paths, data_dir=tmp_path / "store"))
    monkeypatch.setattr(object_store_module, "settings", redirected)
    return redirected.paths.data_dir


@pytest.fixture
def sample_file(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("payload", encoding="utf-8")
    return path


def test_upload_then_download_round_trips(sample_file, tmp_path):
    put_file(sample_file, "round_trip.txt", "raw", partition="2020-01-01")
    downloaded = get_file("round_trip.txt", "raw", partition="2020-01-01", use_cache=False)
    assert downloaded.read_text(encoding="utf-8") == "payload"


def test_latest_partition_picks_the_newest_date(sample_file):
    for partition in ("2020-01-01", "2021-06-15", "2020-12-31"):
        put_file(sample_file, "versioned.txt", "ordering", partition=partition)

    assert latest_partition("ordering") == "2021-06-15"
    assert list_partitions("ordering") == ["2020-01-01", "2020-12-31", "2021-06-15"]


def test_cache_is_partition_scoped(sample_file, tmp_path):
    """A newer partition must not be served from an older partition's cache."""
    put_file(sample_file, "cached.txt", "cachetest", partition="2020-01-01")
    first = get_file("cached.txt", "cachetest", partition="2020-01-01")
    assert first.read_text(encoding="utf-8") == "payload"

    updated = tmp_path / "updated.txt"
    updated.write_text("newer payload", encoding="utf-8")
    put_file(updated, "cached.txt", "cachetest", partition="2020-02-01")

    latest = get_file("cached.txt", "cachetest")
    assert latest.read_text(encoding="utf-8") == "newer payload"
    assert latest != first


def test_cache_is_invalidated_when_a_partition_is_overwritten(sample_file, tmp_path):
    """Re-running the same partition must not serve the previous run's data."""
    put_file(sample_file, "rerun.txt", "rerun", partition="2020-01-01")
    first = get_file("rerun.txt", "rerun", partition="2020-01-01")
    assert first.read_text(encoding="utf-8") == "payload"

    replacement = tmp_path / "replacement.txt"
    replacement.write_text("second run payload", encoding="utf-8")
    put_file(replacement, "rerun.txt", "rerun", partition="2020-01-01")

    again = get_file("rerun.txt", "rerun", partition="2020-01-01")
    assert again == first  # same local path
    assert again.read_text(encoding="utf-8") == "second run payload"


def test_missing_object_raises(sample_file):
    put_file(sample_file, "present.txt", "missingtest", partition="2020-01-01")
    with pytest.raises(ObjectStoreError, match="Download of"):
        get_file("absent.txt", "missingtest", use_cache=False)


def test_missing_partition_raises_actionable_error():
    with pytest.raises(ObjectStoreError, match="No partitions found"):
        latest_partition("status-that-does-not-exist")


def test_uploading_a_missing_file_raises(tmp_path):
    with pytest.raises(ObjectStoreError, match="Cannot upload missing file"):
        put_file(tmp_path / "nope.txt", "nope.txt", "raw")


def test_failed_download_leaves_no_partial_file(download_dir, sample_file):
    put_file(sample_file, "present.txt", "partialtest", partition="2020-01-01")
    with pytest.raises(ObjectStoreError):
        get_file("absent.txt", "partialtest", partition="2020-01-01", use_cache=False)

    expected = download_dir / "partialtest" / "2020-01-01" / "absent.txt"
    assert not expected.exists()
    assert not expected.with_suffix(".txt.part").exists()
