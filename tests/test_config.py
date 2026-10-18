import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize("value", [None, "", "x" * 31])
def test_secret_key_rejected(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("SECRET_KEY", value)
    with pytest.raises(ValidationError):
        Settings()


def test_secret_key_accepted(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    assert Settings().secret_key == "x" * 32


@pytest.mark.parametrize("value", [None, "", "x" * 31])
def test_app_fails_to_start_without_valid_secret_key(value):
    env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY"}
    if value is not None:
        env["SECRET_KEY"] = value
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", "import app.main"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "secret_key" in result.stderr
