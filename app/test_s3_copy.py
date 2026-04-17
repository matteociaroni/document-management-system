import boto3
s3 = boto3.client("s3", endpoint_url="http://s3:8333", aws_access_key_id="mykey", aws_secret_access_key="mysecret", region_name="us-east-1")
try:
    s3.create_bucket(Bucket="old-example-com")
    s3.create_bucket(Bucket="new-example-com")
except Exception:
    pass
s3.put_object(Bucket="old-example-com", Key="bf23fe5d-279f-43ed-8515-e717ca7ab3a0", Body=b"hello")

try:
    s3.copy_object(
        CopySource="old-example-com/bf23fe5d-279f-43ed-8515-e717ca7ab3a0",
        Bucket="new-example-com",
        Key="new-uuid"
    )
    print("worked string")
except Exception as e:
    print("failed string:", e)
