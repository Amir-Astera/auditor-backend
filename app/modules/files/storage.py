from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error


@dataclass
class S3Config:
    endpoint_url: str
    access_key: str
    secret_key: str
    region: str
    bucket_admin_laws: str
    bucket_customer_docs: str


class FileStorage:
    def __init__(self, cfg: S3Config):
        self._cfg = cfg
        self._client = Minio(
            endpoint=cfg.endpoint_url.replace("http://", "").replace("https://", ""),
            access_key=cfg.access_key,
            secret_key=cfg.secret_key,
            secure=cfg.endpoint_url.startswith("https"),
            region=cfg.region,
        )
        self._ensure_bucket(cfg.bucket_admin_laws)
        self._ensure_bucket(cfg.bucket_customer_docs)

    def _ensure_bucket(self, bucket: str) -> None:
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)

    def upload_admin_file(
        self, file_obj: BinaryIO, object_key: str, content_type: str | None
    ) -> None:
        self._put_object(
            bucket=self._cfg.bucket_admin_laws,
            object_key=object_key,
            file_obj=file_obj,
            content_type=content_type,
        )

    def upload_customer_file(
        self,
        customer_id: str,
        file_obj: BinaryIO,
        object_key: str,
        content_type: str | None,
    ) -> None:
        path = f"{customer_id}/{object_key}"
        self._put_object(
            bucket=self._cfg.bucket_customer_docs,
            object_key=path,
            file_obj=file_obj,
            content_type=content_type,
        )

    def download_file(self, bucket: str, object_key: str) -> BinaryIO:
        try:
            response = self._client.get_object(bucket, object_key)
        except S3Error as exc:  # pragma: no cover - network bound
            raise FileNotFoundError(f"Object {object_key} not found in bucket {bucket}") from exc
        return response

    def _put_object(
        self, bucket: str, object_key: str, file_obj: BinaryIO, content_type: str | None
    ) -> None:
        # MinIO SDK requires length; -1 with part_size enables streaming unknown sizes
        self._client.put_object(
            bucket_name=bucket,
            object_name=object_key,
            data=file_obj,
            length=-1,
            part_size=10 * 1024 * 1024,
            content_type=content_type,
        )
