import boto3
from config import settings

EML_BUCKET = "email-eml-storage"


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1",
    )


def get_bucket_name(email: str) -> str:
    """Derive document bucket name from user email domain (mirrors backend logic)."""
    domain = email.split("@")[1]
    return domain.replace(".", "-")


def load_eml(storage_key: str) -> bytes:
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=EML_BUCKET, Key=storage_key)
    return obj["Body"].read()


def ensure_bucket(s3, bucket: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception as e:
        if "404" in str(e) or "NoSuchBucket" in str(e) or "Not Found" in str(e):
            s3.create_bucket(Bucket=bucket)
        else:
            raise
