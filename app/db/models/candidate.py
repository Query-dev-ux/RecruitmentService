import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import ScoreTier, SourceType


class ExternalCandidate(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "external_candidates"

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    parsed_profile: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # CRM reads candidates from us via GET /external-candidates rather than
    # us pushing to it, so we have no way to learn CRM's own candidate id
    # today — this column is reserved for a future write-back/ack endpoint
    # and stays null until one exists.
    crm_candidate_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    sources: Mapped[list["CandidateSource"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")
    scores: Mapped[list["CandidateScore"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")


class CandidateSource(UUIDPKMixin, Base):
    __tablename__ = "candidate_sources"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_candidate_sources_source_external_id"),)

    external_candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("external_candidates.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[SourceType] = mapped_column(
        SAEnum(SourceType, name="source_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    candidate: Mapped["ExternalCandidate"] = relationship(back_populates="sources")


class CandidateScore(UUIDPKMixin, Base):
    __tablename__ = "candidate_scores"
    __table_args__ = (
        UniqueConstraint("external_candidate_id", "search_template_id", name="uq_candidate_scores_candidate_template"),
    )

    external_candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("external_candidates.id", ondelete="CASCADE"), nullable=False
    )
    search_template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("search_templates.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    tier: Mapped[ScoreTier] = mapped_column(
        SAEnum(ScoreTier, name="score_tier", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    breakdown: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    hard_filters_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    candidate: Mapped["ExternalCandidate"] = relationship(back_populates="scores")
