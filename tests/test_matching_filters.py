import random

import pytest

from app.categories import CATEGORY_KEYS
from app.matching.filters import (
    dislikes_respected,
    genders_match,
    non_monogamy_compatible,
    passes_filters,
)
from app.matching.profile import Profile
from tests.matching_profiles import her, profile


def test_self_and_excluded():
    x = profile()
    y = her()
    assert passes_filters(x, y)
    assert not passes_filters(x, x)
    assert not passes_filters(x, y, frozenset({y.id}))


def test_gender_is_mutual():
    man_for_women = profile(gender="man", seeking=("woman",))
    woman_for_women = her(seeking=("woman",))
    woman_for_men = her(seeking=("man",))
    assert genders_match(man_for_women, woman_for_men)
    assert not genders_match(man_for_women, woman_for_women)
    assert not genders_match(woman_for_women, man_for_women)
    other = profile(gender="other", seeking=("man", "woman", "other"))
    assert genders_match(other, profile(gender="woman", seeking=("other",)))


@pytest.mark.parametrize(
    ("a", "b", "ok"),
    [
        (65, 35, False),
        (90, 0, False),
        (65, 36, True),
        (64, 0, True),
        (90, 90, True),
        (10, 10, True),
        (35, 65, False),
    ],
)
def test_non_monogamist(a, b, ok):
    x = profile(non_monogamist=a)
    y = her(non_monogamist=b)
    assert non_monogamy_compatible(x, y) is ok
    assert non_monogamy_compatible(y, x) is ok


def test_dislikes_both_ways():
    viewer = profile(dislikes=("pet",))
    assert not dislikes_respected(viewer, her(pet=65))
    assert dislikes_respected(viewer, her(pet=64))
    assert not dislikes_respected(her(pet=65), viewer)
    shy = her(dislikes=("sadist",))
    assert not dislikes_respected(profile(sadist=80), shy)
    assert dislikes_respected(profile(sadist=80), her())


def test_dislikes_use_raw_scores_not_switch_expansion():
    # A switch who is dominant but not submissive does not trip a "submissive" dislike.
    switch = her(switch=90, dominant=80, submissive=10)
    assert dislikes_respected(profile(dislikes=("submissive",)), switch)


def _random_profile(rng: random.Random) -> Profile:
    genders = ("man", "woman", "other")
    seeking = tuple(g for g in genders if rng.random() < 0.6) or ("woman",)
    dislikes = tuple(k for k in CATEGORY_KEYS if rng.random() < 0.1)
    scores = {k.replace("-", "_"): rng.randint(0, 100) for k in CATEGORY_KEYS}
    return profile(gender=rng.choice(genders), seeking=seeking, dislikes=dislikes, **scores)


def test_filters_are_symmetric():
    rng = random.Random(7)
    people = [_random_profile(rng) for _ in range(60)]
    passed = 0
    for x in people:
        for y in people:
            assert passes_filters(x, y) == passes_filters(y, x)
            passed += passes_filters(x, y)
    assert passed > 0
