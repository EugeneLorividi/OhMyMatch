from app.categories import (
    ALIASES,
    AXES,
    CATEGORIES,
    CATEGORY_KEYS,
    NON_MONOGAMIST,
    ROLE_PAIRS,
    STYLE_KEYS,
    SWITCH,
)


def test_canonical_list():
    assert len(CATEGORIES) == 25
    assert [c.name for c in CATEGORIES][:3] == ["Switch", "Vanilla", "Rigger"]
    for key in CATEGORY_KEYS:
        assert key == key.lower()
        assert " " not in key


def test_every_category_has_exactly_one_role():
    paired = [key for pair in ROLE_PAIRS for key in pair]
    assert len(paired) == len(set(paired)) == 20
    assert set(STYLE_KEYS) == {"experimentalist", "vanilla", "ageplayer"}
    assert set(paired) | set(STYLE_KEYS) | {SWITCH, NON_MONOGAMIST} == set(CATEGORY_KEYS)


def test_axes_from_spec():
    assert [axis.key for axis in AXES] == [
        "power",
        "pain",
        "rope",
        "play",
        "humiliation",
        "care",
        "display",
        "style",
    ]
    power = next(axis for axis in AXES if axis.key == "power")
    assert power.pairs == (
        ("dominant", "submissive"),
        ("master-mistress", "slave"),
        ("owner", "pet"),
    )


def test_aliases_point_to_real_keys():
    assert set(ALIASES.values()) <= set(CATEGORY_KEYS)
