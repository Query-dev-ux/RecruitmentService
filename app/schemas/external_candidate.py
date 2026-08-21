from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.models.enums import ScoreTier, SourceType


class CandidateSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: SourceType
    external_id: str
    external_url: Optional[str]
    first_seen_at: datetime
    last_seen_at: datetime


class CandidateScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    search_template_id: UUID
    score: int
    tier: ScoreTier
    hard_filters_passed: bool
    breakdown: Optional[dict]
    computed_at: datetime


class ExternalCandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_seen_at: datetime
    last_seen_at: datetime
    parsed_profile: Optional[dict]
    crm_candidate_id: Optional[str]
    sources: list[CandidateSourceOut]
    scores: list[CandidateScoreOut]
