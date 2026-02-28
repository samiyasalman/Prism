import uuid

import ibm_boto3
from ibm_botocore.client import Config

from app.config import settings


def _get_cos_client():
    return ibm_boto3.client(
        "s3",
        ibm_api_key_id=settings.cos_api_key,
        ibm_service_instance_id=settings.cos_instance_id,
        config=Config(signature_version="oauth"),
        endpoint_url=settings.cos_endpoint,
    )


def upload_to_cos(file_bytes: bytes, filename: str, content_type: str) -> str:
    client = _get_cos_client()
    key = f"uploads/{uuid.uuid4()}/{filename}"
    client.put_object(
        Bucket=settings.cos_bucket,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return key


def get_cos_uri(key: str) -> str:
    return f"cos://{settings.cos_bucket}/{key}"


def download_from_cos(key: str) -> bytes:
    client = _get_cos_client()
    response = client.get_object(Bucket=settings.cos_bucket, Key=key)
    return response["Body"].read()
