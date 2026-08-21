from dataclasses import dataclass

from app.db.models.enums import CriterionMode
from app.providers.hh.search import build_search_params


@dataclass
class C:
    key: str
    value: str
    mode: CriterionMode = CriterionMode.PREFERRED


def test_required_structured_criterion_becomes_hard_filter():
    params = build_search_params([C("employment_type", "full", CriterionMode.REQUIRED)])

    assert params["employment_form"] == ["FULL"]


def test_preferred_structured_criterion_is_never_sent_as_filter():
    params = build_search_params([C("employment_type", "full", CriterionMode.PREFERRED)])

    assert "employment_form" not in params
    # Falls back to a preferred (OR) text term instead.
    assert params["text"] == ["(full)"]


def test_ignore_mode_is_dropped_entirely():
    params = build_search_params([C("employment_type", "full", CriterionMode.IGNORE)])

    assert params == {}


def test_unmapped_required_keyword_becomes_mandatory_text_term():
    params = build_search_params([C("vertical", "igaming", CriterionMode.REQUIRED)])

    assert params["text"] == ["igaming"]


def test_unmapped_preferred_keywords_are_or_grouped():
    params = build_search_params(
        [
            C("technology", "Keitaro", CriterionMode.PREFERRED),
            C("technology", "PWA", CriterionMode.PREFERRED),
        ]
    )

    assert params["text"] == ["(Keitaro OR PWA)"]


def test_required_and_preferred_text_terms_combine_with_and():
    params = build_search_params(
        [
            C("vertical", "igaming", CriterionMode.REQUIRED),
            C("technology", "Keitaro", CriterionMode.PREFERRED),
        ]
    )

    assert params["text"] == ["igaming AND (Keitaro)"]


def test_multiple_required_structured_values_repeat_the_param():
    params = build_search_params(
        [
            C("experience_level", "3_6_years", CriterionMode.REQUIRED),
            C("experience_level", "6_plus_years", CriterionMode.REQUIRED),
        ]
    )

    assert params["experience"] == ["between3And6", "moreThan6"]


def test_geo_area_id_requires_numeric_value():
    numeric = build_search_params([C("geo_area_id", "1", CriterionMode.REQUIRED)])
    non_numeric = build_search_params([C("geo_area_id", "Moscow", CriterionMode.REQUIRED)])

    assert numeric["area"] == ["1"]
    assert "area" not in non_numeric
    assert non_numeric["text"] == ["Moscow"]


def test_language_criterion_converts_colon_to_dot():
    params = build_search_params([C("language", "eng:b2", CriterionMode.REQUIRED)])

    assert params["language"] == ["eng.b2"]
