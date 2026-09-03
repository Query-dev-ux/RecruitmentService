from dataclasses import dataclass

from app.criteria import split_alternatives
from app.db.models.enums import CriterionMode
from app.providers.base import ParsedProfile
from app.providers.hh.search import build_search_params
from app.scoring.engine import score_candidate


@dataclass
class C:
    key: str
    value: str
    mode: CriterionMode
    weight: int = 0


def test_split_alternatives_basic():
    assert split_alternatives("Media Buyer|Traffic Manager") == ["Media Buyer", "Traffic Manager"]


def test_split_alternatives_trims_whitespace_and_drops_empties():
    assert split_alternatives(" Media Buyer | Traffic Manager |  ") == ["Media Buyer", "Traffic Manager"]


def test_split_alternatives_single_value_is_one_item_list():
    assert split_alternatives("Media Buyer") == ["Media Buyer"]


# --- search.py: HH query building ---


def test_required_position_synonyms_become_single_or_and_term():
    params = build_search_params(
        [C("position", "Media Buyer|Traffic Manager|Team Lead Media Buying", CriterionMode.REQUIRED)]
    )

    assert params["text"] == ["(Media Buyer OR Traffic Manager OR Team Lead Media Buying)"]


def test_required_structured_field_alternatives_repeat_the_hh_param():
    params = build_search_params(
        [C("job_search_status", "active_search|looking_for_offers", CriterionMode.REQUIRED)]
    )

    assert params["job_search_status"] == ["active_search", "looking_for_offers"]


def test_preferred_alternatives_are_nested_in_the_outer_or_group():
    params = build_search_params(
        [
            C("technology", "Keitaro|Binom", CriterionMode.PREFERRED, weight=10),
            C("technology", "PWA", CriterionMode.PREFERRED, weight=10),
        ]
    )

    assert params["text"] == ["((Keitaro OR Binom) OR PWA)"]


def test_structured_alternatives_skip_invalid_entries_but_keep_valid_ones():
    params = build_search_params([C("employment_type", "full|not_a_real_value", CriterionMode.REQUIRED)])

    assert params["employment_form"] == ["FULL"]


# --- scoring/engine.py: candidate matching ---


def profile(**overrides) -> ParsedProfile:
    defaults = dict(
        position_title="Traffic Manager",
        employment_type="full",
        job_search_status="looking_for_offers",
        text_blob="Traffic Manager with Facebook Ads experience",
    )
    defaults.update(overrides)
    return ParsedProfile(**defaults)


def test_required_alternative_passes_if_any_matches():
    criteria = [C("job_search_status", "active_search|looking_for_offers", CriterionMode.REQUIRED)]

    result = score_candidate(profile(job_search_status="looking_for_offers"), criteria)

    assert result.hard_filters_passed is True


def test_required_alternative_fails_if_none_match():
    criteria = [C("job_search_status", "active_search|has_job_offer", CriterionMode.REQUIRED)]

    result = score_candidate(profile(job_search_status="looking_for_offers"), criteria)

    assert result.hard_filters_passed is False


def test_preferred_alternative_keyword_match_scores_full_on_any_hit():
    criteria = [C("technology", "Keitaro|Binom", CriterionMode.PREFERRED, weight=100)]

    result = score_candidate(profile(text_blob="Uses Binom for tracking"), criteria)

    assert result.score == 100
