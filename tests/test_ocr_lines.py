"""OCR line parsing without Tesseract: fuzzy names, uncertainty flags, merging."""

from app.parsing.ocr_parser import OcrLine, fuzzy_match, parse_lines


def lines(*texts, confidence=95.0):
    return [OcrLine(text, confidence) for text in texts]


def test_exact_and_alias_names_are_certain():
    assert fuzzy_match("Rigger").certain
    assert fuzzy_match("Master / Mistress").key == "master-mistress"


def test_fuzzy_names():
    match = fuzzy_match("Exhibltionist")
    assert match.key == "exhibitionist"
    assert match.certain
    near = fuzzy_match("Rlgger")
    assert near.key == "rigger"
    assert not near.certain  # 83 < 85
    assert fuzzy_match("Weather") is None


def test_close_runner_up_is_ambiguous():
    match = fuzzy_match("Degradce")
    assert match.key in {"degrader", "degradee"}
    assert match.ambiguous
    assert not match.certain


def test_clean_lines():
    result = parse_lines(lines("== Results ==", "92% Rigger", "79% Dominant"))
    assert result.values == {"rigger": 92, "dominant": 79}
    assert result.errors == []
    assert "rigger" not in result.flagged
    assert len(result.flagged) == 23


def test_uncertain_name_is_filled_and_flagged():
    result = parse_lines(lines("92% Rlgger"))
    assert result.values == {"rigger": 92}
    assert "rigger" in result.flagged


def test_low_tesseract_confidence_is_flagged():
    result = parse_lines([OcrLine("92% Rigger", 41.0), OcrLine("79% Dominant", 96.0)])
    assert result.values == {"rigger": 92, "dominant": 79}
    assert "rigger" in result.flagged
    assert "dominant" not in result.flagged


def test_out_of_range_is_flagged():
    result = parse_lines(lines("192% Sadist"))
    assert "sadist" not in result.values
    assert "sadist" in result.flagged
    assert "вне диапазона" in result.errors[0]


def test_unpaired_category_is_flagged():
    result = parse_lines(lines("Masochist", "40% Sadist"))
    assert "masochist" not in result.values
    assert "masochist" in result.flagged


def test_overlapping_screenshots_merge_quietly():
    first = lines("92% Rigger", "79% Dominant")
    second = lines("79% Dominant", "10% Pet")
    result = parse_lines(first + second)
    assert result.values == {"rigger": 92, "dominant": 79, "pet": 10}
    assert result.errors == []
    assert "dominant" not in result.flagged


def test_repeat_upgrades_uncertain_reading():
    result = parse_lines([OcrLine("79% Dominant", 30.0), OcrLine("79% Dominant", 95.0)])
    assert "dominant" not in result.flagged


def test_conflicting_readings_keep_more_confident_and_flag():
    result = parse_lines([OcrLine("79% Dominant", 70.0), OcrLine("19% Dominant", 95.0)])
    assert result.values["dominant"] == 19
    assert "dominant" in result.flagged
    assert "по-разному" in result.errors[0]


def test_unknown_name_with_percent_is_reported():
    result = parse_lines(lines("55% Weather"))
    assert result.values == {}
    assert result.errors == ["Не удалось распознать категорию «Weather»."]
