import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin
from app.db.models.enums import TelegramSyncStatus


class TelegramApplication(UUIDPKMixin, Base):
    """Staging row for an inbound Telegram application.

    Written by POST /telegram/applications. Nothing calls that endpoint yet
    (CGBot integration is a later phase) — this table exists so the endpoint
    and its persistence are already testable.
    """

    __tablename__ = "telegram_applications"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vacancy_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    candidate_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resume_file_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    external_candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("external_candidates.id", ondelete="SET NULL"), nullable=True
    )
    sync_status: Mapped[TelegramSyncStatus] = mapped_column(
        SAEnum(TelegramSyncStatus, name="telegram_sync_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=TelegramSyncStatus.PENDING,
    )
