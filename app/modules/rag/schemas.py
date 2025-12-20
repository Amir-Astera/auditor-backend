"""Pydantic schemas for RAG endpoints."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    """Запрос к RAG системе (гибридный поиск по законам и документам заказчика)."""

    question: str = Field(..., description="Вопрос пользователя")

    # Hybrid retrieval controls
    customer_id: Optional[str] = Field(
        default=None,
        description="Опционально: заказчик (для поиска по документам заказчика)",
    )
    include_admin_laws: bool = Field(
        default=True,
        description="Искать по административным файлам (законы, ISA/IFRS, методички)",
    )
    include_customer_docs: bool = Field(
        default=True,
        description="Искать по документам заказчика (требует customer_id)",
    )

    mode: str = Field(
        default="hybrid",
        description="Режим запроса: naive, local, global, hybrid (LightRAG) / hybrid retrieval (Qdrant+LightRAG)",
    )
    top_k: int = Field(
        default=8, ge=1, le=30, description="Количество результатов (top-k)"
    )
    context_limit: Optional[int] = Field(
        None, description="Лимит контекста (символы/байты, если поддерживается)"
    )
    temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Температура генерации ответа LLM",
    )


class RAGQueryResponse(BaseModel):
    """Ответ от RAG системы."""

    answer: str = Field(..., description="Ответ на вопрос")
    context: List[Dict[str, Any]] = Field(
        default_factory=list, description="Контекстные узлы/фрагменты"
    )
    nodes: List[Dict[str, Any]] = Field(
        default_factory=list, description="Узлы графа (если доступно)"
    )
    edges: List[Dict[str, Any]] = Field(
        default_factory=list, description="Связи графа (если доступно)"
    )
    mode: str = Field(..., description="Использованный режим")


class RAGEvidenceRequest(BaseModel):
    """Запрос только на retrieval (без генерации ответа)."""

    question: str = Field(..., description="Поисковый запрос")
    customer_id: Optional[str] = Field(
        default=None,
        description="Опционально: заказчик (для поиска по документам заказчика)",
    )
    include_admin_laws: bool = Field(
        default=True,
        description="Искать по административным файлам (законы, ISA/IFRS, методички)",
    )
    include_customer_docs: bool = Field(
        default=True,
        description="Искать по документам заказчика (требует customer_id)",
    )
    mode: str = Field(
        default="hybrid",
        description="Режим retrieval: hybrid|qdrant|lightrag (если поддерживается)",
    )
    top_k: int = Field(
        default=8, ge=1, le=50, description="Количество результатов (top-k)"
    )


class RAGEvidenceResponse(BaseModel):
    """Ответ retrieval-only (без LLM генерации)."""

    context: List[Dict[str, Any]] = Field(
        default_factory=list, description="Найденные фрагменты/доказательства"
    )
    nodes: List[Dict[str, Any]] = Field(
        default_factory=list, description="Узлы графа (если доступно)"
    )
    edges: List[Dict[str, Any]] = Field(
        default_factory=list, description="Связи графа (если доступно)"
    )
    mode: str = Field(..., description="Использованный режим")


class RAGInsertRequest(BaseModel):
    """Запрос на вставку текста в граф знаний."""

    text: str = Field(..., min_length=1, description="Текст для вставки")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Метаданные документа")


class RAGInsertResponse(BaseModel):
    """Ответ на вставку текста."""

    node_id: str = Field(..., description="ID созданного узла")
    success: bool = Field(..., description="Успешность операции")


class RAGGraphStatsResponse(BaseModel):
    """Статистика графа знаний."""

    nodes_count: int = Field(..., description="Количество узлов")
    edges_count: int = Field(..., description="Количество связей")
    working_dir: str = Field(..., description="Рабочая директория")


class RAGDeleteRequest(BaseModel):
    """Запрос на удаление узла."""

    node_id: str = Field(..., description="ID узла для удаления")


class RAGDeleteResponse(BaseModel):
    """Ответ на удаление узла."""

    success: bool = Field(..., description="Успешность операции")
    node_id: str = Field(..., description="ID удаленного узла")
