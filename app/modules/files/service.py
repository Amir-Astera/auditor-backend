from __future__ import annotations

import io
import uuid
from typing import List

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.modules.files.models import FileIndexStatus, FileScope, StoredFile
from app.modules.files.storage import FileStorage

logger = get_logger(__name__)


class FileService:
    """
    File CRUD-only service.

    Responsibilities:
    - Upload files to object storage (MinIO/S3)
    - Create and query StoredFile records in Postgres

    Non-responsibilities (moved elsewhere):
    - Indexing/chunking/embeddings/vector DB (Qdrant/LightRAG)
    - Semantic search
    """

    def __init__(self, db: Session, storage: FileStorage):
        self.db = db
        self.storage = storage

    def upload_admin_file(self, user, file) -> StoredFile:
        """
        Upload an admin (law/standard) file and create a StoredFile record.
        Indexing is handled asynchronously by a worker (Arq) after the upload.
        """
        logger.info(
            "Uploading admin file",
            extra={
                "user_id": str(user.id),
                "file_name": file.filename,
                "content_type": file.content_type,
            },
        )

        content = file.file.read()
        object_key = f"{uuid.uuid4()}_{file.filename}"

        self.storage.upload_admin_file(
            file_obj=io.BytesIO(content),
            object_key=object_key,
            content_type=file.content_type,
        )

        stored_file = StoredFile(
            owner_id=user.id,
            customer_id=None,
            scope=FileScope.ADMIN_LAW,
            bucket=self.storage._cfg.bucket_admin_laws,
            object_key=object_key,
            original_filename=file.filename,
            content_type=file.content_type,
            size_bytes=len(content),
            is_indexed=False,
            index_error=None,
            index_status=FileIndexStatus.QUEUED,
        )

        self.db.add(stored_file)
        self.db.commit()
        self.db.refresh(stored_file)

        logger.info(
            "Admin file stored",
            extra={
                "stored_file_id": str(stored_file.id),
                "bucket": stored_file.bucket,
                "object_key": stored_file.object_key,
                "size_bytes": stored_file.size_bytes,
            },
        )

        return stored_file

    def upload_customer_file(self, user, customer_id: str, file) -> StoredFile:
        """
        Upload a customer document and create a StoredFile record.
        Indexing is handled asynchronously by a worker (Arq) after the upload.
        """
        logger.info(
            "Uploading customer file",
            extra={
                "user_id": str(user.id),
                "customer_id": customer_id,
                "file_name": file.filename,
                "content_type": file.content_type,
            },
        )

        content = file.file.read()
        object_key = f"{uuid.uuid4()}_{file.filename}"

        self.storage.upload_customer_file(
            customer_id=customer_id,
            file_obj=io.BytesIO(content),
            object_key=object_key,
            content_type=file.content_type,
        )

        stored_file = StoredFile(
            owner_id=user.id,
            customer_id=customer_id,
            scope=FileScope.CUSTOMER_DOC,
            bucket=self.storage._cfg.bucket_customer_docs,
            object_key=f"{customer_id}/{object_key}",
            original_filename=file.filename,
            content_type=file.content_type,
            size_bytes=len(content),
            is_indexed=False,
            index_error=None,
            index_status=FileIndexStatus.QUEUED,
        )

        self.db.add(stored_file)
        self.db.commit()
        self.db.refresh(stored_file)

        logger.info(
            "Customer file stored",
            extra={
                "stored_file_id": str(stored_file.id),
                "customer_id": customer_id,
                "bucket": stored_file.bucket,
                "object_key": stored_file.object_key,
                "size_bytes": stored_file.size_bytes,
            },
        )

        return stored_file

    def list_admin_files(self, search: str | None = None) -> List[StoredFile]:
        query = self.db.query(StoredFile).filter(
            StoredFile.scope == FileScope.ADMIN_LAW
        )
        if search:
            query = query.filter(StoredFile.original_filename.ilike(f"%{search}%"))
        return query.order_by(StoredFile.uploaded_at.desc()).all()

    def list_customer_files(
        self, customer_id: str, owner_id: str | None = None
    ) -> List[StoredFile]:
        query = self.db.query(StoredFile).filter(
            StoredFile.scope == FileScope.CUSTOMER_DOC,
            StoredFile.customer_id == customer_id,
        )
        if owner_id:
            query = query.filter(StoredFile.owner_id == owner_id)
        return query.order_by(StoredFile.uploaded_at.desc()).all()

    def get_file(self, file_id):
        return self.db.query(StoredFile).filter(StoredFile.id == file_id).first()
