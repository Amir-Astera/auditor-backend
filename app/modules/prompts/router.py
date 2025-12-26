from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.models import User
from app.modules.auth.router import get_current_admin
from app.modules.prompts.models import PromptCategory, PromptStatus
from app.modules.prompts.schemas import (
    PromptBase,
    PromptCreate,
    PromptListResponse,
    PromptUpdate,
    PromptVersionBase,
)
from app.modules.prompts.service import PromptsService


router = APIRouter(prefix="/prompts", tags=["prompts"])


def _get_service(db: Session = Depends(get_db)) -> PromptsService:
    return PromptsService(db)


@router.post(
    "",
    response_model=PromptBase,
    status_code=status.HTTP_201_CREATED,
    summary="Create prompt",
)
def create_prompt(
    payload: PromptCreate,
    current_user: User = Depends(get_current_admin),
    service: PromptsService = Depends(_get_service),
):
    try:
        prompt = service.create_prompt(
            name=payload.name,
            display_name=payload.display_name,
            content=payload.content,
            category=payload.category,
            author_id=str(current_user.id),
            description=payload.description,
            variables=payload.variables,
            language=payload.language,
            priority=payload.priority,
        )
        return prompt
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "",
    response_model=PromptListResponse,
    summary="List prompts",
)
def list_prompts(
    category: PromptCategory | None = Query(default=None),
    status_filter: PromptStatus | None = Query(default=None, alias="status"),
    language: str = Query(default="EN"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(get_current_admin),
    service: PromptsService = Depends(_get_service),
):
    prompts = service.list_prompts(
        category=category,
        status=status_filter,
        language=language,
        limit=limit,
        offset=offset,
    )
    return {"items": prompts, "total": len(prompts)}


@router.get(
    "/{prompt_id}",
    response_model=PromptBase,
    summary="Get prompt by id",
)
def get_prompt(
    prompt_id: str,
    _: User = Depends(get_current_admin),
    service: PromptsService = Depends(_get_service),
):
    prompt = service.get_prompt_by_id(prompt_id)
    if not prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")
    return prompt


@router.patch(
    "/{prompt_id}",
    response_model=PromptBase,
    summary="Update prompt",
)
def update_prompt(
    prompt_id: str,
    payload: PromptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
    service: PromptsService = Depends(_get_service),
):
    data = payload.dict(exclude_unset=True)

    try:
        prompt = service.update_prompt(
            prompt_id=prompt_id,
            content=data.get("content"),
            display_name=data.get("display_name"),
            description=data.get("description"),
            variables=data.get("variables"),
            status=data.get("status"),
            priority=data.get("priority"),
            updated_by_id=str(current_user.id),
            change_summary=data.get("change_summary"),
        )

        if data.get("category") is not None:
            prompt.category = data["category"]
            db.commit()
            db.refresh(prompt)
        if data.get("language") is not None:
            prompt.language = data["language"]
            db.commit()
            db.refresh(prompt)

        return prompt
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{prompt_id}/activate",
    response_model=PromptBase,
    summary="Activate prompt",
)
def activate_prompt(
    prompt_id: str,
    current_user: User = Depends(get_current_admin),
    service: PromptsService = Depends(_get_service),
):
    try:
        return service.activate_prompt(prompt_id=prompt_id, activated_by_id=str(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/{prompt_id}/versions",
    response_model=list[PromptVersionBase],
    summary="Get prompt versions",
)
def get_prompt_versions(
    prompt_id: str,
    _: User = Depends(get_current_admin),
    service: PromptsService = Depends(_get_service),
):
    return service.get_prompt_versions(prompt_id)


@router.post(
    "/admin/seed-defaults",
    summary="Seed default prompts from app/prompts/*.txt",
)
def seed_default_prompts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
    service: PromptsService = Depends(_get_service),
):
    service.initialize_default_prompts(admin_user_id=str(current_user.id))
    return {"status": "ok"}
