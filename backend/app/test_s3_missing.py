import boto3
s3 = boto3.client("s3", endpoint_url="http://s3:8333", aws_access_key_id="mykey", aws_secret_access_key="mysecret", region_name="us-east-1")
try:
    s3.copy_object(CopySource="unibo-it/non-existent-key", Bucket="unibo-it", Key="new-key")
except Exception as e:
    print("copy of missing object error:", e)
