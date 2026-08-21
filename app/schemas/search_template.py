from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models.enums import CriterionMode

# Matches the interval options from the brief (§7): 15m/30m/1h/2h/6h/12h/24h.
ALLOWED_INTERVAL_MINUTES = {15, 30, 60, 120, 360, 720, 1440}


class CriterionIn(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=500)
    mode: CriterionMode = CriterionMode.PREFERRED
    weight: int = Field(default=0, ge=0, le=100)


class CriterionOut(CriterionIn):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


def _validate_interval(interval_minutes: Optional[int]) -> Optional[int]:
    if interval_minutes is not None and interval_minutes not in ALLOWED_INTERVAL_MINUTES:
        raise ValueError(f"interval_minutes must be one of {sorted(ALLOWED_INTERVAL_MINUTES)}")
    return interval_minutes


class SearchTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    crm_vacancy_id: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = True
    auto_search_enabled: bool = False
    interval_minutes: Optional[int] = None
    score_thresholds: Optional[dict] = None
    created_by: Optional[str] = Field(default=None, max_length=255)
    criteria: list[CriterionIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_interval(self) -> "SearchTemplateCreate":
        _validate_interval(self.interval_minutes)
        return self


class SearchTemplateUpdate(BaseModel):
    """Partial update. A field left as None is not touched, except `criteria`,
    where None means "leave as is" and an explicit [] clears all criteria."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    crm_vacancy_id: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None
    auto_search_enabled: Optional[bool] = None
    interval_minutes: Optional[int] = None
    score_thresholds: Optional[dict] = None
    criteria: Optional[list[CriterionIn]] = None

    @model_validator(mode="after")
    def _check_interval(self) -> "SearchTemplateUpdate":
        _validate_interval(self.interval_minutes)
        return self


class SearchTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    crm_vacancy_id: Optional[str]
    is_active: bool
    auto_search_enabled: bool
    interval_minutes: Optional[int]
    score_thresholds: Optional[dict]
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    last_success_at: Optional[datetime]
    last_error: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    criteria: list[CriterionOut]
