"""Raw HH `/resumes/{id}` JSON -> ParsedProfile.

Field shape is HH's documented resume object (title, total_experience.months,
area.name, salary.amount/currency, employment.id, schedule.id,
job_search_status.id, language[], skill_set[], experience[]). Every access
below is defensive (.get with fallbacks) since search-result-level resumes
carry less detail than a fully opened one, and both flow through this same
function.

employment.id/schedule.id here come from HH's resume-object dictionaries
(deprecated `employment`/`schedule`, e.g. "part"/"fullDay") — a DIFFERENT
vocabulary from the current search-filter dictionaries used in
providers/hh/search.py ("employment_form"/"work_format", e.g. "PART_TIME"/
"ON_SITE"). The two don't correspond 1:1 (HH has no search-filter
equivalent for resume-body "project"/"probation" or "shift"/"flexible"), so
they're translated here into one canonical vocabulary — the same one
search.py's HR-facing criteria already use — so the scoring engine can
compare HH and (later) Telegram candidates against the same values. Raw
values with no confident canonical equivalent normalize to None rather than
guessing.
"""

from datetime import date, datetime
from typing import Any, Optional

from app.providers.base import ParsedProfile

# HH resume-body `employment.id` -> our canonical vocabulary (matches
# providers/hh/search.py's EMPLOYMENT_TYPES keys).
EMPLOYMENT_ID_TO_CANONICAL = {
    "full": "full",
    "part": "part_time",
    "volunteer": "volunteer",
    # "project", "probation" have no confident canonical equivalent — left unmapped.
}

# HH resume-body `schedule.id` -> our canonical vocabulary (matches
# providers/hh/search.py's WORK_FORMATS keys).
SCHEDULE_ID_TO_CANONICAL = {
    "fullDay": "on_site",
    "remote": "remote",
    "flyInFlyOut": "fly_in_fly_out",
    # "shift", "flexible" have no confident canonical equivalent — left unmapped.
}


def normalize_resume(raw: dict[str, Any]) -> ParsedProfile:
    total_experience = raw.get("total_experience") or {}
    area = raw.get("area") or {}
    salary = raw.get("salary") or {}
    employment = raw.get("employment") or {}
    schedule = raw.get("schedule") or {}
    job_search_status = raw.get("job_search_status") or {}
    experience_entries = raw.get("experience") or []
    skills = [s for s in (raw.get("skill_set") or []) if s]
    languages = _normalize_languages(raw.get("language") or [])

    return ParsedProfile(
        full_name=_full_name(raw),
        position_title=raw.get("title"),
        total_experience_months=total_experience.get("months"),
        geo=area.get("name"),
        employment_type=EMPLOYMENT_ID_TO_CANONICAL.get(employment.get("id")),
        work_format=SCHEDULE_ID_TO_CANONICAL.get(schedule.get("id")),
        salary_expectation=salary.get("amount"),
        salary_currency=salary.get("currency"),
        job_search_status=job_search_status.get("id"),
        languages=languages,
        skills=skills,
        last_experience_ended_months_ago=_months_since_last_experience_end(experience_entries),
        text_blob=_build_text_blob(raw, skills, experience_entries),
    )


def _normalize_languages(raw_languages: list[dict]) -> list[str]:
    # "code" or "code:level" (e.g. "eng" or "eng:b2") — matches the format
    # HR criteria use in search.py's language filter mapping and in the
    # scoring engine, so the same criterion value works for both.
    result = []
    for lang in raw_languages:
        code = lang.get("id")
        if not code:
            continue
        level = (lang.get("level") or {}).get("id")
        result.append(f"{code}:{level}" if level else code)
    return result


def _full_name(raw: dict[str, Any]) -> Optional[str]:
    # Only present once the employer has "opened" this resume's contacts —
    # absent (all None) on search-result-level resumes, which is expected.
    parts = [raw.get("last_name"), raw.get("first_name"), raw.get("middle_name")]
    parts = [p for p in parts if p]
    return " ".join(parts) if parts else None


def _build_text_blob(raw: dict[str, Any], skills: list[str], experience_entries: list[dict]) -> str:
    parts = [raw.get("title") or "", *skills]
    for entry in experience_entries:
        parts.append(entry.get("position") or "")
        parts.append(entry.get("company") or "")
        parts.append(entry.get("description") or "")
    return "\n".join(p for p in parts if p)


def _months_since_last_experience_end(experience_entries: list[dict]) -> Optional[int]:
    if not experience_entries:
        return None

    # HH lists experience most-recent-first.
    latest = experience_entries[0]
    end_raw = latest.get("end")
    if end_raw is None:
        return 0  # still employed there — as recent as it gets

    end_date = _parse_hh_date(end_raw)
    if end_date is None:
        return None

    today = date.today()
    return max(0, (today.year - end_date.year) * 12 + (today.month - end_date.month))


def _parse_hh_date(value: str) -> Optional[date]:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
