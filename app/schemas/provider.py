from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import ProviderAccountStatus


class HHStatusOut(BaseModel):
    connected: bool
    account_id: Optional[UUID] = None
    label: Optional[str] = None
    status: Optional[ProviderAccountStatus] = None
    connected_at: Optional[datetime] = None


class HHConnectOut(BaseModel):
    authorize_url: str
