# app/modules/prompts/schemas.py
"""
Pydantic схемы для работы с промптами через API.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.prompts.models import PromptCategory, PromptStatus


class PromptCreate(BaseModel):
    """Схема для создания нового промпта."""

    name: str = Field(..., description="Название промпта", max_length=255)
    display_name: str = Field(..., description="Отображаемое имя", max_length=255)
    category: PromptCategory = Field(..., description="Категория промпта")
    content: str = Field(..., description="Содержимое промпта")
    status: PromptStatus = Field(
        default=PromptStatus.DRAFT,
        description="Статус промпта",
    )
    language: str = Field(default="EN", description="Язык промпта")
    priority: int = Field(default=0, description="Приоритет")
    version: str = Field(default="1.0", description="Версия промпта")
    description: Optional[str] = Field(None, description="Описание промпта")
    variables: Optional[dict[str, Any]] = Field(
        default=None,
        description="JSON переменные шаблона",
    )


class PromptUpdate(BaseModel):
    """Схема для обновления промпта."""

    name: Optional[str] = Field(None, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    category: Optional[PromptCategory] = None
    content: Optional[str] = None
    status: Optional[PromptStatus] = None
    version: Optional[str] = None
    description: Optional[str] = None
    variables: Optional[dict[str, Any]] = None
    language: Optional[str] = None
    priority: Optional[int] = None
    change_summary: Optional[str] = None


class PromptBase(BaseModel):
    """Базовая схема промпта для ответов API."""

    id: UUID
    name: str
    display_name: str
    category: PromptCategory
    content: str
    status: PromptStatus
    version: str
    description: Optional[str]
    variables: Optional[str]
    author_id: UUID
    language: str
    priority: int
    usage_count: int
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PromptListItem(BaseModel):
    """Упрощённая схема промпта для списков."""

    id: UUID
    name: str
    display_name: str
    category: PromptCategory
    status: PromptStatus
    version: str
    language: str
    priority: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptListResponse(BaseModel):
    """Ответ со списком промптов."""

    items: list[PromptListItem]
    total: int


class PromptContentResponse(BaseModel):
    """Ответ с содержимым промпта (для использования в RAG)."""

    category: PromptCategory
    content: str
    version: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PromptVersionBase(BaseModel):
    """Схема версии промпта."""

    id: UUID
    prompt_id: UUID
    version: str
    content: str
    change_summary: Optional[str]
    created_by_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)