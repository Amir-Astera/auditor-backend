from __future__ import annotations

import asyncio
import uuid
from typing import Any

from arq import cron
from arq.connections import ArqRedis, RedisSettings, create_pool
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.modules.files.models import FileIndexStatus, StoredFile
from app.modules.files.qdrant_client import QdrantVectorStore
from app.modules.files.service import EmbeddingProvider, FileService
from app.modules.files.storage import FileStorage, S3Config
from app.modules.files.file_text_extractor import extract_text
from app.modules.rag.lightrag_integration import create_lightrag_service
from app.modules.embeddings.service import get_embedding_service
from app.modules.rag.gemini import GeminiAPI

logger = get_logger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    """
    Инициализация контекста воркера.
    Здесь можно подготовить тяжёлые клиенты, если нужно.
    """
    configure_logging()
    logger.info("File indexer worker starting up")

    import app.modules.auth.models as _auth_models

    ctx["storage_cfg"] = S3Config(
        endpoint_url=settings.S3_ENDPOINT_URL,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY,
        region=settings.S3_REGION,
        bucket_admin_laws=settings.S3_BUCKET_ADMIN_LAWS,
        bucket_customer_docs=settings.S3_BUCKET_CUSTOMER_DOCS,
    )

    ctx["qdrant"] = QdrantVectorStore(
        url=settings.QDRANT_URL,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        vector_size=settings.QDRANT_VECTOR_SIZE,
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("File indexer worker shutting down")


async def index_file_task(ctx: dict[str, Any], file_id: str) -> None:
    """
    Основная задача Arq для индексации файла.
    """
    configure_logging()
    logger.info("Index file task started", extra={"file_id": file_id})

    try:
        file_uuid = uuid.UUID(file_id)
    except Exception:
        logger.error("Invalid file_id (expected UUID)", extra={"file_id": file_id})
        return

    db: Session = SessionLocal()  # новая сессия для воркера
    try:
        storage = FileStorage(cfg=ctx["storage_cfg"])
        vector_store: QdrantVectorStore = ctx["qdrant"]
        embedding_provider = EmbeddingProvider(vector_store.vector_size)

        service = FileService(
            db=db,
            storage=storage,
            vector_store=vector_store,
            embedding_provider=embedding_provider,
        )

        # Обновляем статус файла -> RUNNING
        stored_file: StoredFile | None = db.get(StoredFile, file_uuid)
        if not stored_file:
            logger.warning("Stored file not found", extra={"file_id": file_id})
            return

        stored_file.index_status = FileIndexStatus.RUNNING
        db.commit()

        # Синхронная индексация внутри воркера (можно асинхронизировать позже)
        service.index_file(file_uuid)

        # index_file сам проставляет is_indexed/index_error, здесь можно добить статус/время
        stored_file = db.get(StoredFile, file_uuid)
        if stored_file and stored_file.is_indexed and not stored_file.index_error:
            from datetime import datetime

            stored_file.index_status = FileIndexStatus.DONE
            stored_file.indexed_at = datetime.utcnow()
            db.commit()

            # LightRAG second-signal indexing (best-effort)
            try:
                obj = storage.download_file(stored_file.bucket, stored_file.object_key)
                file_bytes = obj.read()
                if hasattr(obj, "close"):
                    obj.close()
                if hasattr(obj, "release_conn"):  # type: ignore[attr-defined]
                    obj.release_conn()

                text = extract_text(
                    file_bytes=file_bytes,
                    content_type=stored_file.content_type,
                    filename=stored_file.original_filename,
                )

                if text:
                    scope = stored_file.scope.value
                    if scope == "ADMIN_LAW":
                        workspace = "admin_law"
                    else:
                        workspace = f"customer_{stored_file.customer_id}"

                    lightrag = create_lightrag_service(
                        working_dir="./lightrag_cache",
                        workspace=workspace,
                        gemini_api=GeminiAPI(),
                        embedding_service=get_embedding_service(),
                    )

                    await lightrag.ainsert(
                        text=text,
                        file_path=stored_file.original_filename or f"{scope}/{stored_file.id}",
                    )
            except Exception as exc:
                logger.warning(
                    "LightRAG second-signal indexing failed",
                    extra={"file_id": file_id, "error": str(exc)},
                )

        logger.info(
            "Index file task completed",
            extra={
                "file_id": file_id,
                "status": stored_file.index_status if stored_file else None,
            },
        )

    except Exception as exc:
        logger.exception(
            "Index file task failed",
            extra={"file_id": file_id, "error": str(exc)},
        )
        # Пытаемся зафиксировать ошибку в БД
        try:
            db.rollback()
            stored_file = db.get(StoredFile, file_uuid)
            if stored_file:
                stored_file.index_status = FileIndexStatus.ERROR
                stored_file.is_indexed = False
                stored_file.index_error = str(exc)
                db.commit()
        except Exception as inner_exc:
            logger.exception(
                "Failed to update stored_file error status",
                extra={"file_id": file_id, "error": str(inner_exc)},
            )
    finally:
        db.close()


class WorkerSettings:
    functions = [index_file_task]
    on_startup = startup
    on_shutdown = shutdown

    # Передаём либо RedisSettings, либо именно строку (но не AnyUrl)
    redis_settings = RedisSettings.from_dsn(str(settings.REDIS_URL))


async def create_redis_pool() -> ArqRedis:
    return await create_pool(RedisSettings.from_dsn(str(settings.REDIS_URL)))

