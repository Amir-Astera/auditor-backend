# app/modules/prompts/models.py
"""
Модели для хранения промптов в базе данных.
Промпты используются в RAG-системе для управления поведением LLM.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PromptType(str, Enum):
    """Типы промптов для разных задач."""

    SYSTEM = "SYSTEM"  # Системные промпты (роль ассистента)
    STYLE_GUIDE = "STYLE_GUIDE"  # Гайд по стилю (02_StyleGuide)
    ROUTING = "ROUTING"  # Роутинг запросов (03_ISA_RoutingPrompts)
    COMPANY_PROFILE = "COMPANY_PROFILE"  # Профиль компании
    RISK_LIBRARY = "RISK_LIBRARY"  # Библиотека рисков
    MATERIALITY = "MATERIALITY"  # Материальность
    SAMPLING = "SAMPLING"  # Выборка
    LEGAL_MATRIX = "LEGAL_MATRIX"  # Юридическая матрица
    KAM_SKELETON = "KAM_SKELETON"  # Шаблоны KAM
    FORENSIC = "FORENSIC"  # Форензик
    CUSTOM = "CUSTOM"  # Пользовательские промпты


class PromptStatus(str, Enum):
    """Статусы промптов."""

    DRAFT = "DRAFT"  # Черновик
    ACTIVE = "ACTIVE"  # Активный (используется)
    ARCHIVED = "ARCHIVED"  # Архивный


class Prompt(Base):
    """
    Модель промпта для LLM.

    Поля:
    - id: UUID
    - name: Название промпта (для отображения в UI)
    - type: Тип промпта (из PromptType)
    - content: Содержимое промпта
    - status: Статус (draft/active/archived)
    - version: Версия промпта (например, "v1.0")
    - description: Описание промпта
    - metadata_: JSON с дополнительными данными (language, author, tags, etc.)
    - is_default: Является ли промпт дефолтным для своего типа
    - created_by_id: Кто создал
    - updated_by_id: Кто последний раз обновил
    - created_at, updated_at: Временные метки
    """

    __tablename__ = "prompts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    type: Mapped[PromptType] = mapped_column(
        SQLEnum(PromptType),
        nullable=False,
        index=True,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[PromptStatus] = mapped_column(
        SQLEnum(PromptStatus),
        nullable=False,
        default=PromptStatus.DRAFT,
        index=True,
    )

    version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1.0")

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSON поле для хранения метаданных (language, author, tags, kb_tags, etc.)
    metadata_: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Кто создал/обновил (опционально — для аудита)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Prompt {self.name} ({self.type.value}) v{self.version}>"
