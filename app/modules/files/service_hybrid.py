# app/modules/files/service_hybrid.py
"""
Production-ready гибридный FileService с Qdrant + LightRAG.
Включает batch processing, метрики времени и обработку ошибок.
"""

from __future__ import annotations

import io
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List

from qdrant_client.models import PointStruct
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.modules.files.file_text_extractor import extract_text
from app.modules.files.models import FileChunk, FileIndexStatus, FileScope, StoredFile
from app.modules.files.qdrant_client import QdrantVectorStore
from app.modules.files.storage import FileStorage
from app.modules.rag.gemini import GeminiAPI
from app.modules.rag.lightrag_integration import LightRAGService

logger = get_logger(__name__)


class EmbeddingProvider:
    """Production embedding provider with batch support."""

    def __init__(self, gemini_api: GeminiAPI):
        self.gemini = gemini_api

    def embed(self, text: str) -> List[float]:
        """Embed single text."""
        return self.gemini.embed_document(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch embed multiple texts."""
        return self.gemini.embed_documents(texts)


def chunk_text(text: str, chunk_size: int | None = None) -> List[str]:
    """Разбивает текст на чанки."""
    if chunk_size is None:
        chunk_size = settings.CHUNK_SIZE

    if not text:
        return []

    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk = text[i : i + chunk_size]
        if chunk.strip():
            chunks.append(chunk)

    return chunks


class HybridFileService:
    """
    Гибридный сервис индексации: Qdrant + LightRAG.

    Особенности:
    - Batch processing для эмбеддингов
    - Параллельная индексация в обе системы
    - Детальные метрики времени
    - Graceful degradation (если одна система упала)
    """

    def __init__(
        self,
        db: Session,
        storage: FileStorage,
        vector_store: QdrantVectorStore | None,
        lightrag_service: LightRAGService | None,
        gemini_api: GeminiAPI,
    ):
        self.db = db
        self.storage = storage
        self.vector_store = vector_store
        self.lightrag = lightrag_service
        self.embedding_provider = EmbeddingProvider(gemini_api)

    def upload_admin_file(self, user, file) -> StoredFile:
        """Загрузка файла админа (без индексации здесь)."""
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
            "Admin file uploaded",
            extra={
                "stored_file_id": str(stored_file.id),
                "size_bytes": stored_file.size_bytes,
            },
        )

        return stored_file

    def upload_customer_file(self, user, customer_id: str, file) -> StoredFile:
        """Загрузка файла заказчика."""
        logger.info(
            "Uploading customer file",
            extra={
                "user_id": str(user.id),
                "customer_id": customer_id,
                "file_name": file.filename,
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
            "Customer file uploaded",
            extra={
                "stored_file_id": str(stored_file.id),
                "customer_id": customer_id,
                "size_bytes": stored_file.size_bytes,
            },
        )

        return stored_file

    def index_file(self, file_id: uuid.UUID) -> Dict[str, Any]:
        """
        ГИБРИДНАЯ ИНДЕКСАЦИЯ: Qdrant + LightRAG.

        Returns:
            Метрики времени для каждого шага.
        """
        metrics = {
            "file_id": str(file_id),
            "started_at": time.time(),
            "times": {},
            "status": "started",
        }

        stored_file = self.db.query(StoredFile).get(file_id)
        if not stored_file:
            logger.warning("File not found", extra={"file_id": str(file_id)})
            return {"status": "error", "error": "File not found"}

        logger.info(
            "Starting hybrid indexing",
            extra={
                "file_id": str(file_id),
                "file_name": stored_file.original_filename,
                "size_bytes": stored_file.size_bytes,
            },
        )

        try:
            # ═══════════════════════════════════════════
            # ШАГ 1: СКАЧИВАНИЕ
            # ═══════════════════════════════════════════
            t_start = time.time()

            obj = self.storage.download_file(stored_file.bucket, stored_file.object_key)
            file_bytes = obj.read()

            if hasattr(obj, "close"):
                obj.close()
            if hasattr(obj, "release_conn"):
                obj.release_conn()

            metrics["times"]["download"] = time.time() - t_start

            # ═══════════════════════════════════════════
            # ШАГ 2: ПАРСИНГ
            # ═══════════════════════════════════════════
            t_start = time.time()

            text = extract_text(
                file_bytes=file_bytes,
                content_type=stored_file.content_type,
                filename=stored_file.original_filename,
            )

            metrics["times"]["parse"] = time.time() - t_start
            metrics["text_length"] = len(text)

            if not text:
                logger.warning("No text extracted")
                stored_file.is_indexed = False
                stored_file.index_error = "No text extracted"
                stored_file.index_status = FileIndexStatus.ERROR
                self.db.commit()
                return metrics

            # ═══════════════════════════════════════════
            # ШАГ 3: ЧАНКИНГ
            # ═══════════════════════════════════════════
            t_start = time.time()

            chunks = chunk_text(text, chunk_size=settings.CHUNK_SIZE)
            metrics["num_chunks"] = len(chunks)
            metrics["times"]["chunking"] = time.time() - t_start

            logger.info(
                f"Text chunked: {len(chunks)} chunks",
                extra={"file_id": str(file_id), "chunks": len(chunks)},
            )

            # Метаданные
            base_metadata = {
                "file_id": str(stored_file.id),
                "scope": stored_file.scope.value,
                "customer_id": stored_file.customer_id,
                "owner_id": str(stored_file.owner_id),
                "file_name": stored_file.original_filename,
            }

            # ═══════════════════════════════════════════
            # ШАГ 4: ИНДЕКСАЦИЯ В QDRANT
            # ═══════════════════════════════════════════
            if self.vector_store:
                t_start = time.time()

                try:
                    self._index_to_qdrant(
                        stored_file=stored_file,
                        chunks=chunks,
                        base_metadata=base_metadata,
                        metrics=metrics,
                    )

                    metrics["times"]["qdrant_total"] = time.time() - t_start
                    metrics["qdrant_status"] = "success"

                except Exception as e:
                    logger.exception("Qdrant indexing failed", extra={"file_id": str(file_id)})

                    metrics["qdrant_status"] = "failed"
                    metrics["qdrant_error"] = str(e)
            else:
                logger.warning(
                    "Qdrant vector store not available, skipping Qdrant indexing",
                    extra={"file_id": str(file_id)},
                )
                metrics["qdrant_status"] = "skipped"

            # ═══════════════════════════════════════════
            # ШАГ 5: ИНДЕКСАЦИЯ В LIGHTRAG
            # ═══════════════════════════════════════════
            if self.lightrag:
                t_start = time.time()

                try:
                    self._index_to_lightrag(
                        stored_file=stored_file,
                        chunks=chunks,
                        base_metadata=base_metadata,
                        metrics=metrics,
                    )

                    metrics["times"]["lightrag_total"] = time.time() - t_start
                    metrics["lightrag_status"] = "success"

                except Exception as e:
                    logger.exception("LightRAG indexing failed",
                     extra={"file_id": str(file_id)}
                     )

                    metrics["lightrag_status"] = "failed"
                    metrics["lightrag_error"] = str(e)
            else:
                logger.debug(
                    "LightRAG not available, skipping LightRAG indexing",
                    extra={"file_id": str(file_id)},
                )
                metrics["lightrag_status"] = "skipped"

            # ═══════════════════════════════════════════
            # ФИНАЛИЗАЦИЯ
            # ═══════════════════════════════════════════
            stored_file.is_indexed = True
            stored_file.index_status = FileIndexStatus.DONE
            stored_file.indexed_at = datetime.utcnow()
            self.db.commit()

            metrics["total_time"] = time.time() - metrics["started_at"]
            metrics["status"] = "success"

            logger.info(
                "Hybrid indexing completed",
                extra={
                    "file_id": str(file_id),
                    "total_time": metrics["total_time"],
                    "metrics": metrics,
                },
            )

            return metrics

        except Exception as exc:
            logger.exception(
                "Hybrid indexing failed",
                extra={"file_id": str(file_id)},
            )


            stored_file.is_indexed = False
            stored_file.index_error = str(exc)
            stored_file.index_status = FileIndexStatus.ERROR
            stored_file.indexed_at = datetime.utcnow()
            self.db.commit()

            metrics["status"] = "error"
            metrics["error"] = str(exc)
            return metrics

    def _index_to_qdrant(
        self,
        stored_file: StoredFile,
        chunks: List[str],
        base_metadata: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> None:
        """Индексация в Qdrant с batch embeddings."""

        # ШАГ 1: Batch эмбеддинги (БЫСТРО!)
        t_start = time.time()

        embeddings = self.embedding_provider.embed_batch(chunks)

        metrics["times"]["qdrant_embeddings"] = time.time() - t_start

        # ШАГ 2: Создание FileChunk + PointStruct
        t_start = time.time()

        qdrant_points = []

        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = FileChunk(
                file_id=stored_file.id,
                chunk_index=idx,
                text=chunk_text,
            )
            self.db.add(chunk)

            point_id = str(uuid.uuid4())
            chunk.qdrant_point_id = point_id

            qdrant_points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        **base_metadata,
                        "chunk_index": idx,
                        "text": chunk_text,
                    },
                )
            )

        self.db.commit()

        metrics["times"]["qdrant_prepare"] = time.time() - t_start

        # ШАГ 3: Batch upsert в Qdrant
        t_start = time.time()

        batch_size = settings.QDRANT_BATCH_SIZE
        num_batches = (len(qdrant_points) + batch_size - 1) // batch_size

        for i in range(0, len(qdrant_points), batch_size):
            batch = qdrant_points[i : i + batch_size]
            if self.vector_store is None:
                raise RuntimeError("vector_store is not configured")
            self.vector_store.upsert_vectors(batch)

        metrics["times"]["qdrant_upsert"] = time.time() - t_start
        metrics["qdrant_batches"] = num_batches

        logger.info(
            f"Indexed to Qdrant: {len(qdrant_points)} points in {num_batches} batches"
        )

    def _index_to_lightrag(
        self,
        stored_file: StoredFile,
        chunks: List[str],
        base_metadata: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> None:
        """Индексация в LightRAG с merge chunks.
        Важно: в insert() передаём СТРОКУ large_chunk, а не функцию chunk_text.
        """

        # Нечего индексировать
        if not chunks:
            metrics["lightrag_large_chunks"] = 0
            metrics["times"]["lightrag_merge"] = 0.0
            metrics["times"]["lightrag_insert"] = 0.0
            logger.info("LightRAG: no chunks to index")
            return

        # 1) Объединяем мелкие чанки в крупные блоки + запоминаем диапазоны индексов
        t_merge = time.time()

        merge_size = settings.MERGE_SIZE
        large_chunks: List[str] = []
        ranges: List[tuple[int, int]] = []

        for start_idx in range(0, len(chunks), merge_size):
            end_idx = min(start_idx + merge_size - 1, len(chunks) - 1)
            merged_text = "\n\n".join(chunks[start_idx : end_idx + 1])
            large_chunks.append(merged_text)
            ranges.append((start_idx, end_idx))

        metrics["lightrag_large_chunks"] = len(large_chunks)
        metrics["times"]["lightrag_merge"] = time.time() - t_merge

        # 2) Вставляем в LightRAG и проставляем lightrag_node_id для соответствующих FileChunk
        if self.lightrag is None:
            raise RuntimeError("lightrag service is not configured")

        t_insert = time.time()

        for group_idx, (large_chunk, (start_idx, end_idx)) in enumerate(zip(large_chunks, ranges)):
            # пропускаем пустые блоки
            if not large_chunk or not large_chunk.strip():
                logger.debug(f"LightRAG: skip empty large_chunk group={group_idx}")
                continue

            node_id = self.lightrag.insert(large_chunk)  # ✅ ВАЖНО: передаём строку

            # ✅ Проставляем node_id всем мелким чанкам этой группы
            self.db.query(FileChunk).filter(
                FileChunk.file_id == stored_file.id,
                FileChunk.chunk_index >= start_idx,
                FileChunk.chunk_index <= end_idx,
            ).update({"lightrag_node_id": node_id}, synchronize_session=False)

            logger.debug(
                f"LightRAG insert: chunk_group={group_idx}, node_id={node_id}, range=({start_idx}-{end_idx})"
            )

        self.db.commit()

        metrics["times"]["lightrag_insert"] = time.time() - t_insert
        logger.info(f"Indexed to LightRAG: {len(large_chunks)} large chunks")


    def get_file(self, file_id: uuid.UUID) -> StoredFile | None:
        """Получить файл по ID."""
        return self.db.query(StoredFile).get(file_id)

    def list_admin_files(self, search: str | None = None) -> List[StoredFile]:
        """Список административных файлов."""
        query = self.db.query(StoredFile).filter(
            StoredFile.scope == FileScope.ADMIN_LAW
        )
        if search:
            query = query.filter(StoredFile.original_filename.ilike(f"%{search}%"))
        return query.order_by(StoredFile.uploaded_at.desc()).all()

    def list_customer_files(
        self, customer_id: str, owner_id: str | None = None
    ) -> List[StoredFile]:
        """Список файлов заказчика."""
        query = self.db.query(StoredFile).filter(
            StoredFile.scope == FileScope.CUSTOMER_DOC,
            StoredFile.customer_id == customer_id,
        )
        if owner_id:
            query = query.filter(StoredFile.owner_id == owner_id)
        return query.order_by(StoredFile.uploaded_at.desc()).all()
