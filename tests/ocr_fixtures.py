"""Synthetic screenshots for OCR tests. Generated at test time, never from real results."""

import io
import os
import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.categories import CATEGORIES

THEMES = {"light": ("#ffffff", "#1f1f1f"), "dark": ("#1c1c1e", "#e8e8e8")}


def sample_values() -> dict[str, int]:
    return {c.key: (i * 37 + 11) % 101 for i, c in enumerate(CATEGORIES)}


def render(
    lines: list[str], *, theme: str = "light", scale: int = 1, image_format: str = "PNG", **save
) -> bytes:
    background, foreground = THEMES[theme]
    font = ImageFont.load_default(size=18 * scale)
    line_height = 30 * scale
    margin = 24 * scale
    image = Image.new("RGB", (560 * scale, margin * 2 + line_height * len(lines)), background)
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((margin, margin + index * line_height), line, font=font, fill=foreground)
    buffer = io.BytesIO()
    image.save(buffer, format=image_format, **save)
    return buffer.getvalue()


def result_lines(values: dict[str, int], names: dict[str, str] | None = None) -> list[str]:
    names = names or {}
    lines = ["== Results from bdsmtest.org ==", "bdsmtest.org/r/synthetic"]
    for category in CATEGORIES:
        if category.key in values:
            lines.append(f"{values[category.key]}% {names.get(category.key, category.name)}")
    return lines


@pytest.fixture
def tesseract():
    if shutil.which("tesseract") is None:
        if os.environ.get("REQUIRE_TESSERACT"):
            pytest.fail("Tesseract is required (REQUIRE_TESSERACT is set) but not installed")
        pytest.skip("Tesseract is not installed; run the suite via compose.test.yml")
