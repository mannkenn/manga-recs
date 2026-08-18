"""Tests for serving-artifact resolution.

This is the logic that lets the deployed image run with no bucket and no
credentials, so the cases that matter are: a present bundle wins, a missing
bundle falls back or fails loudly depending on policy, and nothing silently
reaches for the network when it was told not to.
"""

from __future__ import annotations

import json
from dataclasses import replace

import joblib
import pandas as pd
import pytest

from manga_recs.common.constants import (
    CLEANED_MANGA_METADATA_PARQUET,
    COSINE_SIM_FILENAME,
)
from manga_recs.common.settings import settings
from manga_recs.serving import artifacts


@pytest.fixture
def bundle(tmp_path, similarity_matrix, catalog_metadata):
    """A complete, loadable bundle on disk."""
    bundle_dir = tmp_path / "serving"
    bundle_dir.mkdir()
    joblib.dump(similarity_matrix, bundle_dir / COSINE_SIM_FILENAME)
    catalog_metadata.to_parquet(bundle_dir / CLEANED_MANGA_METADATA_PARQUET)
    return bundle_dir


@pytest.fixture
def bundled_settings(monkeypatch, bundle):
    """Point the package's settings at the temp bundle."""
    patched = replace(settings, serving=replace(settings.serving, bundle_dir=bundle))
    monkeypatch.setattr(artifacts, "settings", patched)
    return patched


class TestBundleDetection:
    def test_complete_bundle_is_detected(self, bundle):
        assert artifacts.bundle_is_present(bundle)

    def test_partial_bundle_is_not_usable(self, bundle):
        (bundle / COSINE_SIM_FILENAME).unlink()
        assert not artifacts.bundle_is_present(bundle)

    def test_empty_directory_is_not_usable(self, tmp_path):
        assert not artifacts.bundle_is_present(tmp_path)


class TestResolve:
    def test_auto_prefers_the_bundle(self, bundle):
        resolved = artifacts.resolve(source="auto", bundle_dir=bundle)
        assert resolved.source == "bundle"
        assert resolved.model_path == bundle / COSINE_SIM_FILENAME

    def test_bundle_source_never_touches_the_object_store(self, bundle, monkeypatch):
        """The whole point of the bundle is that serving needs no network."""

        def explode(*args, **kwargs):
            raise AssertionError("the object store must not be consulted")

        monkeypatch.setattr("manga_recs.data.load.get_file", explode)
        assert artifacts.resolve(source="bundle", bundle_dir=bundle).source == "bundle"

    def test_missing_bundle_under_bundle_policy_is_an_actionable_error(self, tmp_path):
        with pytest.raises(artifacts.ArtifactsUnavailableError, match="manga-recs bundle"):
            artifacts.resolve(source="bundle", bundle_dir=tmp_path / "absent")

    def test_auto_falls_back_to_the_object_store(self, tmp_path, monkeypatch, bundle):
        """With no bundle, `auto` should fetch rather than give up."""
        calls = []

        def fake_get_file(filename, status, partition=None, **kwargs):
            calls.append((filename, status))
            return bundle / filename

        monkeypatch.setattr("manga_recs.data.load.get_file", fake_get_file)
        resolved = artifacts.resolve(source="auto", bundle_dir=tmp_path / "absent")

        assert resolved.source == "object_store"
        assert [name for name, _ in calls] == [
            COSINE_SIM_FILENAME,
            CLEANED_MANGA_METADATA_PARQUET,
        ]

    def test_object_store_failure_is_wrapped(self, tmp_path, monkeypatch):
        from manga_recs.data.load import ObjectStoreError

        def explode(*args, **kwargs):
            raise ObjectStoreError("no credentials")

        monkeypatch.setattr("manga_recs.data.load.get_file", explode)
        with pytest.raises(artifacts.ArtifactsUnavailableError, match="no credentials"):
            artifacts.resolve(source="object_store", bundle_dir=tmp_path / "absent")

    def test_unknown_source_is_rejected(self, bundle):
        with pytest.raises(artifacts.ArtifactsUnavailableError, match="Unknown artifact source"):
            artifacts.resolve(source="carrier-pigeon", bundle_dir=bundle)


class TestManifest:
    def test_manifest_is_read_when_present(self, bundle):
        (bundle / artifacts.MANIFEST_FILENAME).write_text(
            json.dumps({"partition": "2026-08-07"}), encoding="utf-8"
        )
        assert artifacts.read_manifest(bundle)["partition"] == "2026-08-07"

    def test_absent_manifest_is_not_an_error(self, bundle):
        assert artifacts.read_manifest(bundle) is None

    def test_corrupt_manifest_is_ignored_rather_than_fatal(self, bundle):
        # Provenance metadata is informational; it must never take serving down.
        (bundle / artifacts.MANIFEST_FILENAME).write_text("{not json", encoding="utf-8")
        assert artifacts.read_manifest(bundle) is None

    def test_resolve_attaches_the_manifest(self, bundle):
        (bundle / artifacts.MANIFEST_FILENAME).write_text(
            json.dumps({"partition": "2026-08-07"}), encoding="utf-8"
        )
        assert artifacts.resolve(source="bundle", bundle_dir=bundle).manifest == {
            "partition": "2026-08-07"
        }


class TestRecommenderLoading:
    def test_loads_from_a_bundle_and_reports_its_source(self, bundled_settings, bundle):
        from manga_recs.serving.recommender import Recommender

        recommender = Recommender.load(source="bundle")
        assert recommender.source == "bundle"
        assert recommender.sim_matrix.shape == (4, 4)

        _, recs = recommender.recommend("berserk", 1)
        assert recs[0]["title"] == "vagabond"


class TestBuildBundle:
    def test_copies_artifacts_and_writes_a_manifest(self, tmp_path, monkeypatch, bundle):
        target = tmp_path / "out"

        def fake_get_file(filename, status, partition=None, **kwargs):
            return bundle / filename

        monkeypatch.setattr("manga_recs.data.load.get_file", fake_get_file)
        monkeypatch.setattr("manga_recs.data.load.describe_backend", lambda: "test-backend")

        resolved = artifacts.build_bundle(partition="2026-08-07", bundle_dir=target)

        assert (target / COSINE_SIM_FILENAME).exists()
        assert (target / CLEANED_MANGA_METADATA_PARQUET).exists()

        manifest = json.loads((target / artifacts.MANIFEST_FILENAME).read_text())
        assert manifest["partition"] == "2026-08-07"
        assert manifest["source_backend"] == "test-backend"
        assert set(manifest["files"]) == {COSINE_SIM_FILENAME, CLEANED_MANGA_METADATA_PARQUET}
        assert resolved.source == "bundle"

        # The copy has to be loadable, not merely present.
        assert isinstance(joblib.load(target / COSINE_SIM_FILENAME), pd.DataFrame)
