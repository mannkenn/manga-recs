"""Resolve the two artifacts the serving path needs.

Inference needs only a similarity matrix and the metadata table it indexes. At
the current catalogue size that is roughly 8 MB, small enough to bake into the
image, which is what lets the deployed service run with no bucket, no
credentials, and no network egress. The pipeline still reads and writes the
object store; only serving is allowed to shortcut to a local bundle.
"""

from __future__ import annotations

import gzip
import io
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

# The bundle stores metadata as gzipped JSON rather than Parquet. Reading one
# 0.5 MB Parquet file at startup was the only thing in the serving path that
# needed pyarrow, and pyarrow is 143 MB installed - a fifth of the image, to
# read a file smaller than the wheel's changelog. Gzipped JSON is 368 KB, which
# is smaller than the Parquet it replaces, round-trips the list columns
# unchanged, and costs nothing but stdlib.
#
# Parquet stays in the pipeline, where columnar reads over the full dataset
# actually earn their dependency.
BUNDLE_METADATA_FILENAME = "manga_metadata.json.gz"

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
    """Return the model and metadata paths inside a bundle.

    Falls back to a Parquet metadata file so a bundle built before the format
    change still resolves rather than reporting itself absent.
    """
    bundle_dir = bundle_dir or settings.serving.bundle_dir
    metadata = bundle_dir / BUNDLE_METADATA_FILENAME
    if not metadata.exists():
        legacy = bundle_dir / CLEANED_MANGA_METADATA_PARQUET
        if legacy.exists():
            metadata = legacy
    return bundle_dir / COSINE_SIM_FILENAME, metadata


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
    model_target = bundle_dir / COSINE_SIM_FILENAME
    metadata_target = bundle_dir / BUNDLE_METADATA_FILENAME

    if resolved.model_path.resolve() != model_target.resolve():
        shutil.copy2(resolved.model_path, model_target)
    _write_bundle_metadata(resolved.metadata_path, metadata_target)

    # A bundle left holding both formats would keep resolving to whichever
    # bundle_paths prefers, so the superseded file is a trap rather than a
    # fallback.
    legacy = bundle_dir / CLEANED_MANGA_METADATA_PARQUET
    if legacy.exists():
        legacy.unlink()
        logger.info("Removed superseded %s", legacy.name)

    for dest in (model_target, metadata_target):
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


def _write_bundle_metadata(source: Path, dest: Path) -> None:
    """Convert the published Parquet metadata into the bundle's JSON format."""
    import pandas as pd

    frame = pd.read_parquet(source) if source.suffix == ".parquet" else read_bundle_metadata(source)
    with gzip.open(dest, "wt", encoding="utf-8") as handle:
        handle.write(frame.to_json(orient="records"))


def read_bundle_metadata(path: Path):
    """Load the metadata table, accepting either bundle format."""
    import pandas as pd

    if path.suffix == ".parquet":
        return pd.read_parquet(path)

    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return pd.read_json(io.StringIO(handle.read()), orient="records")


def _describe_backend() -> str:
    from manga_recs.data.load import describe_backend

    return describe_backend()


__all__ = [
    "ArtifactsUnavailableError",
    "BUNDLE_METADATA_FILENAME",
    "MANIFEST_FILENAME",
    "ResolvedArtifacts",
    "build_bundle",
    "bundle_is_present",
    "bundle_paths",
    "read_bundle_metadata",
    "read_manifest",
    "resolve",
]
