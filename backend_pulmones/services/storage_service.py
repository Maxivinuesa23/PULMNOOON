import boto3

from core.config import (
    S3_ACCESS_KEY_ID,
    S3_BUCKET,
    S3_ENDPOINT_URL,
    S3_REGION,
    S3_SECRET_ACCESS_KEY,
)


def upload_zip(file_path: str, object_key: str) -> str:
    """Upload a tomography archive and return its bucket object key."""
    client = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT_URL,
        region_name=S3_REGION,
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
    )
    client.upload_file(
        file_path,
        S3_BUCKET,
        object_key,
        ExtraArgs={"ContentType": "application/zip"},
    )
    return object_key
