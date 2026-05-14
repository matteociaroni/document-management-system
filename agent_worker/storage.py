import boto3
from config import settings




def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1",
    )


def get_tenant_folder(email: str) -> str:
    """Derive document bucket name from user email domain (mirrors backend logic)."""
    domain = email.split("@")[1]
    return domain.replace(".", "-")


def load_eml(storage_key: str) -> bytes:
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=settings.gcp_bucket_name, Key=storage_key)
    return obj["Body"].read()


def load_document(tenant_folder: str, document_id: str) -> bytes:
    """Download a document's bytes from the user's tenant folder."""
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=settings.gcp_bucket_name, Key=f"{tenant_folder}/{document_id}")
    return obj["Body"].read()


def ensure_bucket(s3, bucket: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception as e:
        if "404" in str(e) or "NoSuchBucket" in str(e) or "Not Found" in str(e):
            s3.create_bucket(Bucket=bucket)
        else:
            raise
