from pathlib import Path

CSS = Path(__file__).parent.parent / "app" / "static" / "style.css"


def test_full_width_rule_skips_radios_and_checkboxes():
    # A 100%-wide radio inside a flex label pushed its caption out of the fieldset.
    css = CSS.read_text(encoding="utf-8")
    assert 'input:not([type="checkbox"]):not([type="radio"]) {' in css
    assert 'input:not([type="checkbox"]) {' not in css
    assert 'input[type="radio"]' in css
