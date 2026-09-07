import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import DiscoveryChannel, ReviewStatus, ScoreTier, SourceType


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

    # Which vacancy this candidate applied to — set from TelegramApplication.
    # vacancy_ref (see services/telegram_intake.py); stays null for HH-only
    # candidates, whose vacancy association lives on CandidateScore.search_
    # template_id / SearchTemplate.hh_vacancy_id instead. Was previously
    # captured only in telegram_applications and never surfaced via this
    # API — CRM had no way to see which vacancy a Telegram reply was for.
    # On re-application, the latest vacancy_ref wins, same "latest wins"
    # pattern as raw_data/parsed_profile.
    vacancy_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # HR's triage decision on this raw finding — NOT the hiring pipeline
    # itself (that's entirely CRM's, once ADDED). Every new finding (search
    # result or, later, inbound response) starts PENDING regardless of
    # source — the same gate applies everywhere.
    review_status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus, name="review_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ReviewStatus.PENDING,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

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
    # How this HH sighting was found — search vs. inbound negotiation.
    # Always null for Telegram (only one channel there) and for any HH row
    # sourced before this field existed.
    via: Mapped[Optional[DiscoveryChannel]] = mapped_column(
        SAEnum(DiscoveryChannel, name="discovery_channel", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
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
