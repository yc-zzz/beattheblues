"""Upload trained recommender artifacts to Google Cloud Storage."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


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
    try:
        from google.cloud import storage
    except ImportError as error:
        raise RuntimeError(
            "Google Cloud Storage support is not installed. "
            "Install dependencies from song_recommendation/requirements.txt."
        ) from error

    bucket_name, prefix = parse_gcs_uri(bucket_uri)
    bucket = storage.Client().bucket(bucket_name)
    uploaded_uris = []
    for artifact_path in artifact_paths:
        artifact_path = Path(artifact_path)
        if not artifact_path.is_file():
            raise FileNotFoundError(f"Cannot upload missing artifact: {artifact_path}")
        object_name = "/".join(part for part in (prefix, artifact_path.name) if part)
        bucket.blob(object_name).upload_from_filename(artifact_path)
        uploaded_uris.append(f"gs://{bucket_name}/{object_name}")
    return uploaded_uris
