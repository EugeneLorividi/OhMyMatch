import pytest

from app.config import ACTIVE_THRESHOLD, CURIOUS_FACTOR, CURIOUS_LOW, WEIGHTS
from app.matching.scoring import (
    direction_value,
    effective_scores,
    role_fit,
    score_match,
    style_similarity,
)
from tests.matching_profiles import her, profile


def test_switch_takes_both_sides():
    scores = profile(switch=65, dominant=80, submissive=10, rigger=0, rope_bunny=70).scores
    effective = effective_scores(scores)
    assert effective["dominant"] == effective["submissive"] == 80
    assert effective["rigger"] == effective["rope-bunny"] == 70
    assert effective["switch"] == 65


def test_switch_below_threshold_changes_nothing():
    scores = profile(switch=64, dominant=80).scores
    assert effective_scores(scores) == dict(scores)


def test_switch_does_not_touch_style_or_structure():
    scores = profile(switch=100, vanilla=20, ageplayer=90, non_monogamist=10).scores
    effective = effective_scores(scores)
    for key in ("vanilla", "ageplayer", "experimentalist", "non-monogamist"):
        assert effective[key] == scores[key]


def test_switch_makes_two_dominants_match():
    dom = her(dominant=90)
    switch = profile(switch=80, dominant=85)
    assert not score_match(dom, profile(dominant=85)).has_strict
    assert score_match(dom, switch).has_strict


@pytest.mark.parametrize(
    ("x", "y", "experimental", "value", "strict"),
    [
        (65, 65, False, 65.0, True),
        (90, 70, False, 70.0, True),
        (90, 64, False, 0.0, False),
        (90, 64, True, CURIOUS_FACTOR * 64, False),
        (90, CURIOUS_LOW, True, CURIOUS_FACTOR * CURIOUS_LOW, False),
        (90, CURIOUS_LOW - 1, True, 0.0, False),
        (64, 50, True, 0.0, False),  # nobody really wants it
        (50, 90, True, CURIOUS_FACTOR * 50, False),
    ],
)
def test_direction_value(x, y, experimental, value, strict):
    fit = direction_value(x, y, experimental)
    assert fit.value == pytest.approx(value)
    assert fit.strict is strict


def test_best_of_two_directions():
    x = profile(dominant=70, submissive=95).scores
    y = her(dominant=90, submissive=80).scores
    _, pairs = role_fit(x, y, experimental=False)
    # x as sub with y as dom: min(95, 90) beats x as dom with y as sub: min(70, 80).
    assert pairs[("dominant", "submissive")].value == 90


def test_narrow_interests_are_not_diluted():
    rigger = profile(rigger=90)
    bunny = her(rope_bunny=80)
    match = score_match(rigger, bunny)
    assert match.role_fit == 80
    assert list(match.pairs) == [("rigger", "rope-bunny")]


def test_pair_counts_when_only_one_side_is_active():
    x = profile(rigger=90, dominant=90).scores
    y = her(rope_bunny=80, dominant=90).scores  # both dominant: no working power direction
    fit, pairs = role_fit(x, y, experimental=False)
    assert set(pairs) == {("rigger", "rope-bunny"), ("dominant", "submissive")}
    assert fit == pytest.approx((80 + 0) / 2)


def test_empty_denominator():
    fit, pairs = role_fit(profile().scores, her().scores, experimental=False)
    assert fit == 0
    assert pairs == {}
    assert not score_match(profile(), her()).has_strict


def test_style_similarity():
    x = profile(experimentalist=80, vanilla=20, ageplayer=0).scores
    y = her(experimentalist=60, vanilla=20, ageplayer=30).scores
    assert style_similarity(x, y) == pytest.approx((80 + 100 + 70) / 3)


def test_final_score_formula_by_viewer_mode():
    x = profile(rigger=90, experimentalist=50)
    y = her(rope_bunny=80, experimentalist=30)
    roles, style = 80, (80 + 100 + 100) / 3
    for mode in ("normal", "experimental"):
        viewer = profile(mode=mode, rigger=90, experimentalist=50)
        weight_roles, weight_style = WEIGHTS[mode]
        assert score_match(viewer, y).score == pytest.approx(
            weight_roles * roles + weight_style * style
        )
    assert (
        score_match(x, y).score
        != score_match(profile(mode="experimental", rigger=90, experimentalist=50), y).score
    )


def test_curiosity_zone_only_in_experimental_mode():
    y = her(submissive=50, rigger=70)
    normal = score_match(profile(dominant=90, rope_bunny=70), y)
    experimental = score_match(profile(mode="experimental", dominant=90, rope_bunny=70), y)
    assert normal.pairs[("dominant", "submissive")].value == 0
    assert experimental.pairs[("dominant", "submissive")].value == CURIOUS_FACTOR * 50
    assert experimental.role_fit > normal.role_fit


def test_curiosity_alone_never_qualifies():
    viewer = profile(mode="experimental", dominant=90)
    only_curious = her(submissive=60)
    match = score_match(viewer, only_curious)
    assert match.role_fit > 0
    assert not match.has_strict


def test_threshold_constant_matches_spec():
    assert ACTIVE_THRESHOLD == 65
