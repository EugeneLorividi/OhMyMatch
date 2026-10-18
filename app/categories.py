"""The 25 bdsmtest.org categories, their axes and role pairs. Single source of truth."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    key: str
    name: str


@dataclass(frozen=True)
class Axis:
    key: str
    label: str  # Russian, shown in "совпали по: ..."
    pairs: tuple[tuple[str, str], ...] = ()
    style: tuple[str, ...] = ()


CATEGORIES: tuple[Category, ...] = (
    Category("switch", "Switch"),
    Category("vanilla", "Vanilla"),
    Category("rigger", "Rigger"),
    Category("non-monogamist", "Non-monogamist"),
    Category("rope-bunny", "Rope bunny"),
    Category("dominant", "Dominant"),
    Category("submissive", "Submissive"),
    Category("voyeur", "Voyeur"),
    Category("exhibitionist", "Exhibitionist"),
    Category("experimentalist", "Experimentalist"),
    Category("pet", "Pet"),
    Category("brat", "Brat"),
    Category("owner", "Owner"),
    Category("brat-tamer", "Brat tamer"),
    Category("master-mistress", "Master/Mistress"),
    Category("sadist", "Sadist"),
    Category("slave", "Slave"),
    Category("degrader", "Degrader"),
    Category("masochist", "Masochist"),
    Category("daddy-mommy", "Daddy/Mommy"),
    Category("primal-hunter", "Primal (Hunter)"),
    Category("degradee", "Degradee"),
    Category("ageplayer", "Ageplayer"),
    Category("little", "Little"),
    Category("primal-prey", "Primal (Prey)"),
)
CATEGORY_KEYS: tuple[str, ...] = tuple(c.key for c in CATEGORIES)
CATEGORY_BY_KEY: dict[str, Category] = {c.key: c for c in CATEGORIES}

SWITCH = "switch"
NON_MONOGAMIST = "non-monogamist"

AXES: tuple[Axis, ...] = (
    Axis(
        "power",
        "власть",
        pairs=(
            ("dominant", "submissive"),
            ("master-mistress", "slave"),
            ("owner", "pet"),
        ),
    ),
    Axis("pain", "боль", pairs=(("sadist", "masochist"),)),
    Axis("rope", "верёвки", pairs=(("rigger", "rope-bunny"),)),
    Axis(
        "play",
        "игра",
        pairs=(("brat", "brat-tamer"), ("primal-hunter", "primal-prey")),
    ),
    Axis("humiliation", "унижение", pairs=(("degrader", "degradee"),)),
    Axis("care", "опека", pairs=(("daddy-mommy", "little"),)),
    Axis("display", "показ", pairs=(("voyeur", "exhibitionist"),)),
    Axis("style", "стиль", style=("experimentalist", "vanilla", "ageplayer")),
)
ROLE_PAIRS: tuple[tuple[str, str], ...] = tuple(p for axis in AXES for p in axis.pairs)
STYLE_KEYS: tuple[str, ...] = next(axis.style for axis in AXES if axis.style)

# Alternative spellings, written in normalized form (see parsing.text_parser.normalize_name).
ALIASES: dict[str, str] = {
    "non monogamist": "non-monogamist",
    "nonmonogamist": "non-monogamist",
    "non-monogamous": "non-monogamist",
    "non monogamous": "non-monogamist",
    "rope-bunny": "rope-bunny",
    "ropebunny": "rope-bunny",
    "brat-tamer": "brat-tamer",
    "brattamer": "brat-tamer",
    "master": "master-mistress",
    "mistress": "master-mistress",
    "mistress/master": "master-mistress",
    "master-mistress": "master-mistress",
    "daddy": "daddy-mommy",
    "mommy": "daddy-mommy",
    "mummy": "daddy-mommy",
    "daddy/mummy": "daddy-mommy",
    "mommy/daddy": "daddy-mommy",
    "daddy-mommy": "daddy-mommy",
    "primal hunter": "primal-hunter",
    "primal-hunter": "primal-hunter",
    "hunter": "primal-hunter",
    "primal prey": "primal-prey",
    "primal-prey": "primal-prey",
    "prey": "primal-prey",
    "age player": "ageplayer",
    "age-player": "ageplayer",
}


def _check() -> None:
    paired = [key for pair in ROLE_PAIRS for key in pair]
    problems = [
        len(CATEGORY_KEYS) != 25 or len(set(CATEGORY_KEYS)) != 25,
        len(paired) != len(set(paired)),
        set(paired) | set(STYLE_KEYS) | {SWITCH, NON_MONOGAMIST} != set(CATEGORY_KEYS),
        not set(ALIASES.values()) <= set(CATEGORY_KEYS),
    ]
    if any(problems):
        raise RuntimeError("categories.py is inconsistent")


_check()
