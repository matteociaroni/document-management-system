"""
EML file storage helpers.

Saves raw email bytes (.eml) to a dedicated S3 bucket so they can be
retrieved later by the agent worker.
"""

import logging
from storage import get_s3_client
from config import settings

logger = logging.getLogger(__name__)

EML_FOLDER = "email-eml-storage"


def _ensure_bucket(s3) -> None:
    """Create the EML bucket if it doesn't exist yet."""
    try:
        s3.head_bucket(Bucket=settings.gcp_bucket_name)
    except Exception as e:
        if "404" in str(e) or "NoSuchBucket" in str(e) or "Not Found" in str(e):
            s3.create_bucket(Bucket=settings.gcp_bucket_name)
            logger.info("Created main storage bucket: %s", settings.gcp_bucket_name)
        else:
            raise


def store_eml(job_id: str, raw_bytes: bytes) -> str:
    """
    Upload a raw .eml file to object storage.

    Args:
        job_id: The UUID of the EmailJob record (used as the storage key).
        raw_bytes: The complete RFC 822 message bytes.

    Returns:
        The storage key ('{job_id}.eml').
    """
    s3 = get_s3_client()
    _ensure_bucket(s3)

    key = f"{EML_FOLDER}/{job_id}.eml"
    s3.put_object(
        Bucket=settings.gcp_bucket_name,
        Key=key,
        Body=raw_bytes,
        ContentType="message/rfc822",
    )
    logger.debug("Stored EML: bucket=%s key=%s size=%d", settings.gcp_bucket_name, key, len(raw_bytes))
    return key


def load_eml(storage_key: str) -> bytes:
    """
    Download a raw .eml file from object storage.

    Args:
        storage_key: The key returned by store_eml ('{job_id}.eml').

    Returns:
        Raw bytes of the .eml file.
    """
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=settings.gcp_bucket_name, Key=storage_key)
    return obj["Body"].read()
