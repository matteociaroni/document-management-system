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


def get_tenant_folder(email: str) -> str:
    """Derive tenant folder from email domain"""
    if "@" not in email:
        raise ValueError(f"Invalid email format: {email}")
    domain = email.split("@")[1]
    return domain.replace(".", "-")


def _generate_presigned_url(document_id: str, email: str, operation: str, mime_type: str = None) -> str:
    """Generate presigned URL for upload (put_object) or download (get_object)"""
    try:
        s3 = get_s3_client()
        bucket = settings.gcp_bucket_name
        tenant_folder = get_tenant_folder(email)
        object_key = f"{tenant_folder}/{document_id}"
        
        try:
            s3.head_bucket(Bucket=bucket)
        except Exception as e:
            # SeaweedFS returns 404 on head_bucket for non-existent buckets
            error_code = getattr(e.response['Error'], 'Code', None) if hasattr(e, 'response') else None
            if '404' in str(e) or error_code == '404' or 'NoSuchBucket' in str(e):
                s3.create_bucket(Bucket=bucket)
            else:
                logger.error(f"S3 bucket head check failed: {e}")
                raise
            
        s3_ext = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name="us-east-1"
        )
        
        params = {"Bucket": bucket, "Key": object_key}
        if mime_type and operation == "put_object":
            params["ContentType"] = mime_type
            
        url = s3_ext.generate_presigned_url(
            operation,
            Params=params,
            ExpiresIn=3600
        )
        return url
    except Exception as e:
        logger.error(f"Failed to generate presigned URL ({operation}): {e}")
        return f"{settings.s3_endpoint}/{settings.gcp_bucket_name}/{get_tenant_folder(email)}/{document_id}"


def generate_upload_url(document_id: str, email: str, mime_type: str = None) -> str:
    return _generate_presigned_url(document_id, email, "put_object", mime_type)


def generate_download_url(document_id: str, email: str) -> str:
    return _generate_presigned_url(document_id, email, "get_object")
