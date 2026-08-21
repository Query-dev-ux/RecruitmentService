import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, JSON, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import SearchRunStatus, SearchRunTrigger


class SearchRun(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "search_runs"

    search_template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("search_templates.id", ondelete="CASCADE"), nullable=False
    )
    trigger: Mapped[SearchRunTrigger] = mapped_column(
        SAEnum(SearchRunTrigger, name="search_run_trigger", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    status: Mapped[SearchRunStatus] = mapped_column(
        SAEnum(SearchRunStatus, name="search_run_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=SearchRunStatus.QUEUED,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stats: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
