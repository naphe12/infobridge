from functools import lru_cache
from pathlib import Path

from app.core.config import settings


class StorageConfigurationError(RuntimeError):
    pass


@lru_cache
def _s3_client():
    if not settings.s3_access_key_id or not settings.s3_secret_access_key:
        raise StorageConfigurationError("S3 credentials are not configured")
    if not settings.s3_bucket.strip():
        raise StorageConfigurationError("S3 bucket is not configured")
    import boto3
    from botocore.exceptions import ClientError

    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
    )
    if settings.s3_auto_create_bucket:
        try:
            client.head_bucket(Bucket=settings.s3_bucket)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if str(error_code) not in {"404", "NoSuchBucket", "NotFound"}:
                raise
            create_options = {"Bucket": settings.s3_bucket}
            if not settings.s3_endpoint_url and settings.s3_region != "us-east-1":
                create_options["CreateBucketConfiguration"] = {"LocationConstraint": settings.s3_region}
            client.create_bucket(**create_options)
    return client


def store_bytes(object_key: str, content: bytes) -> tuple[str, str]:
    backend = settings.document_storage_backend.lower()
    if backend == "s3":
        _s3_client().put_object(Bucket=settings.s3_bucket, Key=object_key, Body=content)
        return object_key, "s3"
    if backend != "local":
        raise StorageConfigurationError(f"Unknown document storage backend: {backend}")
    storage_dir = Path(settings.effective_document_storage_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / object_key
    file_path.write_bytes(content)
    return str(file_path), "local"


def read_bytes(file_path: str, storage_backend: str) -> bytes:
    backend = storage_backend.lower()
    if backend == "s3":
        response = _s3_client().get_object(Bucket=settings.s3_bucket, Key=file_path)
        return response["Body"].read()
    if backend != "local":
        raise StorageConfigurationError(f"Unknown document storage backend: {backend}")
    return Path(file_path).read_bytes()


def delete_bytes(file_path: str, storage_backend: str) -> None:
    backend = storage_backend.lower()
    if backend == "s3":
        _s3_client().delete_object(Bucket=settings.s3_bucket, Key=file_path)
        return
    if backend != "local":
        raise StorageConfigurationError(f"Unknown document storage backend: {backend}")

    storage_root = Path(settings.effective_document_storage_path).resolve()
    target = Path(file_path).resolve()
    if not target.is_relative_to(storage_root):
        raise StorageConfigurationError("Refusing to delete a document outside the configured storage directory")
    target.unlink(missing_ok=True)
