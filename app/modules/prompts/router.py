# app/modules/prompts/router.py
"""
API роуты для управления промптами.
Позволяют создавать, редактировать, удалять и получать промпты из БД.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.logging import get_logger
from app.modules.auth.models import User
from app.modules.auth.router import get_current_admin
from app.modules.prompts.models import PromptStatus, PromptType
from app.modules.prompts.schemas import (
    PromptBase,
    PromptContentResponse,
    PromptCreate,
    PromptListResponse,
    PromptUpdate,
)
from app.modules.prompts.service import PromptService

logger = get_logger(__name__)

router = APIRouter(prefix="/prompts", tags=["prompts"])


def _get_prompt_service(db: Session = Depends(get_db)) -> PromptService:
    """Dependency для получения PromptService."""
    return PromptService(db)


@router.post(
    "",
    response_model=PromptBase,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый промпт",
)
def create_prompt(
    prompt_data: PromptCreate,
    user: User = Depends(get_current_admin),
    service: PromptService = Depends(_get_prompt_service),
):
    """
    Создать новый промпт.

    Требуется роль администратора.
    """
    prompt = service.create_prompt(prompt_data, created_by_id=user.id)
    return prompt


@router.get(
    "",
    response_model=PromptListResponse,
    summary="Список промптов",
)
def list_prompts(
    prompt_type: PromptType | None = Query(None, description="Фильтр по типу"),
    status_filter: PromptStatus | None = Query(
        None,
        description="Фильтр по статусу",
        alias="status",
    ),
    is_default: bool | None = Query(None, description="Только дефолтные промпты"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_admin),
    service: PromptService = Depends(_get_prompt_service),
):
    """
    Получить список промптов с фильтрацией.

    Требуется роль администратора.
    """
    prompts = service.list_prompts(
        prompt_type=prompt_type,
        status=status_filter,
        is_default=is_default,
        limit=limit,
        offset=offset,
    )

    total = len(prompts)  # Для более точного total можно добавить count query

    return {"items": prompts, "total": total}


@router.get(
    "/{prompt_id}",
    response_model=PromptBase,
    summary="Получить промпт по ID",
)
def get_prompt(
    prompt_id: UUID,
    user: User = Depends(get_current_admin),
    service: PromptService = Depends(_get_prompt_service),
):
    """
    Получить полную информацию о промпте.

    Требуется роль администратора.
    """
    prompt = service.get_prompt(prompt_id)

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        )

    return prompt


@router.patch(
    "/{prompt_id}",
    response_model=PromptBase,
    summary="Обновить промпт",
)
def update_prompt(
    prompt_id: UUID,
    prompt_data: PromptUpdate,
    user: User = Depends(get_current_admin),
    service: PromptService = Depends(_get_prompt_service),
):
    """
    Обновить существующий промпт.

    Требуется роль администратора.
    """
    prompt = service.update_prompt(prompt_id, prompt_data, updated_by_id=user.id)

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        )

    return prompt


@router.delete(
    "/{prompt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить промпт",
)
def delete_prompt(
    prompt_id: UUID,
    user: User = Depends(get_current_admin),
    service: PromptService = Depends(_get_prompt_service),
):
    """
    Удалить промпт (переводит в статус ARCHIVED).

    Требуется роль администратора.
    """
    success = service.delete_prompt(prompt_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        )


@router.get(
    "/active/{prompt_type}",
    response_model=PromptContentResponse,
    summary="Получить активный промпт по типу",
)
def get_active_prompt(
    prompt_type: PromptType,
    user: User = Depends(get_current_admin),
    service: PromptService = Depends(_get_prompt_service),
):
    """
    Получить содержимое активного промпта для заданного типа.

    Используется RAG-сервисом для получения системных промптов.
    Требуется роль администратора.
    """
    content = service.get_active_prompt_content(prompt_type)

    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active prompt found for type {prompt_type.value}",
        )

    return {
        "type": prompt_type,
        "content": content,
        "version": "active",
        "metadata": None,
    }


@router.post(
    "/seed",
    summary="Загрузить промпты из файлов",
)
def seed_prompts_from_files(
    user: User = Depends(get_current_admin),
    service: PromptService = Depends(_get_prompt_service),
):
    """
    Загрузить дефолтные промпты из файлов app/core/prompts в БД.

    Используется при первом запуске или для восстановления промптов.
    Требуется роль администратора.
    """
    created_count = service.seed_from_files()

    return {
        "message": f"Seeded {created_count} prompts from files",
        "created_count": created_count,
    }


@router.post(
    "/cache/clear",
    summary="Очистить кеш промптов",
)
def clear_prompt_cache(
    user: User = Depends(get_current_admin),
    service: PromptService = Depends(_get_prompt_service),
):
    """
    Очистить кеш промптов в сервисе.

    Полезно после обновления промптов в БД.
    Требуется роль администратора.
    """
    service.clear_cache()

    return {"message": "Prompt cache cleared"}
