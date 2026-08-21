import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import ProviderAccountStatus, ProviderType


class ProviderAccount(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "provider_accounts"

    provider: Mapped[ProviderType] = mapped_column(
        SAEnum(ProviderType, name="provider_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ProviderType.HH,
    )
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[ProviderAccountStatus] = mapped_column(
        SAEnum(ProviderAccountStatus, name="provider_account_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ProviderAccountStatus.DISCONNECTED,
    )
    connected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class ProviderToken(UUIDPKMixin, TimestampMixin, Base):
    """Kept in a separate table from ProviderAccount so listing/joining
    accounts never accidentally pulls token material along with it.

    access_token/refresh_token are stored as plain text in Phase 1 scaffolding;
    encrypting them at rest (Fernet) is part of the HH OAuth phase, not built yet.
    """

    __tablename__ = "provider_tokens"

    provider_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("provider_accounts.id", ondelete="CASCADE"), nullable=False
    )
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
