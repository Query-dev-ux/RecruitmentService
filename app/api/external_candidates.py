import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_service_token
from app.db.base import get_db
from app.db.models.enums import ReviewStatus, SourceType
from app.repositories import candidates as repo
from app.schemas.external_candidate import CandidateReviewIn, ExternalCandidateOut

router = APIRouter(prefix="/external-candidates", tags=["external-candidates"])


@router.get("", response_model=list[ExternalCandidateOut])
async def list_candidates(
    source: Optional[SourceType] = Query(default=None),
    search_template_id: Optional[uuid.UUID] = Query(default=None),
    min_score: Optional[int] = Query(default=None, ge=0, le=100),
    review_status: Optional[ReviewStatus] = Query(default=None),
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
        review_status=review_status,
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


@router.patch("/{candidate_id}/review", response_model=ExternalCandidateOut)
async def review_candidate(
    candidate_id: uuid.UUID,
    payload: CandidateReviewIn,
    _: None = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
):
    """The «Добавить в кандидаты» / «Пропустить» gate — see docs/API_INTEGRATION.md.
    Applies uniformly regardless of how the candidate was found (HH search,
    Telegram, or future HH negotiations)."""
    candidate = await repo.get_candidate(db, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return await repo.set_review_status(db, candidate, decision=payload.decision, reviewed_by=payload.reviewed_by)
