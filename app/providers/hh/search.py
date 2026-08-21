"""Search-template criteria -> HH `/resumes` query params.

Field names and enum values below were verified live against
api.hh.ru/openapi/specification/public and api.hh.ru/dictionaries (not
guessed — see the plan). Two important corrections from that verification:
`employment`/`schedule` are HH-deprecated; the current replacements
`employment_form`/`work_format` use different (uppercase) enum values from a
different dictionary. This module only ever uses the current ones.

HR sets plain criteria (key/value/mode/weight) with no idea which become
real HH filters vs scoring-only — this registry is exactly what decides
that, per the brief. Anything not recognized here (iGaming, Facebook,
Keitaro, PWA, ...) isn't a structured HH resume field at all; it falls back
to full-text search and remains otherwise scoring-only against
ParsedProfile.text_blob.

Mode matters: only REQUIRED criteria become hard HH filters (or a mandatory
AND text term) — HH filters are exclusionary, and applying a merely
PREFERRED criterion as one would wrongly drop candidates who don't match it
from the search results entirely. PREFERRED criteria only ever bias
full-text recall (OR'd in) or, for structured fields, are left out of the
HH query altogether and scored purely after fetch.
"""

from typing import Optional, Protocol

from app.db.models.enums import CriterionMode

EXPERIENCE_LEVELS = {
    "no_experience": "noExperience",
    "1_3_years": "between1And3",
    "3_6_years": "between3And6",
    "6_plus_years": "moreThan6",
}

EMPLOYMENT_TYPES = {
    "full": "FULL",
    "part_time": "PART_TIME",
    "internship": "INTERNSHIP",
    "volunteer": "VOLUNTEER",
}

WORK_FORMATS = {
    "on_site": "ON_SITE",
    "remote": "REMOTE",
    "hybrid": "HYBRID",
    "field_work": "FIELD_WORK",
    "fly_in_fly_out": "FLY_IN_FLY_OUT",
}

JOB_SEARCH_STATUSES = {
    "active_search",
    "looking_for_offers",
    "not_looking_for_job",
    "has_job_offer",
    "accepted_job_offer",
}


class Criterion(Protocol):
    """Structural type — satisfied by both the Pydantic CriterionIn and the
    SQLAlchemy SearchTemplateCriterion, without importing either here."""

    key: str
    value: str
    mode: CriterionMode


def build_search_params(criteria: list[Criterion]) -> dict[str, list[str]]:
    params: dict[str, list[str]] = {}
    required_terms: list[str] = []
    preferred_terms: list[str] = []

    for criterion in criteria:
        if criterion.mode == CriterionMode.IGNORE:
            continue

        if criterion.mode == CriterionMode.REQUIRED:
            mapped = _map_structured_field(criterion.key, criterion.value)
            if mapped is not None:
                field, value = mapped
                params.setdefault(field, []).append(value)
                continue
            required_terms.append(criterion.value)
        else:
            # PREFERRED never becomes a hard filter — see module docstring.
            preferred_terms.append(criterion.value)

    text_query = _build_text_query(required_terms, preferred_terms)
    if text_query:
        params["text"] = [text_query]

    return params


def _map_structured_field(key: str, value: str) -> Optional[tuple[str, str]]:
    if key == "experience_level" and value in EXPERIENCE_LEVELS:
        return "experience", EXPERIENCE_LEVELS[value]
    if key == "employment_type" and value in EMPLOYMENT_TYPES:
        return "employment_form", EMPLOYMENT_TYPES[value]
    if key == "work_format" and value in WORK_FORMATS:
        return "work_format", WORK_FORMATS[value]
    if key == "job_search_status" and value in JOB_SEARCH_STATUSES:
        return "job_search_status", value
    if key == "geo_area_id" and value.isdigit():
        return "area", value
    if key == "professional_role_id" and value.isdigit():
        return "professional_role", value
    if key == "salary_from" and value.isdigit():
        return "salary_from", value
    if key == "salary_to" and value.isdigit():
        return "salary_to", value
    if key == "language" and ":" in value:
        # HR-facing "eng:b2" -> HH's "eng.b2" (code from GET /languages, level from language_level dictionary)
        lang, level = value.split(":", 1)
        return "language", f"{lang}.{level}"
    return None


def _build_text_query(required_terms: list[str], preferred_terms: list[str]) -> str:
    """HH's text field supports boolean search (AND/OR/parentheses) per its
    query-language docs at dev.hh.ru — that grammar itself wasn't
    independently re-verified this session (only field/enum names were).
    Confirm it before relying on this for strict REQUIRED-term exclusion in
    production, and watch search recall once live."""
    parts = []
    if required_terms:
        parts.append(" AND ".join(required_terms))
    if preferred_terms:
        parts.append("(" + " OR ".join(preferred_terms) + ")")
    return " AND ".join(parts)
