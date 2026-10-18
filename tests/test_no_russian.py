"""Project rule: no Russian anywhere in the repository.

Cyrillic is allowed only where Ukrainian belongs (the spec, the Ukrainian locale, test
strings, and the language switch label in en.json). Everywhere, including those files,
Russian-only letters and common Russian-only words fail the build. Every Russian letter and
word below is built from code points so this file never contains them literally.
"""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THIS = Path(__file__).resolve()
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "backups"}
SKIP_FILES = {"uv.lock"}

# Letters used in Russian but not in Ukrainian (yery, e, hard sign, yo), lower and upper case.
RUSSIAN_ONLY = frozenset(map(chr, (0x44B, 0x44D, 0x44A, 0x451, 0x42B, 0x42D, 0x42A, 0x401)))

# Common Russian words that are not Ukrainian words: the conjunction "and", "what", "so that",
# "this", "how", "if", "only", "need" (two forms), "when", "where", "here", "now", "too",
# "also", "or", "no", "she", "they", "his", "is/there is", "still", "why", "thanks", "please".
RUSSIAN_WORDS = frozenset(
    "".join(map(chr, codes))
    for codes in (
        (0x438,),
        (0x447, 0x442, 0x43E),
        (0x447, 0x442, 0x43E, 0x431, 0x44B),
        (0x44D, 0x442, 0x43E),
        (0x43A, 0x430, 0x43A),
        (0x435, 0x441, 0x43B, 0x438),
        (0x442, 0x43E, 0x43B, 0x44C, 0x43A, 0x43E),
        (0x43D, 0x443, 0x436, 0x43D, 0x43E),
        (0x43D, 0x430, 0x434, 0x43E),
        (0x43A, 0x43E, 0x433, 0x434, 0x430),
        (0x433, 0x434, 0x435),
        (0x437, 0x434, 0x435, 0x441, 0x44C),
        (0x441, 0x435, 0x439, 0x447, 0x430, 0x441),
        (0x442, 0x43E, 0x436, 0x435),
        (0x442, 0x430, 0x43A, 0x436, 0x435),
        (0x438, 0x43B, 0x438),
        (0x43D, 0x435, 0x442),
        (0x43E, 0x43D, 0x430),
        (0x43E, 0x43D, 0x438),
        (0x435, 0x433, 0x43E),
        (0x435, 0x441, 0x442, 0x44C),
        (0x435, 0x449, 0x435),
        (0x43F, 0x43E, 0x447, 0x435, 0x43C, 0x443),
        (0x441, 0x43F, 0x430, 0x441, 0x438, 0x431, 0x43E),
        (0x43F, 0x43E, 0x436, 0x430, 0x43B, 0x443, 0x439, 0x441, 0x442, 0x430),
    )
)
CONJUNCTION_AND = chr(0x438)

CYRILLIC = re.compile(r"[Ѐ-ӿ]")
# A Cyrillic word, apostrophes inside it included (Ukrainian uses them, e.g. "m'iaso").
WORD = re.compile(r"[Ѐ-ӿ]+(?:[’ʼ'][Ѐ-ӿ]+)*")

ALLOWED_CYRILLIC = {"docs/SPEC.uk.md", "app/locales/uk.json"}


def repo_files() -> list[Path]:
    try:
        out = subprocess.run(  # noqa: S603
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],  # noqa: S607
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        paths = [ROOT / name for name in out.decode().split("\0") if name]
    except (OSError, subprocess.CalledProcessError):
        # No git (test container): walk the tree instead.
        paths = [
            path
            for path in ROOT.rglob("*")
            if path.is_file() and not SKIP_DIRS & set(path.relative_to(ROOT).parts)
        ]
    return [path for path in paths if path.name not in SKIP_FILES and path.exists()]


def texts() -> dict[str, str]:
    found = {}
    for path in repo_files():
        try:
            found[path.relative_to(ROOT).as_posix()] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return found


def russian_words(text: str) -> set[str]:
    return {
        word for word in (m.group(0).lower() for m in WORD.finditer(text)) if word in RUSSIAN_WORDS
    }


def test_files_are_found():
    assert len(texts()) > 50


def test_no_russian_only_letters_anywhere():
    offenders = []
    for name, text in texts().items():
        if Path(ROOT / name).resolve() == THIS:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if RUSSIAN_ONLY & set(line):
                offenders.append(f"{name}:{number}")
    assert offenders == []


def test_no_russian_words_anywhere():
    offenders = []
    for name, text in texts().items():
        if Path(ROOT / name).resolve() == THIS:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if words := russian_words(line):
                offenders.append(f"{name}:{number}: {len(words)} word(s)")
    assert offenders == []


def test_cyrillic_only_where_ukrainian_belongs():
    offenders = []
    for name, text in texts().items():
        if name in ALLOWED_CYRILLIC or name.startswith("tests/") or not CYRILLIC.search(text):
            continue
        if name == "app/locales/en.json":
            data = json.loads(text)
            # The language switch names Ukrainian in Ukrainian; nothing else may be Cyrillic.
            if [key for key, value in data.items() if CYRILLIC.search(value)] == ["lang.switch"]:
                continue
        offenders.append(name)
    assert offenders == []


def test_no_standalone_russian_and_in_locale_and_spec():
    uk = json.loads((ROOT / "app/locales/uk.json").read_text(encoding="utf-8"))
    for key, value in uk.items():
        assert CONJUNCTION_AND not in {m.group(0).lower() for m in WORD.finditer(value)}, key
    spec = (ROOT / "docs/SPEC.uk.md").read_text(encoding="utf-8")
    assert CONJUNCTION_AND not in {m.group(0).lower() for m in WORD.finditer(spec)}


def test_guard_detects_russian_and_accepts_ukrainian():
    russian = " ".join(
        "".join(map(chr, codes))
        for codes in ((0x44D, 0x442, 0x43E), (0x438,), (0x447, 0x442, 0x43E))
    )  # "this", "and", "what"
    assert RUSSIAN_ONLY & set(russian)
    assert russian_words(russian) == {
        chr(0x438),
        "".join(map(chr, (0x447, 0x442, 0x43E))),
        "".join(map(chr, (0x44D, 0x442, 0x43E))),
    }
    russian_without_letters = "".join(map(chr, (0x43A, 0x430, 0x43A)))  # "how", no telltale letter
    assert not RUSSIAN_ONLY & set(russian_without_letters)
    assert russian_words(russian_without_letters)
    ukrainian = "Що це таке й навіщо? Лише те, що потрібно, і коли треба, пам’ять."
    assert not RUSSIAN_ONLY & set(ukrainian)
    assert russian_words(ukrainian) == set()


def test_word_list_is_not_ukrainian():
    uk = json.loads((ROOT / "app/locales/uk.json").read_text(encoding="utf-8"))
    vocabulary = {m.group(0).lower() for value in uk.values() for m in WORD.finditer(value)}
    spec = (ROOT / "docs/SPEC.uk.md").read_text(encoding="utf-8")
    vocabulary |= {m.group(0).lower() for m in WORD.finditer(spec)}
    assert len(vocabulary) > 500
    assert not RUSSIAN_WORDS & vocabulary
