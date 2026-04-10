import requests
import boto3
from app.storage import generate_upload_url, get_s3_client, get_bucket_name

url = generate_upload_url("test-file-id", "test@unibo.it")
print("URL:", url)

res = requests.put(url, data="hello world", headers={'Content-Type': 'text/plain'})
print(res.status_code)
print(res.text)
