import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import CriterionMode


class SearchTemplate(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "search_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Opaque reference to a vacancy in the CRM's own database. Recruitment
    # Service does not own or validate vacancies — CRM and Recruitment each
    # keep their own Postgres, and this is just the join key CRM uses when
    # it pulls scored candidates for a given vacancy via the API.
    crm_vacancy_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    auto_search_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interval_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    score_thresholds: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    criteria: Mapped[list["SearchTemplateCriterion"]] = relationship(
        back_populates="search_template", cascade="all, delete-orphan"
    )


class SearchTemplateCriterion(UUIDPKMixin, Base):
    __tablename__ = "search_template_criteria"

    search_template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("search_templates.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    mode: Mapped[CriterionMode] = mapped_column(
        SAEnum(CriterionMode, name="criterion_mode", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    search_template: Mapped[SearchTemplate] = relationship(back_populates="criteria")
