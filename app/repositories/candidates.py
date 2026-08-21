import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import CandidateScore, CandidateSource, ExternalCandidate
from app.db.models.enums import ScoreTier, SourceType

_WITH_SOURCES_AND_SCORES = (
    selectinload(ExternalCandidate.sources),
    selectinload(ExternalCandidate.scores),
)


async def get_or_create_candidate(
    db: AsyncSession,
    *,
    source: SourceType,
    external_id: str,
    external_url: Optional[str],
    raw_data: dict,
    parsed_profile: dict,
) -> tuple[ExternalCandidate, bool]:
    """Dedup key: (source, external_id), enforced by candidate_sources'
    unique constraint. A matching source row means we've already seen this
    exact external candidate — refresh its snapshot instead of duplicating
    it. Cross-source (HH<->Telegram) matching by email/phone is NOT done
    here — that logic belongs where a candidate's contact details are
    actually available (post contact-reveal for HH, at intake for
    Telegram), not in this generic dedup path. Fuzzy name/company matching
    is explicitly out of scope per the brief.
    """
    result = await db.execute(
        select(CandidateSource).where(CandidateSource.source == source, CandidateSource.external_id == external_id)
    )
    existing_source = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if existing_source is not None:
        candidate = await db.get(ExternalCandidate, existing_source.external_candidate_id)
        assert candidate is not None  # FK guarantees this
        candidate.raw_data = raw_data
        candidate.parsed_profile = parsed_profile
        candidate.last_seen_at = now
        existing_source.last_seen_at = now
        if external_url:
            existing_source.external_url = external_url
        await db.commit()
        return candidate, False

    candidate = ExternalCandidate(raw_data=raw_data, parsed_profile=parsed_profile, first_seen_at=now, last_seen_at=now)
    db.add(candidate)
    await db.flush()  # populate candidate.id for the FK below, without a full commit yet

    db.add(
        CandidateSource(
            external_candidate_id=candidate.id,
            source=source,
            external_id=external_id,
            external_url=external_url,
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    await db.commit()
    return candidate, True


async def upsert_candidate_score(
    db: AsyncSession,
    *,
    external_candidate_id: uuid.UUID,
    search_template_id: uuid.UUID,
    score: int,
    tier: ScoreTier,
    breakdown: dict,
    hard_filters_passed: bool,
) -> CandidateScore:
    result = await db.execute(
        select(CandidateScore).where(
            CandidateScore.external_candidate_id == external_candidate_id,
            CandidateScore.search_template_id == search_template_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.score = score
        existing.tier = tier
        existing.breakdown = breakdown
        existing.hard_filters_passed = hard_filters_passed
        await db.commit()
        return existing

    candidate_score = CandidateScore(
        external_candidate_id=external_candidate_id,
        search_template_id=search_template_id,
        score=score,
        tier=tier,
        breakdown=breakdown,
        hard_filters_passed=hard_filters_passed,
    )
    db.add(candidate_score)
    await db.commit()
    return candidate_score


async def get_candidate(db: AsyncSession, candidate_id: uuid.UUID) -> Optional[ExternalCandidate]:
    result = await db.execute(
        select(ExternalCandidate).options(*_WITH_SOURCES_AND_SCORES).where(ExternalCandidate.id == candidate_id)
    )
    return result.scalar_one_or_none()


async def list_candidates(
    db: AsyncSession,
    *,
    source: Optional[SourceType] = None,
    search_template_id: Optional[uuid.UUID] = None,
    min_score: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ExternalCandidate]:
    """This is the read side of the CRM integration contract: CRM's own
    backend calls GET /external-candidates (backed by this function) to
    pull scored candidates on its own schedule — Recruitment Service never
    pushes into CRM. See services/search_execution.py and
    services/telegram_intake.py, neither of which calls out to CRM.

    Matching candidate ids are resolved first, over non-JSON columns only —
    this deliberately avoids `SELECT DISTINCT` on rows that include a JSON
    column: Postgres's plain `json` type (unlike `jsonb`) has no equality
    operator, so a naive `.distinct()` on the full joined row would work in
    SQLite (used in tests) but fail on Postgres in production.
    """
    id_query = select(ExternalCandidate.id).distinct()
    if source is not None:
        id_query = id_query.join(
            CandidateSource, CandidateSource.external_candidate_id == ExternalCandidate.id
        ).where(CandidateSource.source == source)
    if search_template_id is not None or min_score is not None:
        id_query = id_query.join(CandidateScore, CandidateScore.external_candidate_id == ExternalCandidate.id)
        if search_template_id is not None:
            id_query = id_query.where(CandidateScore.search_template_id == search_template_id)
        if min_score is not None:
            id_query = id_query.where(CandidateScore.score >= min_score)

    matching_ids = [row[0] for row in (await db.execute(id_query)).all()]
    if not matching_ids:
        return []

    result = await db.execute(
        select(ExternalCandidate)
        .options(*_WITH_SOURCES_AND_SCORES)
        .where(ExternalCandidate.id.in_(matching_ids))
        .order_by(ExternalCandidate.last_seen_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
