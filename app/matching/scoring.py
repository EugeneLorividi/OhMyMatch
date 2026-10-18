"""Steps 2 to 6: effective profile, role fit, style similarity, final score."""

from collections.abc import Mapping
from dataclasses import dataclass

from app.categories import AXES, ROLE_PAIRS, STYLE_KEYS, SWITCH
from app.config import (
    ACTIVE_THRESHOLD,
    CURIOUS_FACTOR,
    CURIOUS_LOW,
    PAIR_WEIGHTS,
    WEIGHTS,
)
from app.matching.profile import Profile

Pair = tuple[str, str]


@dataclass(frozen=True)
class PairFit:
    value: float
    strict: bool  # comes from a strictly working direction, not the curiosity zone


@dataclass(frozen=True)
class MatchScore:
    score: float
    role_fit: float
    style_sim: float
    pairs: dict[Pair, PairFit]

    @property
    def has_strict(self) -> bool:
        return any(fit.strict for fit in self.pairs.values())


def effective_scores(scores: Mapping[str, int]) -> dict[str, int]:
    """Step 2: a Switch takes either side of every role pair at the stronger value."""
    effective = dict(scores)
    if scores[SWITCH] >= ACTIVE_THRESHOLD:
        for a, b in ROLE_PAIRS:
            effective[a] = effective[b] = max(scores[a], scores[b])
    return effective


def direction_value(x: int, y: int, experimental: bool) -> PairFit:
    low, high = min(x, y), max(x, y)
    if low >= ACTIVE_THRESHOLD:
        return PairFit(float(low), True)
    if experimental and high >= ACTIVE_THRESHOLD and low >= CURIOUS_LOW:
        return PairFit(CURIOUS_FACTOR * low, False)
    return PairFit(0.0, False)


def pair_fit(x: Mapping[str, int], y: Mapping[str, int], pair: Pair, experimental: bool) -> PairFit:
    a, b = pair
    one = direction_value(x[a], y[b], experimental)
    other = direction_value(x[b], y[a], experimental)
    candidates = sorted([one, other], key=lambda fit: (fit.value, fit.strict), reverse=True)
    return candidates[0]


def _pair_in_play(x: Mapping[str, int], y: Mapping[str, int], pair: Pair) -> bool:
    return any(profile[key] >= ACTIVE_THRESHOLD for profile in (x, y) for key in pair)


def role_fit(
    x: Mapping[str, int], y: Mapping[str, int], experimental: bool
) -> tuple[float, dict[Pair, PairFit]]:
    fits: dict[Pair, PairFit] = {}
    numerator = denominator = 0.0
    for pair in ROLE_PAIRS:
        if not _pair_in_play(x, y, pair):
            continue
        weight = PAIR_WEIGHTS.get(pair, 1.0)
        fit = pair_fit(x, y, pair, experimental)
        fits[pair] = fit
        numerator += weight * fit.value
        denominator += weight
    if denominator == 0:
        return 0.0, fits
    return numerator / denominator, fits


def style_similarity(x: Mapping[str, int], y: Mapping[str, int]) -> float:
    return sum(100 - abs(x[key] - y[key]) for key in STYLE_KEYS) / len(STYLE_KEYS)


def score_match(viewer: Profile, candidate: Profile) -> MatchScore:
    """Score as seen by `viewer`: the viewer's mode picks weights and the curiosity zone."""
    x = effective_scores(viewer.scores)
    y = effective_scores(candidate.scores)
    experimental = viewer.mode == "experimental"
    fit, pairs = role_fit(x, y, experimental)
    style = style_similarity(x, y)
    weight_roles, weight_style = WEIGHTS[viewer.mode]
    return MatchScore(weight_roles * fit + weight_style * style, fit, style, pairs)


AXIS_OF_PAIR: dict[Pair, str] = {pair: axis.key for axis in AXES for pair in axis.pairs}
