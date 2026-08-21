from dataclasses import dataclass

from app.db.models.enums import CriterionMode, ScoreTier
from app.providers.base import ParsedProfile
from app.scoring.engine import score_candidate


@dataclass
class C:
    key: str
    value: str
    mode: CriterionMode
    weight: int = 0


def profile(**overrides) -> ParsedProfile:
    defaults = dict(
        total_experience_months=18,
        employment_type="full",
        work_format="remote",
        job_search_status="active_search",
        geo="Philippines",
        languages=["eng:b2"],
        salary_expectation=1500,
        last_experience_ended_months_ago=0,
        text_blob="Facebook Ads iGaming Keitaro PWA iOS Android",
    )
    defaults.update(overrides)
    return ParsedProfile(**defaults)


def test_failed_required_criterion_fails_hard_filters():
    result = score_candidate(profile(), [C("vertical", "crypto", CriterionMode.REQUIRED)])

    assert result.hard_filters_passed is False


def test_passed_required_criteria_dont_affect_score():
    result = score_candidate(
        profile(),
        [
            C("vertical", "igaming", CriterionMode.REQUIRED),
            C("traffic_source", "facebook", CriterionMode.REQUIRED),
        ],
    )

    assert result.hard_filters_passed is True
    assert result.score == 0  # no preferred criteria -> no score contribution


def test_brief_example_scores_as_hot():
    # Mirrors the brief's own worked example: iGaming(+25) Facebook(+15)
    # 1yr+ exp(+10) iOS(+10) Android(+5) PWA(+10) Keitaro(+10) $1000+/day(+10)
    # recent exp(+5) = 100 -> HOT.
    criteria = [
        C("vertical", "igaming", CriterionMode.REQUIRED),
        C("traffic_source", "facebook", CriterionMode.REQUIRED),
        C("min_experience_months", "12", CriterionMode.PREFERRED, weight=10),
        C("technology", "iOS", CriterionMode.PREFERRED, weight=10),
        C("technology", "Android", CriterionMode.PREFERRED, weight=5),
        C("technology", "PWA", CriterionMode.PREFERRED, weight=10),
        C("technology", "Keitaro", CriterionMode.PREFERRED, weight=10),
        C("salary_from", "1000", CriterionMode.PREFERRED, weight=10),
        C("recent_experience_months", "6", CriterionMode.PREFERRED, weight=5),
        # required-only criteria contribute no score weight themselves, so
        # add the brief's igaming/facebook preferred-style weight explicitly
        # via separate preferred keyword criteria to hit the full 100:
        C("vertical", "igaming", CriterionMode.PREFERRED, weight=25),
        C("traffic_source", "facebook", CriterionMode.PREFERRED, weight=15),
    ]

    result = score_candidate(profile(), criteria)

    assert result.hard_filters_passed is True
    assert result.score == 100
    assert result.tier == ScoreTier.HOT


def test_partial_preferred_match_scales_score_and_tier():
    criteria = [
        C("technology", "Keitaro", CriterionMode.PREFERRED, weight=50),
        C("technology", "PWA", CriterionMode.PREFERRED, weight=50),
    ]

    result = score_candidate(profile(text_blob="Keitaro only, no other tools"), criteria)

    assert result.score == 50
    assert result.tier == ScoreTier.LOW  # default thresholds: medium starts at 55


def test_ignore_mode_never_affects_score_or_hard_filters():
    criteria = [C("vertical", "crypto", CriterionMode.IGNORE, weight=999)]

    result = score_candidate(profile(), criteria)

    assert result.hard_filters_passed is True
    assert result.score == 0
    assert result.breakdown == {}


def test_weights_are_rescaled_regardless_of_their_sum():
    criteria = [C("technology", "Keitaro", CriterionMode.PREFERRED, weight=5)]

    result = score_candidate(profile(), criteria)

    assert result.score == 100  # single fully-matched criterion -> 100%, whatever its raw weight


def test_custom_score_thresholds_override_defaults():
    criteria = [C("technology", "Keitaro", CriterionMode.PREFERRED, weight=100)]

    result = score_candidate(profile(), criteria, score_thresholds={"medium": 10, "high": 50, "hot": 101})

    assert result.tier == ScoreTier.HIGH  # 100 >= high(50) but < hot(101)


def test_experience_level_bucket_match():
    criteria = [C("experience_level", "1_3_years", CriterionMode.REQUIRED)]

    passes = score_candidate(profile(total_experience_months=18), criteria)
    fails = score_candidate(profile(total_experience_months=6), criteria)

    assert passes.hard_filters_passed is True
    assert fails.hard_filters_passed is False


def test_language_matches_code_only_regardless_of_level():
    criteria = [C("language", "eng", CriterionMode.REQUIRED)]

    result = score_candidate(profile(languages=["eng:c1"]), criteria)

    assert result.hard_filters_passed is True


def test_language_with_level_requires_exact_level():
    criteria = [C("language", "eng:b2", CriterionMode.REQUIRED)]

    result = score_candidate(profile(languages=["eng:c1"]), criteria)

    assert result.hard_filters_passed is False


def test_recent_experience_criterion():
    criteria = [C("recent_experience_months", "6", CriterionMode.REQUIRED)]

    recent = score_candidate(profile(last_experience_ended_months_ago=3), criteria)
    stale = score_candidate(profile(last_experience_ended_months_ago=12), criteria)

    assert recent.hard_filters_passed is True
    assert stale.hard_filters_passed is False


def test_missing_profile_data_fails_required_criterion_gracefully():
    criteria = [C("salary_from", "1000", CriterionMode.REQUIRED)]

    result = score_candidate(profile(salary_expectation=None), criteria)

    assert result.hard_filters_passed is False
