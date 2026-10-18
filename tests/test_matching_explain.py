from app.categories import CATEGORIES
from app.matching.explain import explain
from app.matching.scoring import score_match
from tests.matching_profiles import her, profile


def test_matched_axes_only_names():
    viewer = profile(dominant=90, sadist=80, rigger=70)
    candidate = her(submissive=85, masochist=95, rope_bunny=70)
    explanation = explain(score_match(viewer, candidate))
    assert explanation.matched == ("power", "pain", "rope")
    assert explanation.curious == ()
    names = {c.name.lower() for c in CATEGORIES} | {c.key for c in CATEGORIES}
    for label in explanation.matched:
        assert label not in names


def test_axis_ranked_by_strength():
    viewer = profile(dominant=70, sadist=95)
    candidate = her(submissive=70, masochist=95)
    assert explain(score_match(viewer, candidate)).matched == ("pain", "power")


def test_curious_axes_are_separate():
    viewer = profile(mode="experimental", dominant=90, brat_tamer=80)
    candidate = her(submissive=80, brat=40)
    explanation = explain(score_match(viewer, candidate))
    assert explanation.matched == ("power",)
    assert explanation.curious == ("play",)


def test_axis_with_strict_and_curious_pairs_counts_as_matched():
    viewer = profile(mode="experimental", dominant=90, owner=90)
    candidate = her(submissive=80, pet=40)
    explanation = explain(score_match(viewer, candidate))
    assert explanation.matched == ("power",)
    assert explanation.curious == ()


def test_at_most_five_axes():
    viewer = profile(
        switch=90,
        dominant=90,
        sadist=90,
        rigger=90,
        brat=90,
        degrader=90,
        daddy_mommy=90,
        voyeur=90,
    )
    candidate = her(
        switch=90,
        dominant=90,
        sadist=90,
        rigger=90,
        brat=90,
        degrader=90,
        daddy_mommy=90,
        voyeur=90,
    )
    explanation = explain(score_match(viewer, candidate))
    assert len(explanation.matched) == 5
    assert explanation.curious == ()
