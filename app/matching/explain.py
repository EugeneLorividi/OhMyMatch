"""Step 7: the only thing a candidate card says about the match. Axis names, nothing else."""

from dataclasses import dataclass

from app.categories import AXES
from app.config import EXPLAIN_MAX_AXES
from app.matching.scoring import AXIS_OF_PAIR, MatchScore

_AXIS_ORDER = {axis.key: index for index, axis in enumerate(AXES)}
_AXIS_LABEL = {axis.key: axis.label for axis in AXES}


@dataclass(frozen=True)
class Explanation:
    matched: tuple[str, ...]  # "совпали по: ..."
    curious: tuple[str, ...]  # "можно попробовать: ..."


def explain(match: MatchScore) -> Explanation:
    strict: dict[str, float] = {}
    curious: dict[str, float] = {}
    for pair, fit in match.pairs.items():
        if fit.value <= 0:
            continue
        axis = AXIS_OF_PAIR[pair]
        bucket = strict if fit.strict else curious
        bucket[axis] = max(bucket.get(axis, 0.0), fit.value)
    for axis in strict:
        curious.pop(axis, None)

    def ranked(axes: dict[str, float]) -> list[str]:
        order = sorted(axes, key=lambda key: (-axes[key], _AXIS_ORDER[key]))
        return [_AXIS_LABEL[key] for key in order]

    matched = ranked(strict)[:EXPLAIN_MAX_AXES]
    room = EXPLAIN_MAX_AXES - len(matched)
    return Explanation(tuple(matched), tuple(ranked(curious)[:room]))
