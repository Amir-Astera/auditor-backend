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
from app.modules.files.models import FileChunk
from app.modules.files.schemas import (
    FileListResponse,
    FileStatusResponse,
    FileUploadResponse,
)
from app.modules.files.service import FileService
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

    return FileService(db=db, storage=storage)


@router.post("/admin", status_code=201)
async def upload_admin_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    service = _get_file_service(db)

    try:
        stored_file = service.upload_admin_file(user, file)
    except Exception as e:
        logger.exception(
            "Admin file upload failed",
            extra={"user_id": str(getattr(user, "id", "")), "filename": getattr(file, "filename", "")},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload admin file: {e}",
        )

    # Ставим задачу в Arq асинхронно
    try:
        redis = await get_arq_redis()
        await redis.enqueue_job("index_file_task", str(stored_file.id))
    except Exception as e:
        logger.exception(
            "Failed to enqueue index_file_task for admin upload",
            extra={"stored_file_id": str(getattr(stored_file, "id", ""))},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue indexing job: {e}",
        )

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
async def upload_customer_file(
    customer_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_employee),
    service: FileService = Depends(_get_file_service),
):
    try:
        stored_file = service.upload_customer_file(
            user=user,
            customer_id=customer_id,
            file=file,
        )
    except Exception as e:
        logger.exception(
            "Customer file upload failed",
            extra={
                "user_id": str(getattr(user, "id", "")),
                "customer_id": customer_id,
                "filename": getattr(file, "filename", ""),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload customer file: {e}",
        )

    try:
        redis = await get_arq_redis()
        await redis.enqueue_job("index_file_task", str(stored_file.id))
    except Exception as e:
        logger.exception(
            "Failed to enqueue index_file_task for customer upload",
            extra={"stored_file_id": str(getattr(stored_file, "id", "")), "customer_id": customer_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue indexing job: {e}",
        )

    logger.info(
        "Index file task enqueued",
        extra={"stored_file_id": str(stored_file.id)},
    )

    return stored_file


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
    "/{file_id}",
    response_model=FileStatusResponse,
    summary="Статус файла (индексация)",
)
def get_file_status(
    file_id: UUID,
    user=Depends(get_current_user),
    service: FileService = Depends(_get_file_service),
):
    stored_file = service.get_file(file_id)
    if not stored_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    # Доступ: админ видит все, сотрудник — только свои customer docs
    if not getattr(user, "is_admin", False):
        if stored_file.scope.name == "ADMIN_LAW":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
            )
        if stored_file.owner_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
            )

    # Convert UUID to string for response
    return FileStatusResponse(
        id=str(stored_file.id),
        scope=stored_file.scope,
        customer_id=stored_file.customer_id,
        original_filename=stored_file.original_filename,
        is_indexed=stored_file.is_indexed,
        index_status=stored_file.index_status,
        index_error=stored_file.index_error,
    )


@router.get(
    "/{file_id}/chunks",
    summary="Чанки файла (для отладки и трассируемости)",
)
def list_file_chunks(
    file_id: UUID,
    limit: int = Query(200, ge=1, le=1000, description="Лимит чанков"),
    offset: int = Query(0, ge=0, description="Смещение"),
    user=Depends(get_current_user),
    service: FileService = Depends(_get_file_service),
):
    stored_file = service.get_file(file_id)
    if not stored_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    # Доступ: админ видит все, сотрудник — только свои customer docs
    if not getattr(user, "is_admin", False):
        if stored_file.scope.name == "ADMIN_LAW":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
            )
        if stored_file.owner_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
            )

    q = (
        service.db.query(FileChunk)
        .filter(FileChunk.file_id == stored_file.id)
        .order_by(FileChunk.chunk_index.asc())
        .limit(limit)
        .offset(offset)
    )
    chunks = q.all()

    return {
        "items": [
            {
                "chunk_index": c.chunk_index,
                "text": c.text,
                "qdrant_point_id": getattr(c, "qdrant_point_id", None),
                "lightrag_node_id": getattr(c, "lightrag_node_id", None),
                "created_at": c.created_at.isoformat()
                if getattr(c, "created_at", None)
                else None,
            }
            for c in chunks
        ],
        "total": len(chunks),
        "limit": limit,
        "offset": offset,
        "file_id": str(file_id),
    }


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

    # объект может быть HTTP-ответом minio, у которого есть release_conn
    if hasattr(obj, "release_conn"):
        obj.release_conn()

    from urllib.parse import quote

    original_filename = stored_file.original_filename
    ascii_fallback = original_filename.encode("ascii", "ignore").decode("ascii")
    if not ascii_fallback:
        ascii_fallback = "download"
    utf8_quoted = quote(original_filename, safe="")

    headers = {
        "Content-Disposition": (
            f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{utf8_quoted}'
        ),
    }
    return StreamingResponse(
        io.BytesIO(content),
        media_type=stored_file.content_type or "application/octet-stream",
        headers=headers,
    )


# Поиск по базе и генерация ответов теперь доступны через /rag/query.
# Здесь эндпоинт /files/admin/search удалён, чтобы не дублировать логику
# и не держать зависимость от векторного стора в файловом модуле.