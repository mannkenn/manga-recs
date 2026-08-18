"""Resolve the two artifacts the serving path needs.

Inference needs only a similarity matrix and the metadata table it indexes. At
the current catalogue size that is roughly 8 MB, small enough to bake into the
image, which is what lets the deployed service run with no bucket, no
credentials, and no network egress. The pipeline still reads and writes the
object store; only serving is allowed to shortcut to a local bundle.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from manga_recs.common.constants import (
    CLEANED_MANGA_METADATA_PARQUET,
    CLEANED_STATUS,
    COSINE_SIM_FILENAME,
    MODELS_STATUS,
)
from manga_recs.common.settings import settings

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "MANIFEST.json"

VALID_SOURCES = ("auto", "bundle", "object_store")


class ArtifactsUnavailableError(RuntimeError):
    """Raised when neither the bundle nor the object store can supply artifacts."""


@dataclass(frozen=True)
class ResolvedArtifacts:
    model_path: Path
    metadata_path: Path
    source: str
    manifest: dict | None = None


def bundle_paths(bundle_dir: Path | None = None) -> tuple[Path, Path]:
    bundle_dir = bundle_dir or settings.serving.bundle_dir
    return bundle_dir / COSINE_SIM_FILENAME, bundle_dir / CLEANED_MANGA_METADATA_PARQUET


def bundle_is_present(bundle_dir: Path | None = None) -> bool:
    return all(path.exists() for path in bundle_paths(bundle_dir))


def read_manifest(bundle_dir: Path | None = None) -> dict | None:
    bundle_dir = bundle_dir or settings.serving.bundle_dir
    manifest_path = bundle_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        # Provenance metadata is informational; never fail serving over it.
        logger.warning("Ignoring unreadable bundle manifest: %s", exc)
        return None


def resolve(
    source: str | None = None,
    partition: str | None = None,
    bundle_dir: Path | None = None,
) -> ResolvedArtifacts:
    """Return local paths to the model and metadata, honouring the source policy."""
    source = (source or settings.serving.artifact_source).strip().lower()
    if source not in VALID_SOURCES:
        raise ArtifactsUnavailableError(
            f"Unknown artifact source {source!r}; expected one of {', '.join(VALID_SOURCES)}."
        )

    bundle_dir = bundle_dir or settings.serving.bundle_dir

    if source in ("auto", "bundle") and bundle_is_present(bundle_dir):
        model_path, metadata_path = bundle_paths(bundle_dir)
        logger.info("Serving artifacts from bundle at %s", bundle_dir)
        return ResolvedArtifacts(
            model_path=model_path,
            metadata_path=metadata_path,
            source="bundle",
            manifest=read_manifest(bundle_dir),
        )

    if source == "bundle":
        model_path, metadata_path = bundle_paths(bundle_dir)
        missing = [str(p) for p in (model_path, metadata_path) if not p.exists()]
        raise ArtifactsUnavailableError(
            "artifact_source is 'bundle' but the bundle is incomplete. Missing: "
            f"{', '.join(missing)}. Build it with `manga-recs bundle`."
        )

    # Imported lazily so that a bundle-only deployment never needs boto3
    # configured, or even importable, just to answer a request.
    from manga_recs.data.load import ObjectStoreError, get_file

    try:
        model_path = get_file(COSINE_SIM_FILENAME, status=MODELS_STATUS, partition=partition)
        metadata_path = get_file(
            CLEANED_MANGA_METADATA_PARQUET, status=CLEANED_STATUS, partition=partition
        )
    except ObjectStoreError as exc:
        raise ArtifactsUnavailableError(
            f"No bundle at {bundle_dir} and the object store could not supply artifacts: {exc}"
        ) from exc

    logger.info("Serving artifacts from the object store")
    return ResolvedArtifacts(
        model_path=model_path, metadata_path=metadata_path, source="object_store"
    )


def build_bundle(
    partition: str | None = None,
    bundle_dir: Path | None = None,
) -> ResolvedArtifacts:
    """Copy the published artifacts into the bundle directory for baking into an image.

    Writes a manifest alongside them so a running container can report exactly
    which pipeline run produced the model it is serving.
    """
    bundle_dir = bundle_dir or settings.serving.bundle_dir
    bundle_dir.mkdir(parents=True, exist_ok=True)

    resolved = resolve(source="object_store", partition=partition, bundle_dir=bundle_dir)
    model_target, metadata_target = bundle_paths(bundle_dir)

    for src, dest in (
        (resolved.model_path, model_target),
        (resolved.metadata_path, metadata_target),
    ):
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        logger.info("Bundled %s (%.1f MB)", dest.name, dest.stat().st_size / 1_000_000)

    manifest = {
        "partition": partition or "latest",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_backend": _describe_backend(),
        "files": {
            path.name: {"bytes": path.stat().st_size} for path in (model_target, metadata_target)
        },
    }
    (bundle_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    return ResolvedArtifacts(
        model_path=model_target,
        metadata_path=metadata_target,
        source="bundle",
        manifest=manifest,
    )


def _describe_backend() -> str:
    from manga_recs.data.load import describe_backend

    return describe_backend()


__all__ = [
    "ArtifactsUnavailableError",
    "MANIFEST_FILENAME",
    "ResolvedArtifacts",
    "build_bundle",
    "bundle_is_present",
    "bundle_paths",
    "read_manifest",
    "resolve",
]
