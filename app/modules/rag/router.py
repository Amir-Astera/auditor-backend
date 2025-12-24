"""RAG router with LIGHTRAG endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.modules.auth.models import User
from app.modules.auth.router import get_current_user
from app.modules.files.qdrant_client import QdrantVectorStore
from app.modules.prompts.service import PromptService
from app.modules.rag.gemini import GeminiAPI
from app.modules.rag.schemas import (
    RAGDeleteResponse,
    RAGEvidenceRequest,
    RAGEvidenceResponse,
    RAGGraphStatsResponse,
    RAGInsertRequest,
    RAGInsertResponse,
    RAGQueryRequest,
    RAGQueryResponse,
)
from app.modules.rag.service import RAGService

router = APIRouter(prefix="/rag", tags=["rag"])


def _get_rag_service(db: Session = Depends(get_db)) -> RAGService:
    """
    Создает экземпляр RAGService c DB-backed PromptService и Qdrant store.
    """
    gemini_api = GeminiAPI()

    prompts = PromptService(db)

    admin_collection = settings.QDRANT_COLLECTION_ADMIN or settings.QDRANT_COLLECTION_NAME
    client_collection = settings.QDRANT_COLLECTION_CLIENT or settings.QDRANT_COLLECTION_NAME

    qdrant_admin = QdrantVectorStore(
        url=settings.QDRANT_URL,
        collection_name=admin_collection,
        vector_size=settings.QDRANT_VECTOR_SIZE,
    )
    qdrant_client = QdrantVectorStore(
        url=settings.QDRANT_URL,
        collection_name=client_collection,
        vector_size=settings.QDRANT_VECTOR_SIZE,
    )

    return RAGService(
        gemini_api=gemini_api,
        prompts=prompts,
        qdrant_admin=qdrant_admin,
        qdrant_client=qdrant_client,
        lightrag_working_dir=settings.LIGHTRAG_WORKING_DIR,
        db=db,
    )


@router.post(
    "/query",
    response_model=RAGQueryResponse,
    summary="Запрос к RAG системе",
    description="Выполняет гибридный RAG-запрос (Qdrant evidence + Gemini) и возвращает ответ с контекстом",
)
async def query_rag(
    request: RAGQueryRequest,
    service: RAGService = Depends(_get_rag_service),
    user: User = Depends(get_current_user),
):
    """
    Выполняет запрос к RAG системе.

    Режимы:
    - hybrid: Qdrant (evidence) + Gemini (answer), с опциональным LightRAG enrichment
    - qdrant: только Qdrant retrieval + Gemini generation
    - lightrag: только LightRAG (если доступен) + Gemini generation/fallback
    """
    try:
        owner_id = None if getattr(user, "is_admin", False) else str(user.id)
        if owner_id is not None and request.include_admin_laws:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: employees cannot query admin laws",
            )

        result = service.query(
            question=request.question,
            mode=request.mode,
            top_k=request.top_k,
            customer_id=request.customer_id,
            include_admin_laws=request.include_admin_laws,
            include_customer_docs=request.include_customer_docs,
            temperature=request.temperature,
            owner_id=owner_id,
        )
        return RAGQueryResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error querying RAG: {str(e)}",
        )


@router.post(
    "/evidence",
    response_model=RAGEvidenceResponse,
    summary="RAG: retrieval-only (без генерации)",
    description="Делает только retrieval (Qdrant/LightRAG) и возвращает контекст без вызова LLM",
)
async def rag_evidence(
    request: RAGEvidenceRequest,
    service: RAGService = Depends(_get_rag_service),
    user: User = Depends(get_current_user),
):
    """
    Retrieval-only endpoint для отладки и трассируемости.
    """
    try:
        owner_id = None if getattr(user, "is_admin", False) else str(user.id)
        if owner_id is not None and request.include_admin_laws:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: employees cannot query admin laws",
            )

        result = service.evidence(
            question=request.question,
            mode=request.mode,
            top_k=request.top_k,
            customer_id=request.customer_id,
            include_admin_laws=request.include_admin_laws,
            include_customer_docs=request.include_customer_docs,
            owner_id=owner_id,
        )
        return RAGEvidenceResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving evidence: {str(e)}",
        )


@router.post(
    "/insert",
    response_model=RAGInsertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Вставка текста в граф знаний",
    description="Добавляет текст в граф знаний LIGHTRAG для последующего использования в запросах",
)
async def insert_text(
    request: RAGInsertRequest,
    service: RAGService = Depends(_get_rag_service),
    _=Depends(get_current_user),
):
    """Вставляет текст в граф знаний LIGHTRAG."""
    try:
        result = service.insert_text(
            text=request.text,
            metadata=request.metadata,
        )
        return RAGInsertResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inserting text: {str(e)}",
        )


@router.delete(
    "/node/{node_id}",
    response_model=RAGDeleteResponse,
    summary="Удаление узла из графа",
    description="Удаляет узел из графа знаний по его ID",
)
async def delete_node(
    node_id: str,
    service: RAGService = Depends(_get_rag_service),
    _=Depends(get_current_user),
):
    """Удаляет узел из графа знаний."""
    try:
        result = service.delete_node(node_id)
        return RAGDeleteResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting node: {str(e)}",
        )


@router.get(
    "/stats",
    response_model=RAGGraphStatsResponse,
    summary="Статистика графа знаний",
    description="Возвращает статистику графа знаний: количество узлов, связей и т.д.",
)
async def get_rag_stats(
    service: RAGService = Depends(_get_rag_service),
    _=Depends(get_current_user),
):
    """Возвращает статистику графа знаний."""
    try:
        stats = service.get_stats()
        return RAGGraphStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting stats: {str(e)}",
        )
