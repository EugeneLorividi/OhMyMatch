"""Project rule: no Russian anywhere in the repository (English and Ukrainian only)."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Letters used in Russian but not in Ukrainian (yery, e, hard sign, yo), lower and upper case.
RUSSIAN_ONLY = frozenset(map(chr, (0x44B, 0x44D, 0x44A, 0x451, 0x42B, 0x42D, 0x42A, 0x401)))
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "backups"}


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(  # noqa: S603
            ["git", "ls-files", "-z"],  # noqa: S607
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        return [ROOT / name for name in out.decode().split("\0") if name]
    except (OSError, subprocess.CalledProcessError):
        # No git (test container): walk the tree instead.
        return [
            path
            for path in ROOT.rglob("*")
            if path.is_file() and not SKIP_DIRS & set(path.relative_to(ROOT).parts)
        ]


def test_no_russian_only_letters_in_repository():
    offenders = []
    files = tracked_files()
    assert len(files) > 50
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if RUSSIAN_ONLY & set(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []


def test_guard_detects_russian():
    assert RUSSIAN_ONLY & {chr(0x432), chr(0x44B)}  # a two-letter Russian word with yery
    assert not RUSSIAN_ONLY & set("їєґі")  # Ukrainian ї є ґ і
