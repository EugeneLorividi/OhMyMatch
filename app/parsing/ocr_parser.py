"""Screenshot OCR (section 5.2). Images stay in memory; nothing is written outside tmpfs."""

import io
import threading
from collections.abc import Iterable
from dataclasses import dataclass

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageOps, UnidentifiedImageError
from rapidfuzz import fuzz, process

from app.categories import ALIASES, CATEGORIES, CATEGORY_BY_KEY
from app.config import (
    OCR_CONCURRENCY,
    OCR_FORMATS,
    OCR_FUZZY_FLOOR,
    OCR_FUZZY_MARGIN,
    OCR_FUZZY_THRESHOLD,
    OCR_MAX_FILE_BYTES,
    OCR_MAX_INPUT_PIXELS,
    OCR_MAX_WORK_PIXELS,
    OCR_MIN_CONFIDENCE,
    OCR_TESSERACT_TIMEOUT_SECONDS,
)
from app.parsing.text_parser import ParseResult, normalize_name, split_line

# At most OCR_CONCURRENCY recognitions at once, process-wide.
slots = threading.BoundedSemaphore(OCR_CONCURRENCY)

_CHOICES: dict[str, str] = {normalize_name(c.name): c.key for c in CATEGORIES} | ALIASES


class ImageRejected(ValueError):
    """The upload is not an acceptable image. The message is shown to the user."""


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float  # lowest word confidence on the line, 0..100


@dataclass(frozen=True)
class NameMatch:
    key: str
    score: float
    ambiguous: bool

    @property
    def certain(self) -> bool:
        return self.score >= OCR_FUZZY_THRESHOLD and not self.ambiguous


def fuzzy_match(name: str) -> NameMatch | None:
    normalized = normalize_name(name)
    if normalized in _CHOICES:
        return NameMatch(_CHOICES[normalized], 100.0, False)
    candidates = process.extract(normalized, list(_CHOICES), scorer=fuzz.ratio, limit=10)
    best_by_key: dict[str, float] = {}
    for choice, score, _ in candidates:
        key = _CHOICES[choice]
        best_by_key[key] = max(best_by_key.get(key, 0.0), score)
    ranked = sorted(best_by_key.items(), key=lambda item: item[1], reverse=True)
    if not ranked or ranked[0][1] < OCR_FUZZY_FLOOR:
        return None
    key, score = ranked[0]
    ambiguous = len(ranked) > 1 and score - ranked[1][1] < OCR_FUZZY_MARGIN
    return NameMatch(key, score, ambiguous)


def load_image(data: bytes) -> Image.Image:
    """Validates an upload and returns an RGB copy without EXIF or other metadata."""
    if len(data) > OCR_MAX_FILE_BYTES:
        raise ImageRejected("Файл больше 8 МБ.")
    try:
        image = Image.open(io.BytesIO(data))
        image_format = image.format
        if image_format not in OCR_FORMATS:
            raise ImageRejected("Поддерживаются только jpeg, png и webp.")
        if image.width * image.height > OCR_MAX_INPUT_PIXELS:
            raise ImageRejected("Изображение слишком большое.")
        image = ImageOps.exif_transpose(image)
        pixels = image.convert("RGB")
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise ImageRejected("Не удалось открыть изображение.") from exc
    # Rebuild from raw pixels so no metadata survives.
    return Image.frombytes("RGB", pixels.size, pixels.tobytes())


def preprocess(image: Image.Image) -> np.ndarray:
    gray = np.asarray(image.convert("L"))
    height, width = gray.shape
    scale = 3 if max(height, width) < 1000 else 2
    while scale > 1 and height * width * scale * scale > OCR_MAX_WORK_PIXELS:
        scale -= 1
    if scale > 1:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    if gray.mean() < 128:  # dark theme
        gray = 255 - gray
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )


_LINE_FIELDS = ("page_num", "block_num", "par_num", "line_num")


def recognize_lines(binary: np.ndarray) -> list[OcrLine]:
    data = pytesseract.image_to_data(
        Image.fromarray(binary),
        lang="eng",
        config="--psm 6",
        output_type=pytesseract.Output.DICT,
        timeout=OCR_TESSERACT_TIMEOUT_SECONDS,
    )
    lines: dict[tuple[int, ...], list[tuple[str, float]]] = {}
    for i, word in enumerate(data["text"]):
        word = word.strip()
        confidence = float(data["conf"][i])
        if not word or confidence < 0:
            continue
        line_id = tuple(data[field][i] for field in _LINE_FIELDS)
        lines.setdefault(line_id, []).append((word, confidence))
    return [
        OcrLine(" ".join(w for w, _ in words), min(c for _, c in words))
        for _, words in sorted(lines.items())
    ]


@dataclass
class _Candidate:
    percent: int
    confidence: float
    uncertain: bool


def parse_lines(lines: Iterable[OcrLine]) -> ParseResult:
    result = ParseResult()
    found: dict[str, _Candidate] = {}
    unpaired: set[str] = set()
    for line in lines:
        parts = split_line(line.text)
        if parts is None:
            match = fuzzy_match(line.text)
            if match is not None and match.certain:
                unpaired.add(match.key)
            continue
        percent, name = parts
        match = fuzzy_match(name)
        if match is None:
            result.errors.append(f"Не удалось распознать категорию «{name}».")
            continue
        label = CATEGORY_BY_KEY[match.key].name
        if not 0 <= percent <= 100:
            result.errors.append(f"{label}: распознано {percent}%, это вне диапазона 0–100.")
            result.flagged.add(match.key)
            continue
        uncertain = not match.certain or line.confidence < OCR_MIN_CONFIDENCE
        candidate = _Candidate(percent, line.confidence, uncertain)
        previous = found.get(match.key)
        if previous is None:
            found[match.key] = candidate
        elif previous.percent == percent:
            # Overlapping screenshots repeat lines; keep the more certain reading.
            if previous.uncertain and not uncertain:
                found[match.key] = candidate
        else:
            result.errors.append(
                f"{label}: распознано по-разному ({previous.percent}% и {percent}%)."
            )
            result.flagged.add(match.key)
            if candidate.confidence > previous.confidence:
                found[match.key] = candidate
    for key, candidate in found.items():
        result.values[key] = candidate.percent
        if candidate.uncertain:
            result.flagged.add(key)
    result.flagged.update(unpaired - set(found))
    result.flagged.update(result.missing)
    return result


def parse_images(blobs: list[bytes]) -> ParseResult:
    """Validates all images first, then recognizes them. Raises ImageRejected."""
    images = [load_image(blob) for blob in blobs]
    lines: list[OcrLine] = []
    for image in images:
        lines.extend(recognize_lines(preprocess(image)))
    return parse_lines(lines)
