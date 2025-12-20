# app/modules/prompts/schemas.py
"""
Pydantic схемы для работы с промптами через API.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.prompts.models import PromptStatus, PromptType


class PromptCreate(BaseModel):
    """Схема для создания нового промпта."""

    name: str = Field(..., description="Название промпта", max_length=255)
    type: PromptType = Field(..., description="Тип промпта")
    content: str = Field(..., description="Содержимое промпта")
    status: PromptStatus = Field(
        default=PromptStatus.DRAFT,
        description="Статус промпта",
    )
    version: str = Field(default="v1.0", description="Версия промпта")
    description: Optional[str] = Field(None, description="Описание промпта")
    metadata_: Optional[str] = Field(
        None,
        description="JSON метаданные (language, author, tags)",
        alias="metadata",
    )
    is_default: bool = Field(
        default=False,
        description="Является ли промпт дефолтным для своего типа",
    )


class PromptUpdate(BaseModel):
    """Схема для обновления промпта."""

    name: Optional[str] = Field(None, max_length=255)
    type: Optional[PromptType] = None
    content: Optional[str] = None
    status: Optional[PromptStatus] = None
    version: Optional[str] = None
    description: Optional[str] = None
    metadata_: Optional[str] = Field(None, alias="metadata")
    is_default: Optional[bool] = None


class PromptBase(BaseModel):
    """Базовая схема промпта для ответов API."""

    id: UUID
    name: str
    type: PromptType
    content: str
    status: PromptStatus
    version: str
    description: Optional[str]
    metadata_: Optional[str] = Field(None, alias="metadata")
    is_default: bool
    created_by_id: Optional[UUID]
    updated_by_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        allow_population_by_field_name = True


class PromptListItem(BaseModel):
    """Упрощённая схема промпта для списков."""

    id: UUID
    name: str
    type: PromptType
    status: PromptStatus
    version: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class PromptListResponse(BaseModel):
    """Ответ со списком промптов."""

    items: list[PromptListItem]
    total: int


class PromptContentResponse(BaseModel):
    """Ответ с содержимым промпта (для использования в RAG)."""

    type: PromptType
    content: str
    version: str
    metadata_: Optional[str] = Field(None, alias="metadata")

    class Config:
        orm_mode = True
        allow_population_by_field_name = True
