"""Client for an S3-compatible object store (AWS S3, Cloudflare R2, MinIO).

Artifacts are laid out as ``{status}/{YYYY-MM-DD}/{filename}``. The date acts as
a partition so every pipeline run is immutable and previous runs stay
reproducible; readers resolve the newest partition unless pinned to one.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from manga_recs.common.settings import settings

logger = logging.getLogger(__name__)

PARTITION_FORMAT = "%Y-%m-%d"


class ObjectStoreError(RuntimeError):
    """Raised when an object store operation fails."""


def _build_config() -> Config:
    kwargs: dict[str, object] = {
        "retries": {"max_attempts": 5, "mode": "standard"},
        # Fail fast on a misconfigured endpoint instead of hanging the CLI.
        "connect_timeout": 10,
        "read_timeout": 60,
    }
    if settings.storage.force_path_style:
        kwargs["s3"] = {"addressing_style": "path"}

    # boto3 >= 1.36 sends CRC32 integrity headers on every upload, which several
    # S3-compatible stores reject outright. Only send them when the API requires.
    try:
        return Config(
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
            **kwargs,
        )
    except TypeError:
        return Config(**kwargs)


@lru_cache(maxsize=1)
def get_client():
    """Return a cached S3 client resolved from settings and the AWS credential chain."""
    return boto3.client(
        "s3",
        endpoint_url=settings.storage.endpoint_url or None,
        region_name=settings.storage.region,
        config=_build_config(),
    )


def _resolve_bucket(bucket: str | None) -> str:
    return bucket or settings.storage.bucket


def _wrap(exc: Exception, action: str) -> ObjectStoreError:
    if isinstance(exc, NoCredentialsError):
        return ObjectStoreError(
            f"{action} failed: no object store credentials found. Set "
            "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your .env "
            "(copy .env.example) or configure an AWS profile."
        )
    return ObjectStoreError(f"{action} failed: {exc}")


def list_partitions(status: str, bucket: str | None = None) -> list[str]:
    """Return every ``YYYY-MM-DD`` partition under ``status``, oldest first."""
    bucket = _resolve_bucket(bucket)
    client = get_client()

    partitions: set[str] = set()
    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=f"{status}/"):
            for obj in page.get("Contents", []):
                parts = obj["Key"].split("/")
                if len(parts) < 3 or not parts[2]:
                    continue
                try:
                    datetime.strptime(parts[1], PARTITION_FORMAT)
                except ValueError:
                    continue
                partitions.add(parts[1])
    except (BotoCoreError, ClientError, NoCredentialsError) as exc:
        raise _wrap(exc, f"Listing s3://{bucket}/{status}/") from exc

    return sorted(partitions)


def latest_partition(status: str, bucket: str | None = None) -> str:
    """Return the newest partition under ``status``."""
    partitions = list_partitions(status, bucket)
    if not partitions:
        bucket = _resolve_bucket(bucket)
        raise ObjectStoreError(
            f"No partitions found under s3://{bucket}/{status}/. "
            "Run the upstream pipeline stage first."
        )
    return partitions[-1]


def put_file(
    local_path: str | Path,
    filename: str,
    status: str,
    bucket: str | None = None,
    partition: str | None = None,
) -> str:
    """Upload a local file into ``{status}/{partition}/{filename}``."""
    bucket = _resolve_bucket(bucket)
    local_path = Path(local_path)
    if not local_path.exists():
        raise ObjectStoreError(f"Cannot upload missing file: {local_path}")

    partition = partition or date.today().strftime(PARTITION_FORMAT)
    key = f"{status}/{partition}/{filename}"

    try:
        get_client().upload_file(str(local_path), bucket, key)
    except (BotoCoreError, ClientError, NoCredentialsError) as exc:
        raise _wrap(exc, f"Upload of {filename} to s3://{bucket}/{key}") from exc

    uri = f"s3://{bucket}/{key}"
    logger.info("Uploaded %s -> %s", local_path.name, uri)
    return uri


def _cache_is_current(local_path: Path, bucket: str, key: str) -> bool:
    """Check a cached file against the remote object's size and timestamp.

    Partitioning alone is not enough: re-running the same date overwrites the
    object in place, so a cache hit keyed only on the path would serve the
    previous run's data to the next stage.
    """
    try:
        head = get_client().head_object(Bucket=bucket, Key=key)
    except (BotoCoreError, ClientError, NoCredentialsError):
        # Cannot verify: fall back to re-downloading rather than risk stale data.
        return False

    stat = local_path.stat()
    if stat.st_size != head.get("ContentLength"):
        return False

    last_modified = head.get("LastModified")
    return last_modified is None or stat.st_mtime >= last_modified.timestamp()


def get_file(
    filename: str,
    status: str,
    bucket: str | None = None,
    partition: str | None = None,
    use_cache: bool = True,
) -> Path:
    """Download ``filename`` from the object store, returning the local path.

    The local cache is keyed by partition and validated against the remote
    object, so neither a new partition nor an overwritten one is ever served
    from a stale download.
    """
    bucket = _resolve_bucket(bucket)
    partition = partition or latest_partition(status, bucket)

    local_path = Path(settings.paths.data_dir) / status / partition / filename
    key = f"{status}/{partition}/{filename}"

    if use_cache and local_path.exists() and _cache_is_current(local_path, bucket, key):
        logger.info("Using cached %s", local_path)
        return local_path

    local_path.parent.mkdir(parents=True, exist_ok=True)

    # Download to a temp name first so an interrupted transfer cannot leave a
    # truncated file that later looks like a valid cache hit.
    tmp_path = local_path.with_suffix(local_path.suffix + ".part")
    try:
        get_client().download_file(bucket, key, str(tmp_path))
        tmp_path.replace(local_path)
    except (BotoCoreError, ClientError, NoCredentialsError) as exc:
        tmp_path.unlink(missing_ok=True)
        raise _wrap(exc, f"Download of s3://{bucket}/{key}") from exc

    logger.info("Downloaded s3://%s/%s -> %s", bucket, key, local_path)
    return local_path


def ensure_bucket(bucket: str | None = None) -> None:
    """Create the bucket if it does not exist. Used for MinIO and tests."""
    bucket = _resolve_bucket(bucket)
    client = get_client()
    try:
        client.head_bucket(Bucket=bucket)
        return
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"404", "NoSuchBucket"}:
            raise _wrap(exc, f"Checking bucket {bucket}") from exc
    except (BotoCoreError, NoCredentialsError) as exc:
        raise _wrap(exc, f"Checking bucket {bucket}") from exc

    try:
        client.create_bucket(Bucket=bucket)
    except (BotoCoreError, ClientError) as exc:
        raise _wrap(exc, f"Creating bucket {bucket}") from exc
    logger.info("Created bucket %s", bucket)


def reset_client_cache() -> None:
    """Drop the cached client so new credentials or endpoints take effect."""
    get_client.cache_clear()


def describe_backend() -> str:
    """Human-readable description of where artifacts are being read and written."""
    endpoint = settings.storage.endpoint_url or "AWS S3"
    return f"{settings.storage.bucket} @ {endpoint} (region={settings.storage.region})"


# Backwards-compatible aliases for the original call sites.
def s3_dump(filepath: str, filename: str, bucket: str | None = None, status: str = "raw") -> str:
    return put_file(filepath, filename, status=status, bucket=bucket)


def s3_load(
    filename: str,
    bucket: str | None = None,
    status: str = "raw",
    use_cache: bool = True,
) -> str:
    return str(get_file(filename, status=status, bucket=bucket, use_cache=use_cache))


__all__ = [
    "PARTITION_FORMAT",
    "ObjectStoreError",
    "describe_backend",
    "ensure_bucket",
    "get_client",
    "get_file",
    "latest_partition",
    "list_partitions",
    "put_file",
    "reset_client_cache",
    "s3_dump",
    "s3_load",
]
