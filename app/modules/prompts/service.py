# app/modules/prompts/service.py
"""
Сервис для работы с промптами.
Поддерживает хранение в БД с fallback на файлы из app/core/prompts.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.modules.prompts.models import Prompt, PromptStatus, PromptType
from app.modules.prompts.schemas import PromptCreate, PromptUpdate

logger = get_logger(__name__)

# Путь к файловым промптам (fallback)
PROMPTS_DIR = Path(__file__).parent.parent.parent / "core" / "prompts"


class PromptService:
    """
    Сервис для управления промптами.

    Поддерживает:
    - CRUD операции с промптами в БД
    - Fallback на файловые промпты
    - Кеширование активных промптов
    - Загрузку дефолтных промптов из файлов в БД
    """

    def __init__(self, db: Session):
        self.db = db
        self._cache: Dict[PromptType, str] = {}

    def create_prompt(
        self,
        prompt_data: PromptCreate,
        created_by_id: UUID | None = None,
    ) -> Prompt:
        """Создать новый промпт."""
        prompt = Prompt(
            name=prompt_data.name,
            type=prompt_data.type,
            content=prompt_data.content,
            status=prompt_data.status,
            version=prompt_data.version,
            description=prompt_data.description,
            metadata_=prompt_data.metadata_,
            is_default=prompt_data.is_default,
            created_by_id=created_by_id,
            updated_by_id=created_by_id,
        )

        # Если промпт помечен как default, убираем флаг у других промптов этого типа
        if prompt.is_default:
            self._unset_default_for_type(prompt.type)

        self.db.add(prompt)
        self.db.commit()
        self.db.refresh(prompt)

        # Сбрасываем кеш для этого типа
        self._cache.pop(prompt.type, None)

        logger.info(
            "Prompt created",
            extra={
                "prompt_id": str(prompt.id),
                "type": prompt.type.value,
                "name": prompt.name,
            },
        )

        return prompt

    def update_prompt(
        self,
        prompt_id: UUID,
        prompt_data: PromptUpdate,
        updated_by_id: UUID | None = None,
    ) -> Prompt | None:
        """Обновить существующий промпт."""
        prompt = self.db.query(Prompt).get(prompt_id)
        if not prompt:
            return None

        update_data = prompt_data.dict(exclude_unset=True)

        # Если меняем is_default на True, убираем флаг у других
        if update_data.get("is_default") is True:
            self._unset_default_for_type(prompt.type)

        for key, value in update_data.items():
            if key == "metadata_":
                setattr(prompt, "metadata_", value)
            else:
                setattr(prompt, key, value)

        if updated_by_id:
            prompt.updated_by_id = updated_by_id

        self.db.commit()
        self.db.refresh(prompt)

        # Сбрасываем кеш
        self._cache.pop(prompt.type, None)

        logger.info(
            "Prompt updated",
            extra={"prompt_id": str(prompt.id), "type": prompt.type.value},
        )

        return prompt

    def get_prompt(self, prompt_id: UUID) -> Prompt | None:
        """Получить промпт по ID."""
        return self.db.query(Prompt).get(prompt_id)

    def list_prompts(
        self,
        prompt_type: PromptType | None = None,
        status: PromptStatus | None = None,
        is_default: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Prompt]:
        """Получить список промптов с фильтрацией."""
        query = self.db.query(Prompt)

        if prompt_type:
            query = query.filter(Prompt.type == prompt_type)

        if status:
            query = query.filter(Prompt.status == status)

        if is_default is not None:
            query = query.filter(Prompt.is_default == is_default)

        query = query.order_by(Prompt.created_at.desc())
        query = query.limit(limit).offset(offset)

        return query.all()

    def delete_prompt(self, prompt_id: UUID) -> bool:
        """Удалить промпт (мягкое удаление - перевод в ARCHIVED)."""
        prompt = self.db.query(Prompt).get(prompt_id)
        if not prompt:
            return False

        prompt.status = PromptStatus.ARCHIVED
        self.db.commit()

        # Сбрасываем кеш
        self._cache.pop(prompt.type, None)

        logger.info(
            "Prompt archived",
            extra={"prompt_id": str(prompt_id), "type": prompt.type.value},
        )

        return True

    def get_active_prompt_content(self, prompt_type: PromptType) -> str:
        """
        Получить содержимое активного промпта для заданного типа.

        Логика:
        1. Проверяем кеш
        2. Ищем дефолтный активный промпт в БД
        3. Fallback на файл из app/core/prompts
        4. Возвращаем пустую строку, если ничего не найдено
        """
        # Проверяем кеш
        if prompt_type in self._cache:
            return self._cache[prompt_type]

        # Ищем в БД
        prompt = (
            self.db.query(Prompt)
            .filter(
                Prompt.type == prompt_type,
                Prompt.status == PromptStatus.ACTIVE,
                Prompt.is_default == True,
            )
            .first()
        )

        if prompt:
            content = prompt.content
            self._cache[prompt_type] = content
            logger.info(
                "Prompt loaded from database",
                extra={"type": prompt_type.value, "prompt_id": str(prompt.id)},
            )
            return content

        # Fallback на файлы
        content = self._load_from_file(prompt_type)
        if content:
            self._cache[prompt_type] = content
            logger.info(
                "Prompt loaded from file",
                extra={"type": prompt_type.value},
            )
            return content

        logger.warning(
            "No prompt found for type",
            extra={"type": prompt_type.value},
        )
        return ""

    def _load_from_file(self, prompt_type: PromptType) -> str:
        """
        Загрузить промпт из файла (fallback).

        Маппинг типов на файлы:
        - STYLE_GUIDE -> 02_StyleGuide_v1.txt.txt
        - ROUTING -> 03_ISA_RoutingPrompts_v1.txt.txt
        - COMPANY_PROFILE -> Company Profile — TRI-S-Audit.txt
        и т.д.
        """
        file_mapping = {
            PromptType.STYLE_GUIDE: "02_StyleGuide_v1.txt.txt",
            PromptType.ROUTING: "03_ISA_RoutingPrompts_v1.txt.txt",
            PromptType.COMPANY_PROFILE: "Company Profile — TRI-S-Audit.txt",
            PromptType.RISK_LIBRARY: "04_Risk_Library_by_Cycle_v1.txt",
            PromptType.MATERIALITY: "05_Materiality_Playbook_v1.1.txt",
            PromptType.SAMPLING: "06_Sampling_Methods_ISA530_v1.txt",
            PromptType.LEGAL_MATRIX: "07_Legal_Matrix_ISA560_501_v1.txt",
            PromptType.KAM_SKELETON: "12_KAM_Skeletons_ISA701_v1.txt.txt",
        }

        filename = file_mapping.get(prompt_type)
        if not filename:
            return ""

        file_path = PROMPTS_DIR / filename

        try:
            if file_path.exists():
                return file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(
                "Failed to load prompt from file",
                extra={
                    "type": prompt_type.value,
                    "file": str(file_path),
                    "error": str(e),
                },
            )

        return ""

    def _unset_default_for_type(self, prompt_type: PromptType) -> None:
        """Убрать флаг is_default у всех промптов данного типа."""
        self.db.query(Prompt).filter(
            Prompt.type == prompt_type,
            Prompt.is_default == True,
        ).update({"is_default": False})

    def seed_from_files(self) -> int:
        """
        Загрузить дефолтные промпты из файлов в БД (если их там ещё нет).

        Используется при первом запуске или для восстановления.
        Возвращает количество созданных промптов.
        """
        created_count = 0

        file_mapping = {
            PromptType.STYLE_GUIDE: (
                "02_StyleGuide_v1.txt.txt",
                "Style Guide (TRI-S-AUDIT B4-Level)",
            ),
            PromptType.ROUTING: (
                "03_ISA_RoutingPrompts_v1.txt.txt",
                "ISA Routing Prompts",
            ),
            PromptType.COMPANY_PROFILE: (
                "Company Profile — TRI-S-Audit.txt",
                "Company Profile — TRI-S-Audit",
            ),
            PromptType.RISK_LIBRARY: (
                "04_Risk_Library_by_Cycle_v1.txt",
                "Risk Library by Cycle",
            ),
            PromptType.MATERIALITY: (
                "05_Materiality_Playbook_v1.1.txt",
                "Materiality Playbook v1.1",
            ),
            PromptType.SAMPLING: (
                "06_Sampling_Methods_ISA530_v1.txt",
                "Sampling Methods (ISA 530)",
            ),
            PromptType.LEGAL_MATRIX: (
                "07_Legal_Matrix_ISA560_501_v1.txt",
                "Legal Matrix (ISA 560/501)",
            ),
            PromptType.KAM_SKELETON: (
                "12_KAM_Skeletons_ISA701_v1.txt.txt",
                "KAM Skeletons (ISA 701)",
            ),
        }

        for prompt_type, (filename, name) in file_mapping.items():
            # Проверяем, есть ли уже активный дефолтный промпт этого типа
            existing = (
                self.db.query(Prompt)
                .filter(
                    Prompt.type == prompt_type,
                    Prompt.is_default == True,
                )
                .first()
            )

            if existing:
                logger.info(
                    "Prompt already exists, skipping",
                    extra={"type": prompt_type.value},
                )
                continue

            # Загружаем из файла
            file_path = PROMPTS_DIR / filename
            if not file_path.exists():
                logger.warning(
                    "Prompt file not found",
                    extra={"type": prompt_type.value, "file": str(file_path)},
                )
                continue

            try:
                content = file_path.read_text(encoding="utf-8")

                prompt = Prompt(
                    name=name,
                    type=prompt_type,
                    content=content,
                    status=PromptStatus.ACTIVE,
                    version="v1.0",
                    description=f"Загружен из файла {filename}",
                    is_default=True,
                )

                self.db.add(prompt)
                created_count += 1

                logger.info(
                    "Prompt seeded from file",
                    extra={"type": prompt_type.value, "name": name},
                )

            except Exception as e:
                logger.error(
                    "Failed to seed prompt from file",
                    extra={
                        "type": prompt_type.value,
                        "file": str(file_path),
                        "error": str(e),
                    },
                )

        if created_count > 0:
            self.db.commit()
            logger.info(f"Seeded {created_count} prompts from files")

        return created_count

    def clear_cache(self) -> None:
        """Очистить кеш промптов."""
        self._cache.clear()
        logger.info("Prompt cache cleared")
