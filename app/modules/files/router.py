import io
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.helpers.helpers import get_arq_redis
from app.core.logging import get_logger
from app.modules.auth.models import User
from app.modules.auth.router import (
    get_current_admin,
    get_current_employee,
    get_current_user,
)
from app.modules.files.models import FileScope
from app.modules.files.qdrant_client import QdrantVectorStore
from app.modules.files.schemas import (
    ChunkSearchResponse,
    FileListResponse,
    FileUploadResponse,
)
from app.modules.files.service import EmbeddingProvider, FileService
from app.modules.files.storage import FileStorage, S3Config

logger = get_logger(__name__)


router = APIRouter(prefix="/files", tags=["files"])


def _get_file_service(db: Session = Depends(get_db)) -> FileService:
    storage = FileStorage(
        S3Config(
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            region=settings.S3_REGION,
            bucket_admin_laws=settings.S3_BUCKET_ADMIN_LAWS,
            bucket_customer_docs=settings.S3_BUCKET_CUSTOMER_DOCS,
        )
    )

    vector_store = QdrantVectorStore(
        url=settings.QDRANT_URL,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        vector_size=settings.QDRANT_VECTOR_SIZE,
    )

    embedding_provider = EmbeddingProvider(vector_size=settings.QDRANT_VECTOR_SIZE)

    return FileService(
        db=db,
        storage=storage,
        vector_store=vector_store,
        embedding_provider=embedding_provider,
    )


@router.post("/admin", status_code=201)
async def upload_admin_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    service = _get_file_service(db)

    stored_file = service.upload_admin_file(user, file)

    # Ставим задачу в Arq асинхронно

    redis = await get_arq_redis()

    await redis.enqueue_job("index_file_task", str(stored_file.id))

    logger.info(
        "Index file task enqueued",
        extra={"stored_file_id": str(stored_file.id)},
    )

    return stored_file


@router.post(
    "/customers/{customer_id}",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузка файла заказчика",
)
def upload_customer_file(
    customer_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_employee),
    service: FileService = Depends(_get_file_service),
):
    return service.upload_customer_file(user=user, customer_id=customer_id, file=file)


@router.get(
    "/admin",
    response_model=FileListResponse,
    summary="Список административных файлов",
)
def list_admin_files(
    search: str | None = Query(default=None, description="Фильтр по имени файла"),
    user=Depends(get_current_user),
    service: FileService = Depends(_get_file_service),
):
    files = service.list_admin_files(search=search)
    # Pydantic сам сконвертирует StoredFile -> FileInfo (через orm_mode)
    return {"items": files, "total": len(files)}


@router.get(
    "/customers/{customer_id}",
    response_model=FileListResponse,
    summary="Список файлов по заказчику",
)
def list_customer_files(
    customer_id: str,
    user=Depends(get_current_user),
    service: FileService = Depends(_get_file_service),
):
    owner_id = None if getattr(user, "is_admin", False) else user.id
    files = service.list_customer_files(customer_id=customer_id, owner_id=owner_id)
    return {"items": files, "total": len(files)}


@router.get(
    "/{file_id}/download",
    response_class=StreamingResponse,
    summary="Скачать файл",
)
def download_file(
    file_id: UUID,
    user=Depends(get_current_user),
    service: FileService = Depends(_get_file_service),
):
    stored_file = service.get_file(file_id)
    if not stored_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    if not getattr(user, "is_admin", False):
        if stored_file.scope.name == "ADMIN_LAW":
            pass
        elif stored_file.owner_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
            )

    obj = service.storage.download_file(stored_file.bucket, stored_file.object_key)

    content = obj.read()

    if hasattr(obj, "close"):
        obj.close()

    # объект может быть HTTP-ответом minio, у которого есть release_conn, но
    # статический анализатор видит BinaryIO, поэтому доступны проверка и вызов только в рантайме
    if hasattr(obj, "release_conn"):  # type: ignore[attr-defined]
        obj.release_conn()

    headers = {
        "Content-Disposition": f"attachment; filename={stored_file.original_filename}",
    }
    return StreamingResponse(
        io.BytesIO(content),
        media_type=stored_file.content_type or "application/octet-stream",
        headers=headers,
    )


@router.get(
    "/admin/search",
    response_model=ChunkSearchResponse,
    summary="Поиск по административным файлам (семантический)",
)
def search_admin_files(
    query: str = Query(..., description="Поисковый запрос"),
    limit: int = Query(5, ge=1, le=50),
    user: User = Depends(get_current_admin),
    service: FileService = Depends(_get_file_service),
):
    """
    Семантический поиск по проиндексированным административным файлам.
    """
    results = service.search_chunks(
        query=query,
        limit=limit,
        scope=FileScope.ADMIN_LAW,
    )
    return {
        "items": results,
        "total": len(results),
    }