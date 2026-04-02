from google.cloud import storage
from datetime import timedelta
import base64
from urllib.parse import urlparse


def get_signed_url(bucket: str, blob: str) -> str:
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket)
    blob = bucket.blob(blob)
    expiration_time = timedelta(minutes=15) # max is 7 days

    signed_url = blob.generate_signed_url(
        version='v4',
        expiration=expiration_time,
        method='GET'
    )

    return signed_url


def get_base64_image(bucket: str, blob: str) -> str:
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket)
    blob = bucket.blob(blob)
    image_bytes = blob.download_as_bytes()
    encoded_string = base64.b64encode(image_bytes).decode('utf-8')
    
    return encoded_string


def parse_non_gcs_url(url:str):
    path = urlparse(str(url)).path.lstrip('/')
    parts = path.split('/', 1)
    bucket_name = parts[0]
    blob_name = parts[1] if len(parts) > 1 else ''
    filename = blob_name.split('/')[-1]

    return bucket_name, blob_name, filename


# bucket, blob = parse_gcs_url(url)


# uri = "gs://bucket_name/dir1/dir2/file.png"
# blob = storage.Blob.from_string(uri, client=storage.Client())

# print(f"Bucket: {blob.bucket.name}")
# print(f"Blob: {blob.name}")