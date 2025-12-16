from __future__ import annotations

import io
import uuid
from typing import List, cast

from qdrant_client.models import Filter, PointStruct, ScoredPoint
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.modules.files.file_text_extractor import extract_text
from app.modules.files.models import FileChunk, FileScope, StoredFile
from app.modules.files.qdrant_client import QdrantVectorStore
from app.modules.files.storage import FileStorage

logger = get_logger(__name__)


class EmbeddingProvider:
    """Stub embedding provider. Replace with actual model integration."""

    def __init__(self, vector_size: int):
        self.vector_size = vector_size

    def embed(self, text: str) -> List[float]:
        base = float(len(text) % 13 + 1)
        return [((i + 1) * base) % 7 for i in range(self.vector_size)]


def chunk_text(text: str, chunk_size: int = 1500) -> List[str]:
    """
    Делит текст на чанки.
    Можно улучшить, чтобы резать по предложениям/абзацам, но как базовый вариант ок.
    """
    if not text:
        return []
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

        from app.modules.files.models import FileIndexStatus

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
            "Admin file stored metadata saved",
            extra={
                "stored_file_id": str(stored_file.id),
                "bucket": stored_file.bucket,
                "object_key": stored_file.object_key,
                "size_bytes": stored_file.size_bytes,
            },
        )

        # ВАЖНО: больше не вызываем self.index_file здесь!
        return stored_file

    def upload_customer_file(self, user, customer_id: str, file) -> StoredFile:
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

        from app.modules.files.models import FileIndexStatus

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
            "Customer file stored metadata saved",
            extra={
                "stored_file_id": str(stored_file.id),
                "customer_id": customer_id,
                "bucket": stored_file.bucket,
                "object_key": stored_file.object_key,
                "size_bytes": stored_file.size_bytes,
            },
        )

        # Индексация делается асинхронно воркером Arq
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

    def index_file(self, file_id) -> None:
        stored_file: StoredFile | None = self.get_file(file_id)
        if not stored_file:
            logger.warning(
                "File not found for indexing",
                extra={"file_id": str(file_id)},
            )
            return

        logger.info(
            "Starting file indexing",
            extra={
                "stored_file_id": str(stored_file.id),
                "scope": stored_file.scope.value,
                "bucket": stored_file.bucket,
                "object_key": stored_file.object_key,
                "content_type": stored_file.content_type,
            },
        )

        try:
            obj = self.storage.download_file(stored_file.bucket, stored_file.object_key)

            file_bytes = obj.read()

            if hasattr(obj, "close"):
                obj.close()

            # объект может быть HTTP-ответом minio, у которого есть release_conn,

            # но статический анализатор видит BinaryIO, поэтому помечаем вызов для игнора

            if hasattr(obj, "release_conn"):  # type: ignore[attr-defined]
                obj.release_conn()

            # Извлекаем "чистый" текст из файла (docx/pdf/txt/...)
            text = extract_text(
                file_bytes=file_bytes,
                content_type=stored_file.content_type,
                filename=stored_file.original_filename,
            )

            if not text:
                logger.warning(
                    "No text extracted from file, skipping indexing",
                    extra={"stored_file_id": str(stored_file.id)},
                )
                stored_file.is_indexed = False
                stored_file.index_error = "No text extracted from file"
                self.db.commit()
                return

            chunks = chunk_text(text)
            logger.info(
                "Text chunked for indexing",
                extra={
                    "stored_file_id": str(stored_file.id),
                    "chunks": len(chunks),
                    "text_length": len(text),
                },
            )

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

            logger.info(
                "File chunks saved to DB",
                extra={
                    "stored_file_id": str(stored_file.id),
                    "chunks": len(chunks),
                },
            )

            if points:
                self.vector_store.upsert_vectors(points)
                logger.info(
                    "Vectors upserted to Qdrant",
                    extra={
                        "stored_file_id": str(stored_file.id),
                        "points": len(points),
                    },
                )

            stored_file.is_indexed = True
            stored_file.index_error = None
            self.db.commit()

            logger.info(
                "File indexing completed successfully",
                extra={"stored_file_id": str(stored_file.id)},
            )

        except Exception as exc:  # pragma: no cover - network bound
            logger.error(
                "File indexing failed",
                extra={
                    "stored_file_id": str(stored_file.id),
                    "error": str(exc),
                },
            )
            stored_file.is_indexed = cast(bool, False)
            stored_file.index_error = str(exc)
            self.db.commit()

        def search_chunks(
            self,
            query: str,
            limit: int = 5,
            scope: FileScope | None = None,
            customer_id: str | None = None,
            owner_id: str | None = None,
        ) -> list[dict[str, Any]]:
            """
            Выполнить семантический поиск по индексированным чанкам файлов.

            - query: текст запроса
            - limit: максимальное количество результатов
            - scope: ADMIN_LAW / CUSTOMER_DOC (ограничить поиск по типу файла)
            - customer_id: ограничить поиск по заказчику
            - owner_id: ограничить поиск по владельцу (для сотрудников)
            """
            # 1. Эмбеддинг запроса
            query_vector = self.embedding_provider.embed(query)

            # 2. Фильтр по payload
            q_filter: Filter | None = self.vector_store.build_filter(
                scope=scope.value if scope else None,
                customer_id=customer_id,
                owner_id=str(owner_id) if owner_id is not None else None,
            )

            # 3. Поиск в Qdrant
            points: list[ScoredPoint] = self.vector_store.search(
                query_vector=query_vector,
                limit=limit,
                filter_=q_filter,
            )

            if not points:
                return []

            # 4. Подтягиваем чанки и файлы из БД
            results: list[dict[str, Any]] = []

            for point in points:
                payload = point.payload or {}
                file_id = payload.get("file_id")
                chunk_index = payload.get("chunk_index")

                if not file_id:
                    continue

                chunk = (
                    self.db.query(FileChunk)
                    .filter(
                        FileChunk.file_id == file_id,
                        FileChunk.chunk_index == chunk_index,
                    )
                    .first()
                )
                if not chunk:
                    continue

                stored_file = self.db.query(StoredFile).get(file_id)

                results.append(
                    {
                        "score": point.score,
                        "file_id": file_id,
                        "chunk_index": chunk_index,
                        "text": chunk.text,
                        "filename": stored_file.original_filename
                        if stored_file
                        else None,
                        "scope": payload.get("scope"),
                        "customer_id": payload.get("customer_id"),
                        "owner_id": payload.get("owner_id"),
                    }
                )

            return results

