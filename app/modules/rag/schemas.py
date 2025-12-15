"""Pydantic schemas for RAG endpoints."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class RAGQueryRequest(BaseModel):
    """Запрос к RAG системе."""
    question: str = Field(..., description="Вопрос пользователя")
    mode: str = Field(
        default="hybrid",
        description="Режим запроса: naive, local, global, hybrid"
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Количество результатов")
    context_limit: Optional[int] = Field(None, description="Лимит контекста")


class RAGQueryResponse(BaseModel):
    """Ответ от RAG системы."""
    answer: str = Field(..., description="Ответ на вопрос")
    context: List[Dict[str, Any]] = Field(default_factory=list, description="Контекстные узлы")
    nodes: List[Dict[str, Any]] = Field(default_factory=list, description="Узлы графа")
    edges: List[Dict[str, Any]] = Field(default_factory=list, description="Связи графа")
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

