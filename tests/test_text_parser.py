from app.categories import CATEGORIES, CATEGORY_KEYS
from app.parsing.text_parser import match_name, parse_text
from tests.helpers import full_result_text


def test_full_list():
    result = parse_text(full_result_text())
    assert result.errors == []
    assert result.flagged == set()
    assert set(result.values) == set(CATEGORY_KEYS)
    assert result.values["switch"] == 0
    assert result.values["rigger"] == 8


def test_spec_example():
    result = parse_text("100% Switch\n92% Rigger\n79% Dominant")
    assert result.values == {"switch": 100, "rigger": 92, "dominant": 79}
    assert result.errors == []
    assert len(result.missing) == 22
    assert result.flagged == set(result.missing)


def test_garbage_lines_and_link_are_ignored():
    text = "\n".join(
        [
            "My results",
            "https://bdsmtest.org/r/abcdef",
            "",
            "Percent  Role",
            "100%Switch",  # no space after %, does not match the spec regex
            "abc 50% Rigger",
            "50% Rigger",
        ]
    )
    result = parse_text(text)
    assert result.values == {"rigger": 50}
    assert result.errors == []


def test_case_and_extra_spaces():
    result = parse_text("   92   %    rIGGER   \n7 % rope   BUNNY\n5% PRIMAL ( hunter )")
    assert result.values == {"rigger": 92, "rope-bunny": 7, "primal-hunter": 5}


def test_unicode_spaces():
    text = "92% Rigger\n 89 % Rope bunny\n﻿12% Brat tamer\n5％ Pet"
    result = parse_text(text)
    assert result.values == {"rigger": 92, "rope-bunny": 89, "brat-tamer": 12, "pet": 5}
    assert result.errors == []


def test_tabs():
    assert parse_text("92%\tRigger").values == {"rigger": 92}


def test_aliases():
    for name, key in [
        ("Non monogamist", "non-monogamist"),
        ("Non‑monogamist", "non-monogamist"),
        ("Master / Mistress", "master-mistress"),
        ("Mistress", "master-mistress"),
        ("Daddy/Mummy", "daddy-mommy"),
        ("Primal Prey", "primal-prey"),
        ("Primal(Prey)", "primal-prey"),
        ("Age player", "ageplayer"),
    ]:
        assert match_name(name) == key, name
    assert match_name("Dom") is None


def test_out_of_range():
    result = parse_text("101% Switch\n999% Rigger\n0% Vanilla\n100% Pet")
    assert result.values == {"vanilla": 0, "pet": 100}
    assert len(result.errors) == 2
    assert "Switch" in result.errors[0] and "0–100" in result.errors[0]
    assert {"switch", "rigger"} <= result.flagged


def test_unknown_category_is_an_error():
    result = parse_text("50% Rigger\n40% Unicorn")
    assert result.values == {"rigger": 50}
    assert result.errors == ["Строка 2: неизвестная категория «Unicorn»."]


def test_duplicate_with_different_value_is_dropped_and_flagged():
    result = parse_text("50% Rigger\n10% Switch\n60% rigger")
    assert "rigger" not in result.values
    assert "rigger" in result.flagged
    assert result.values == {"switch": 10}
    assert "повторяется" in result.errors[0]
    assert "строке 1" in result.errors[0]


def test_duplicate_with_same_value_is_kept_but_flagged():
    result = parse_text("50% Rigger\n50% Rigger")
    assert result.values == {"rigger": 50}
    assert "rigger" in result.flagged
    assert len(result.errors) == 1


def test_missing_categories_are_flagged():
    text = "\n".join(f"10% {c.name}" for c in CATEGORIES if c.key != "little")
    result = parse_text(text)
    assert result.missing == ["little"]
    assert result.flagged == {"little"}


def test_non_ascii_digits_do_not_match():
    assert parse_text("٥٠% Rigger").values == {}
