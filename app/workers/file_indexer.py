from __future__ import annotations

from datetime import datetime
from typing import Any

from arq.connections import RedisSettings
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.modules.files.models import FileIndexStatus, StoredFile
from app.modules.files.qdrant_client import QdrantVectorStore
from app.modules.files.service_hybrid import HybridFileService
from app.modules.files.storage import FileStorage, S3Config
from app.modules.rag.gemini import GeminiAPI
from app.modules.rag.lightrag_integration import (
    LightRAGService,
    create_lightrag_service,
)

logger = get_logger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    """
    Worker startup hook.
    Prepares reusable clients/config in context.
    """
    configure_logging()
    logger.info("Hybrid file indexer worker starting up")

    ctx["storage_cfg"] = S3Config(
        endpoint_url=settings.S3_ENDPOINT_URL,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY,
        region=settings.S3_REGION,
        bucket_admin_laws=settings.S3_BUCKET_ADMIN_LAWS,
        bucket_customer_docs=settings.S3_BUCKET_CUSTOMER_DOCS,
    )

    # Gemini client (LLM + embeddings)
    ctx["gemini"] = GeminiAPI()

    # Qdrant vector store (hybrid retrieval)
    ctx["qdrant"] = QdrantVectorStore(
        url=settings.QDRANT_URL,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        vector_size=settings.QDRANT_VECTOR_SIZE,
    )

    # LightRAG (graph-based RAG). Optional.
    try:
        ctx["lightrag"] = create_lightrag_service(
            working_dir=settings.LIGHTRAG_WORKING_DIR,
            gemini_api=ctx["gemini"],
        )
        logger.info("LightRAG initialized in worker context")
    except Exception as e:
        ctx["lightrag"] = None
        logger.warning(
            "LightRAG is not available; worker will index only to Qdrant",
            extra={"error": str(e)},
        )


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("Hybrid file indexer worker shutting down")


async def index_file_task(ctx: dict[str, Any], file_id: str) -> None:
    """
    Main Arq job: indexes a StoredFile into Qdrant and LightRAG.

    - Updates StoredFile.index_status
    - Writes StoredFile.index_error on failures
    """
    configure_logging()
    logger.info("Index file task started", extra={"file_id": file_id})

    db: Session = SessionLocal()
    try:
        stored_file: StoredFile | None = db.query(StoredFile).get(file_id)
        if not stored_file:
            logger.warning("Stored file not found", extra={"file_id": file_id})
            return

        stored_file.index_status = FileIndexStatus.RUNNING
        stored_file.index_error = None
        db.commit()

        storage = FileStorage(cfg=ctx["storage_cfg"])
        gemini: GeminiAPI = ctx["gemini"]
        qdrant: QdrantVectorStore = ctx["qdrant"]
        lightrag: LightRAGService | None = ctx.get("lightrag")

        indexer = HybridFileService(
            db=db,
            storage=storage,
            vector_store=qdrant,
            lightrag_service=lightrag,
            gemini_api=gemini,
        )

        metrics = indexer.index_file(stored_file.id)

        # Determine success: at least one backend succeeded.
        q_ok = metrics.get("qdrant_status") in (None, "success")
        l_ok = metrics.get("lightrag_status") in (None, "success")

        stored_file = db.query(StoredFile).get(file_id)
        if stored_file:
            stored_file.is_indexed = bool(q_ok or l_ok)
            stored_file.index_status = (
                FileIndexStatus.DONE
                if stored_file.is_indexed
                else FileIndexStatus.ERROR
            )
            stored_file.index_error = (
                None
                if stored_file.is_indexed
                else (
                    metrics.get("error")
                    or metrics.get("qdrant_error")
                    or metrics.get("lightrag_error")
                    or "Indexing failed"
                )
            )
            stored_file.indexed_at = datetime.utcnow()
            db.commit()

        logger.info(
            "Index file task completed",
            extra={"file_id": file_id, "metrics": metrics},
        )

    except Exception as exc:
        logger.error(
            "Index file task failed",
            extra={"file_id": file_id, "error": str(exc)},
        )

        try:
            stored_file = db.query(StoredFile).get(file_id)
            if stored_file:
                stored_file.index_status = FileIndexStatus.ERROR
                stored_file.is_indexed = False
                stored_file.index_error = str(exc)
                stored_file.indexed_at = datetime.utcnow()
                db.commit()
        except Exception as inner_exc:
            logger.error(
                "Failed to update stored_file error status",
                extra={"file_id": file_id, "error": str(inner_exc)},
            )
    finally:
        db.close()


class WorkerSettings:
    functions = [index_file_task]
    on_startup = startup
    on_shutdown = shutdown

    # Arq expects RedisSettings (not Pydantic AnyUrl)
    redis_settings = RedisSettings.from_dsn(str(settings.REDIS_URL))
