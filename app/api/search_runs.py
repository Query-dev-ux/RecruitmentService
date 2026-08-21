import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_service_token
from app.db.base import get_db
from app.repositories import search_runs as repo
from app.schemas.search_run import SearchRunOut

router = APIRouter(prefix="/search-runs", tags=["search-runs"])


@router.get("", response_model=list[SearchRunOut])
async def list_runs(
    search_template_id: Optional[uuid.UUID] = Query(default=None),
    _: None = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
):
    return await repo.list_search_runs(db, search_template_id=search_template_id)


@router.get("/{run_id}", response_model=SearchRunOut)
async def get_run(
    run_id: uuid.UUID,
    _: None = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
):
    run = await repo.get_search_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search run not found")
    return run
