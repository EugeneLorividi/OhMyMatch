"""Step 1: hard, mutual filters. Uses raw scores, before the Switch expansion."""

from app.categories import NON_MONOGAMIST
from app.config import ACTIVE_THRESHOLD, NONMONO_LOW
from app.matching.profile import Profile


def genders_match(x: Profile, y: Profile) -> bool:
    return y.gender in x.seeking and x.gender in y.seeking


def non_monogamy_compatible(x: Profile, y: Profile) -> bool:
    a, b = x.scores[NON_MONOGAMIST], y.scores[NON_MONOGAMIST]
    wants_open = a >= ACTIVE_THRESHOLD or b >= ACTIVE_THRESHOLD
    rejects_open = (a >= ACTIVE_THRESHOLD and b <= NONMONO_LOW) or (
        b >= ACTIVE_THRESHOLD and a <= NONMONO_LOW
    )
    return not (wants_open and rejects_open)


def active_categories(profile: Profile) -> set[str]:
    return {key for key, value in profile.scores.items() if value >= ACTIVE_THRESHOLD}


def dislikes_respected(x: Profile, y: Profile) -> bool:
    return not (active_categories(y) & x.dislikes) and not (active_categories(x) & y.dislikes)


def passes_filters(viewer: Profile, candidate: Profile, excluded: frozenset = frozenset()) -> bool:
    """`excluded`: ids hidden by reactions (blocks either way, viewer's likes and passes)."""
    return (
        candidate.id != viewer.id
        and candidate.id not in excluded
        and genders_match(viewer, candidate)
        and non_monogamy_compatible(viewer, candidate)
        and dislikes_respected(viewer, candidate)
    )
