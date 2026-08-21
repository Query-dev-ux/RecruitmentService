import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_service_token
from app.db.base import get_db
from app.db.models.enums import SourceType
from app.repositories import candidates as repo
from app.schemas.external_candidate import ExternalCandidateOut

router = APIRouter(prefix="/external-candidates", tags=["external-candidates"])


@router.get("", response_model=list[ExternalCandidateOut])
async def list_candidates(
    source: Optional[SourceType] = Query(default=None),
    search_template_id: Optional[uuid.UUID] = Query(default=None),
    min_score: Optional[int] = Query(default=None, ge=0, le=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: None = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
):
    return await repo.list_candidates(
        db,
        source=source,
        search_template_id=search_template_id,
        min_score=min_score,
        limit=limit,
        offset=offset,
    )


@router.get("/{candidate_id}", response_model=ExternalCandidateOut)
async def get_candidate(
    candidate_id: uuid.UUID,
    _: None = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
):
    candidate = await repo.get_candidate(db, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return candidate
