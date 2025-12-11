from __future__ import annotations

import io
import uuid
from typing import List

from sqlalchemy.orm import Session
from qdrant_client.models import PointStruct

from app.modules.files.models import FileChunk, FileScope, StoredFile
from app.modules.files.qdrant_client import QdrantVectorStore
from app.modules.files.storage import FileStorage


class EmbeddingProvider:
    """Stub embedding provider. Replace with actual model integration."""

    def __init__(self, vector_size: int):
        self.vector_size = vector_size

    def embed(self, text: str) -> List[float]:
        base = float(len(text) % 13 + 1)
        return [((i + 1) * base) % 7 for i in range(self.vector_size)]


def parse_file_to_text(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8")
    except Exception:
        return file_bytes.decode("utf-8", errors="ignore")


def chunk_text(text: str, chunk_size: int = 1500) -> List[str]:
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


class FileService:
    def __init__(
        self,
        db: Session,
        storage: FileStorage,
        vector_store: QdrantVectorStore,
        embedding_provider: EmbeddingProvider,
    ):
        self.db = db
        self.storage = storage
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider

    def upload_admin_file(self, user, file) -> StoredFile:
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
        )
        self.db.add(stored_file)
        self.db.commit()
        self.db.refresh(stored_file)
        self.index_file(stored_file.id)
        return stored_file

    def upload_customer_file(self, user, customer_id: str, file) -> StoredFile:
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
        )
        self.db.add(stored_file)
        self.db.commit()
        self.db.refresh(stored_file)
        self.index_file(stored_file.id)
        return stored_file

    def list_admin_files(self, search: str | None = None) -> List[StoredFile]:
        query = self.db.query(StoredFile).filter(StoredFile.scope == FileScope.ADMIN_LAW)
        if search:
            query = query.filter(StoredFile.original_filename.ilike(f"%{search}%"))
        return query.order_by(StoredFile.uploaded_at.desc()).all()

    def list_customer_files(self, customer_id: str, owner_id: str | None = None) -> List[StoredFile]:
        query = self.db.query(StoredFile).filter(
            StoredFile.scope == FileScope.CUSTOMER_DOC, StoredFile.customer_id == customer_id
        )
        if owner_id:
            query = query.filter(StoredFile.owner_id == owner_id)
        return query.order_by(StoredFile.uploaded_at.desc()).all()

    def get_file(self, file_id):
        return self.db.query(StoredFile).filter(StoredFile.id == file_id).first()

    def index_file(self, file_id) -> None:
        stored_file: StoredFile | None = self.get_file(file_id)
        if not stored_file:
            return
        try:
            obj = self.storage.download_file(stored_file.bucket, stored_file.object_key)
            file_bytes = obj.read()
            if hasattr(obj, "close"):
                obj.close()
            if hasattr(obj, "release_conn"):
                obj.release_conn()
            text = parse_file_to_text(file_bytes)
            chunks = chunk_text(text)
            points: list[PointStruct] = []
            for idx, chunk_text_value in enumerate(chunks):
                embedding = self.embedding_provider.embed(chunk_text_value)
                chunk = FileChunk(
                    file_id=stored_file.id,
                    chunk_index=idx,
                    text=chunk_text_value,
                )
                self.db.add(chunk)
                point_id = str(uuid.uuid4())
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "file_id": str(stored_file.id),
                            "chunk_index": idx,
                            "scope": stored_file.scope.value,
                            "customer_id": stored_file.customer_id,
                            "owner_id": str(stored_file.owner_id),
                        },
                    )
                )
                chunk.qdrant_point_id = point_id
            self.db.commit()
            if points:
                self.vector_store.upsert_vectors(points)
            stored_file.is_indexed = True
            stored_file.index_error = None
            self.db.commit()
        except Exception as exc:  # pragma: no cover - network bound
            stored_file.is_indexed = False
            stored_file.index_error = str(exc)
            self.db.commit()
