from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin


class IntegrationLog(UUIDPKMixin, Base):
    """Structured event log (SEARCH_STARTED, HH_REQUEST_FAILED, CANDIDATE_DUPLICATE, ...).

    Written via app.logging_config.log_event; context is redacted there and
    must never contain tokens, passwords, or raw resume PII.
    """

    __tablename__ = "integration_logs"

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
