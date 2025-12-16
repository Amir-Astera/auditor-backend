"""RAG router with LIGHTRAG endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.router import get_current_user
from app.modules.rag.schemas import (
    RAGQueryRequest,
    RAGQueryResponse,
    RAGInsertRequest,
    RAGInsertResponse,
    RAGDeleteRequest,
    RAGDeleteResponse,
    RAGGraphStatsResponse,
)
from app.modules.rag.service import RAGService
from app.modules.rag.gemini import GeminiAPI

router = APIRouter(prefix="/rag", tags=["rag"])


def _get_rag_service() -> RAGService:
    """Создает экземпляр RAGService."""
    gemini_api = GeminiAPI()
    return RAGService(gemini_api=gemini_api)


@router.post(
    "/query",
    response_model=RAGQueryResponse,
    summary="Запрос к RAG системе",
    description="Выполняет запрос к графу знаний LIGHTRAG и возвращает ответ с контекстом",
)
async def query_rag(
    request: RAGQueryRequest,
    service: RAGService = Depends(_get_rag_service),
    _=Depends(get_current_user),
):
    """
    Выполняет запрос к RAG системе.
    
    Поддерживаемые режимы:
    - naive: Простой запрос без использования графа
    - local: Использование локального контекста
    - global: Использование глобального контекста графа
    - hybrid: Комбинация локального и глобального контекста
    """
    try:
        result = service.query(
            question=request.question,
            mode=request.mode,
            top_k=request.top_k,
        )
        return RAGQueryResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error querying RAG: {str(e)}",
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

