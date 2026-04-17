import boto3
s3 = boto3.client("s3", endpoint_url="http://s3:8333", aws_access_key_id="mykey", aws_secret_access_key="mysecret", region_name="us-east-1")
try:
    print(s3.head_object(Bucket="unibo-it", Key="bf23fe5d-279f-43ed-8515-e717ca7ab3a0"))
except Exception as e:
    print("head object error:", e)

try:
    print(s3.head_bucket(Bucket="unibo-it"))
except Exception as e:
    print("head bucket error:", e)
