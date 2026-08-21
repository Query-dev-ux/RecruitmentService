from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.models.enums import SearchRunStatus, SearchRunTrigger


class SearchRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    search_template_id: UUID
    trigger: SearchRunTrigger
    status: SearchRunStatus
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    stats: Optional[dict]
    error_message: Optional[str]
    created_at: datetime


class SearchRunCreated(BaseModel):
    search_run_id: UUID
    status: SearchRunStatus
