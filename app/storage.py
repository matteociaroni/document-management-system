import logging
import boto3
from app.config import settings

logger = logging.getLogger(__name__)


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1"
    )


def get_bucket_name(email: str) -> str:
    """Derive bucket name from email domain"""
    if "@" not in email:
        raise ValueError(f"Invalid email format: {email}")
    domain = email.split("@")[1]
    return domain.replace(".", "-")


def _generate_presigned_url(document_id: str, email: str, operation: str) -> str:
    """Generate presigned URL for upload (put_object) or download (get_object)"""
    try:
        s3 = get_s3_client()
        bucket = get_bucket_name(email)
        
        try:
            s3.head_bucket(Bucket=bucket)
        except s3.exceptions.NoSuchBucket:
            s3.create_bucket(Bucket=bucket)
        except Exception as e:
            logger.error(f"S3 bucket head check failed: {e}")
            raise
        
        url = s3.generate_presigned_url(
            operation,
            Params={"Bucket": bucket, "Key": document_id},
            ExpiresIn=3600
        )
        return url
    except Exception as e:
        logger.error(f"Failed to generate presigned URL ({operation}): {e}")
        return f"{settings.s3_endpoint}/{get_bucket_name(email)}/{document_id}"


def generate_upload_url(document_id: str, email: str) -> str:
    return _generate_presigned_url(document_id, email, "put_object")


def generate_download_url(document_id: str, email: str) -> str:
    return _generate_presigned_url(document_id, email, "get_object")
