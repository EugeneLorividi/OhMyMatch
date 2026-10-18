"""End-to-end OCR on synthetic screenshots (section 11): light and dark, two scales."""

import io
import tempfile

import pytest
from PIL import Image

from app.parsing.ocr_parser import ImageRejected, load_image, parse_images
from tests.ocr_fixtures import render, result_lines, sample_values, tesseract  # noqa: F401

pytestmark = pytest.mark.usefixtures("tesseract")


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("scale", [1, 2])
def test_recognizes_at_least_90_percent(theme, scale):
    expected = sample_values()
    result = parse_images([render(result_lines(expected), theme=theme, scale=scale)])
    correct = [key for key, value in expected.items() if result.values.get(key) == value]
    assert len(correct) >= 23, (theme, scale, sorted(set(expected) - set(correct)))
    wrong = {k: v for k, v in result.values.items() if expected[k] != v}
    assert set(wrong) <= result.flagged, wrong


def test_split_across_two_screenshots():
    expected = sample_values()
    keys = list(expected)
    first = {k: expected[k] for k in keys[:15]}
    second = {k: expected[k] for k in keys[12:]}  # overlaps by three lines
    result = parse_images([render(result_lines(first)), render(result_lines(second), theme="dark")])
    correct = [key for key, value in expected.items() if result.values.get(key) == value]
    assert len(correct) >= 23


def test_uncertain_values_are_flagged():
    values = {"rigger": 92, "dominant": 79, "sadist": 40}
    image = render(result_lines(values, names={"rigger": "Rigar"}) + ["Masochist"])
    result = parse_images([image])
    assert result.values.get("dominant") == 79
    assert "rigger" in result.flagged
    assert "masochist" in result.flagged
    assert "dominant" not in result.flagged


def test_jpeg_and_webp(tmp_path):
    expected = sample_values()
    for image_format in ("JPEG", "WEBP"):
        data = render(result_lines(expected), scale=2, image_format=image_format, quality=90)
        result = parse_images([data])
        correct = [key for key, value in expected.items() if result.values.get(key) == value]
        assert len(correct) >= 23, image_format


def test_no_files_left_in_temp_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    parse_images([render(result_lines(sample_values()))])
    assert list(tmp_path.iterdir()) == []


def test_load_image_rejects_without_tesseract():
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, format="GIF")
    with pytest.raises(ImageRejected):
        load_image(gif.getvalue())
