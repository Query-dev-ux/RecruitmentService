"""Provider-agnostic scoring — the same function scores HH and (later)
Telegram candidates identically, since both normalize into ParsedProfile
first (providers/base.py, providers/hh/normalize.py).

REQUIRED criteria gate hard_filters_passed (any failed REQUIRED criterion
rejects the candidate outright, mirroring how HH's own search filters
would have excluded it — but this also re-checks HH-sourced candidates and
is the *only* gate for candidates from sources with no equivalent search
filter, like Telegram). PREFERRED criteria each contribute
weight * match_fraction to the score, then the total is rescaled to 0-100
regardless of what the weights happen to sum to, so HR doesn't have to make
their weights add up to exactly 100. IGNORE is skipped entirely.

Criterion keys recognized here intentionally mirror providers/hh/search.py's
structured-field keys (experience_level, employment_type, work_format,
job_search_status, language, salary_from/to) so the same HR-entered
criterion drives both the HH search filter and the post-fetch score.
Anything else falls back to a case-insensitive substring match against
ParsedProfile.text_blob — this is how free-text criteria like "iGaming",
"Facebook", "Keitaro", "PWA" (not real structured fields anywhere) get
scored.
"""

from dataclasses import dataclass
from typing import Optional, Protocol

from app.db.models.enums import CriterionMode, ScoreTier
from app.providers.base import ParsedProfile

DEFAULT_SCORE_THRESHOLDS = {"low": 0, "medium": 55, "high": 75, "hot": 90}

# Matches providers/hh/search.py's EXPERIENCE_LEVELS keys, expressed as a
# minimum months-of-experience floor for scoring purposes.
EXPERIENCE_LEVEL_MIN_MONTHS = {
    "no_experience": 0,
    "1_3_years": 12,
    "3_6_years": 36,
    "6_plus_years": 72,
}


class Criterion(Protocol):
    key: str
    value: str
    mode: CriterionMode
    weight: int


@dataclass
class ScoreResult:
    score: int
    tier: ScoreTier
    hard_filters_passed: bool
    breakdown: dict


def score_candidate(
    profile: ParsedProfile,
    criteria: list[Criterion],
    score_thresholds: Optional[dict] = None,
) -> ScoreResult:
    thresholds = {**DEFAULT_SCORE_THRESHOLDS, **(score_thresholds or {})}

    hard_filters_passed = True
    breakdown: dict[str, dict] = {}
    raw_score = 0.0
    max_possible = 0.0

    for criterion in criteria:
        if criterion.mode == CriterionMode.IGNORE:
            continue

        match_fraction = _match(criterion.key, criterion.value, profile)

        if criterion.mode == CriterionMode.REQUIRED:
            passed = match_fraction >= 1.0
            breakdown[criterion.key] = {"mode": "required", "passed": passed}
            if not passed:
                hard_filters_passed = False
        else:  # PREFERRED
            contribution = criterion.weight * match_fraction
            raw_score += contribution
            max_possible += criterion.weight
            breakdown[criterion.key] = {
                "mode": "preferred",
                "match_fraction": round(match_fraction, 3),
                "weight": criterion.weight,
                "contribution": round(contribution, 3),
            }

    score = _normalize_score(raw_score, max_possible)
    tier = _tier_for_score(score, thresholds)

    return ScoreResult(score=score, tier=tier, hard_filters_passed=hard_filters_passed, breakdown=breakdown)


def _normalize_score(raw_score: float, max_possible: float) -> int:
    if max_possible <= 0:
        return 0
    return round(max(0.0, min(100.0, 100.0 * raw_score / max_possible)))


def _tier_for_score(score: int, thresholds: dict) -> ScoreTier:
    if score >= thresholds["hot"]:
        return ScoreTier.HOT
    if score >= thresholds["high"]:
        return ScoreTier.HIGH
    if score >= thresholds["medium"]:
        return ScoreTier.MEDIUM
    return ScoreTier.LOW


def _match(key: str, value: str, profile: ParsedProfile) -> float:
    if key == "experience_level":
        return _match_experience_level(value, profile.total_experience_months)
    if key == "min_experience_months":
        return _match_min_experience_months(value, profile.total_experience_months)
    if key == "employment_type":
        return _exact_match(value, profile.employment_type)
    if key == "work_format":
        return _exact_match(value, profile.work_format)
    if key == "job_search_status":
        return _exact_match(value, profile.job_search_status)
    if key == "geo":
        return _text_contains(profile.geo, value)
    if key == "language":
        return _match_language(value, profile.languages)
    if key == "salary_from":
        return _match_salary_from(value, profile.salary_expectation)
    if key == "salary_to":
        return _match_salary_to(value, profile.salary_expectation)
    if key == "recent_experience_months":
        return _match_recent_experience(value, profile.last_experience_ended_months_ago)
    # Default: keyword match — vertical, traffic_source, technology, and any
    # other free-text criterion that isn't a structured HH field.
    return _text_contains(profile.text_blob, value)


def _exact_match(expected: str, actual: Optional[str]) -> float:
    return 1.0 if actual is not None and actual == expected else 0.0


def _text_contains(haystack: Optional[str], needle: str) -> float:
    if not haystack or not needle:
        return 0.0
    return 1.0 if needle.lower() in haystack.lower() else 0.0


def _match_experience_level(value: str, total_months: Optional[int]) -> float:
    if total_months is None or value not in EXPERIENCE_LEVEL_MIN_MONTHS:
        return 0.0
    return 1.0 if total_months >= EXPERIENCE_LEVEL_MIN_MONTHS[value] else 0.0


def _match_min_experience_months(value: str, total_months: Optional[int]) -> float:
    required = _parse_int(value)
    if required is None or total_months is None:
        return 0.0
    if required <= 0 or total_months >= required:
        return 1.0
    return max(0.0, total_months / required)


def _match_recent_experience(value: str, months_ago: Optional[int]) -> float:
    """value = max months since the candidate's last role ended, to still
    count as "recent" (brief's example: last 3-6 months)."""
    max_months = _parse_int(value)
    if max_months is None or months_ago is None:
        return 0.0
    return 1.0 if months_ago <= max_months else 0.0


def _match_language(value: str, languages: list[str]) -> float:
    # value is "code" or "code:level" (e.g. "eng" or "eng:b2") — same format
    # normalize.py produces and search.py's HH filter mapping expects.
    normalized_languages = [lang.lower() for lang in languages]
    if ":" in value:
        return 1.0 if value.lower() in normalized_languages else 0.0
    code = value.lower()
    return 1.0 if any(lang == code or lang.startswith(f"{code}:") for lang in normalized_languages) else 0.0


def _match_salary_from(value: str, salary_expectation: Optional[int]) -> float:
    minimum = _parse_int(value)
    if minimum is None or salary_expectation is None:
        return 0.0
    return 1.0 if salary_expectation >= minimum else 0.0


def _match_salary_to(value: str, salary_expectation: Optional[int]) -> float:
    maximum = _parse_int(value)
    if maximum is None or salary_expectation is None:
        return 0.0
    return 1.0 if salary_expectation <= maximum else 0.0


def _parse_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
