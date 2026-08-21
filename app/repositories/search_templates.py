import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import SearchTemplate, SearchTemplateCriterion
from app.schemas.search_template import SearchTemplateCreate, SearchTemplateUpdate

_WITH_CRITERIA = selectinload(SearchTemplate.criteria)


async def list_search_templates(db: AsyncSession) -> list[SearchTemplate]:
    result = await db.execute(select(SearchTemplate).options(_WITH_CRITERIA).order_by(SearchTemplate.created_at.desc()))
    return list(result.scalars().all())


async def get_search_template(db: AsyncSession, template_id: uuid.UUID) -> Optional[SearchTemplate]:
    result = await db.execute(select(SearchTemplate).options(_WITH_CRITERIA).where(SearchTemplate.id == template_id))
    return result.scalar_one_or_none()


async def create_search_template(db: AsyncSession, data: SearchTemplateCreate) -> SearchTemplate:
    template = SearchTemplate(
        name=data.name,
        crm_vacancy_id=data.crm_vacancy_id,
        is_active=data.is_active,
        auto_search_enabled=data.auto_search_enabled,
        interval_minutes=data.interval_minutes,
        score_thresholds=data.score_thresholds,
        created_by=data.created_by,
        criteria=[
            SearchTemplateCriterion(key=c.key, value=c.value, mode=c.mode, weight=c.weight) for c in data.criteria
        ],
    )
    db.add(template)
    await db.commit()
    # A fresh SELECT (not a partial db.refresh) — refreshing only
    # attribute_names=["criteria"] leaves server-computed columns like
    # updated_at expired, which then blows up with MissingGreenlet when
    # FastAPI serializes the response outside the session's async context.
    return await get_search_template(db, template.id)  # type: ignore[return-value]


async def update_search_template(db: AsyncSession, template: SearchTemplate, data: SearchTemplateUpdate) -> SearchTemplate:
    updatable_fields = (
        "name",
        "crm_vacancy_id",
        "is_active",
        "auto_search_enabled",
        "interval_minutes",
        "score_thresholds",
    )
    for field in updatable_fields:
        value = getattr(data, field)
        if value is not None:
            setattr(template, field, value)

    if data.criteria is not None:
        template.criteria.clear()
        for criterion in data.criteria:
            template.criteria.append(
                SearchTemplateCriterion(key=criterion.key, value=criterion.value, mode=criterion.mode, weight=criterion.weight)
            )

    await db.commit()
    return await get_search_template(db, template.id)  # type: ignore[return-value]


async def delete_search_template(db: AsyncSession, template: SearchTemplate) -> None:
    await db.delete(template)
    await db.commit()
