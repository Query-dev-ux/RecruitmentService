import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_service_token
from app.db.base import get_db
from app.db.models.enums import SearchRunTrigger
from app.repositories import search_runs as search_runs_repo
from app.repositories import search_templates as repo
from app.schemas.search_run import SearchRunCreated
from app.schemas.search_template import SearchTemplateCreate, SearchTemplateOut, SearchTemplateUpdate

router = APIRouter(prefix="/search-templates", tags=["search-templates"])


async def _get_or_404(db: AsyncSession, template_id: uuid.UUID):
    template = await repo.get_search_template(db, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search template not found")
    return template


@router.get("", response_model=list[SearchTemplateOut])
async def list_templates(
    _: None = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
):
    return await repo.list_search_templates(db)


@router.post("", response_model=SearchTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: SearchTemplateCreate,
    _: None = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
):
    return await repo.create_search_template(db, payload)


@router.get("/{template_id}", response_model=SearchTemplateOut)
async def get_template(
    template_id: uuid.UUID,
    _: None = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
):
    return await _get_or_404(db, template_id)


@router.put("/{template_id}", response_model=SearchTemplateOut)
async def update_template(
    template_id: uuid.UUID,
    payload: SearchTemplateUpdate,
    _: None = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
):
    template = await _get_or_404(db, template_id)
    return await repo.update_search_template(db, template, payload)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID,
    _: None = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
):
    template = await _get_or_404(db, template_id)
    await repo.delete_search_template(db, template)


@router.post("/{template_id}/run", response_model=SearchRunCreated, status_code=status.HTTP_202_ACCEPTED)
async def run_template(
    template_id: uuid.UUID,
    _: None = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
):
    """Enqueues a search_run — the worker picks it up asynchronously (see
    app/worker.py). Never runs the search synchronously in the request."""
    template = await _get_or_404(db, template_id)
    run = await search_runs_repo.create_search_run(
        db, search_template_id=template.id, trigger=SearchRunTrigger.MANUAL
    )
    return SearchRunCreated(search_run_id=run.id, status=run.status)
