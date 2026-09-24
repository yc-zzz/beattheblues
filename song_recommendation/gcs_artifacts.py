"""Upload trained recommender artifacts to Google Cloud Storage."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def _storage_client():
    """Create a Cloud Storage client with the project's configured ADC."""
    try:
        from google.cloud import storage
    except ImportError as error:
        raise RuntimeError(
            "Google Cloud Storage support is not installed. "
            "Install dependencies from song_recommendation/requirements.txt."
        ) from error
    return storage.Client()


def parse_gcs_uri(bucket_uri: str) -> tuple[str, str]:
    """Return a bucket name and optional object prefix from a ``gs://`` URI."""
    if not bucket_uri.startswith("gs://"):
        raise ValueError("GCS_BUCKET_URI must start with 'gs://'.")
    bucket_and_prefix = bucket_uri.removeprefix("gs://").strip("/")
    if not bucket_and_prefix:
        raise ValueError("GCS_BUCKET_URI must include a bucket name.")
    bucket_name, separator, prefix = bucket_and_prefix.partition("/")
    return bucket_name, prefix if separator else ""


def upload_artifacts(bucket_uri: str, artifact_paths: Iterable[str | Path]) -> list[str]:
    """Upload local files beneath the prefix in ``bucket_uri``.

    Authentication is delegated to Application Default Credentials, for example
    a service account attached to the runtime or ``GOOGLE_APPLICATION_CREDENTIALS``.
    """
    bucket_name, prefix = parse_gcs_uri(bucket_uri)
    bucket = _storage_client().bucket(bucket_name)
    uploaded_uris = []
    for artifact_path in artifact_paths:
        artifact_path = Path(artifact_path)
        if not artifact_path.is_file():
            raise FileNotFoundError(f"Cannot upload missing artifact: {artifact_path}")
        object_name = "/".join(part for part in (prefix, artifact_path.name) if part)
        bucket.blob(object_name).upload_from_filename(artifact_path)
        uploaded_uris.append(f"gs://{bucket_name}/{object_name}")
    return uploaded_uris


def _embedding_cache_object_prefix(bucket_prefix: str, cache_key: str) -> str:
    """Build the object prefix for one immutable embedding-cache version."""
    if not cache_key or "/" in cache_key:
        raise ValueError("Embedding cache key must be a non-empty path component.")
    return "/".join(part for part in (bucket_prefix, "embedding_cache", cache_key) if part)


def download_embedding_cache(
    bucket_uri: str, cache_key: str, destination_dir: str | Path,
) -> dict[str, Path] | None:
    """Download a complete embedding cache, or return ``None`` when absent.

    ``cache_manifest.json`` is the cache's ready marker. The training code
    uploads it after the arrays, so a missing marker means another job may
    still be creating the cache and it is not safe to consume it yet.
    """
    bucket_name, bucket_prefix = parse_gcs_uri(bucket_uri)
    object_prefix = _embedding_cache_object_prefix(bucket_prefix, cache_key)
    bucket = _storage_client().bucket(bucket_name)
    manifest_blob = bucket.blob(f"{object_prefix}/cache_manifest.json")
    if not manifest_blob.exists():
        return None

    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    filenames = ("train_embeddings.npy", "test_embeddings.npy", "cache_manifest.json")
    local_paths: dict[str, Path] = {}
    for filename in filenames:
        local_path = destination / filename
        bucket.blob(f"{object_prefix}/{filename}").download_to_filename(local_path)
        local_paths[filename] = local_path
    return local_paths


def upload_embedding_cache(
    bucket_uri: str, cache_key: str, cache_paths: dict[str, str | Path],
) -> list[str]:
    """Upload embedding arrays and finally their manifest as an atomic-ready marker."""
    required = {"train_embeddings.npy", "test_embeddings.npy", "cache_manifest.json"}
    if set(cache_paths) != required:
        raise ValueError(f"Embedding cache paths must contain exactly: {sorted(required)}")

    bucket_name, bucket_prefix = parse_gcs_uri(bucket_uri)
    object_prefix = _embedding_cache_object_prefix(bucket_prefix, cache_key)
    bucket = _storage_client().bucket(bucket_name)
    uploaded_uris = []
    # The manifest is deliberately last: its presence means both arrays were
    # completely uploaded and can safely be used by a later Cloud Run job.
    for filename in ("train_embeddings.npy", "test_embeddings.npy", "cache_manifest.json"):
        local_path = Path(cache_paths[filename])
        if not local_path.is_file():
            raise FileNotFoundError(f"Cannot upload missing embedding cache file: {local_path}")
        object_name = f"{object_prefix}/{filename}"
        bucket.blob(object_name).upload_from_filename(local_path)
        uploaded_uris.append(f"gs://{bucket_name}/{object_name}")
    return uploaded_uris
