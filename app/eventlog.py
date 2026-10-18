"""Application log: only an event type and a random request id (section 9). Nothing else."""

import logging
import re
import sys

from fastapi import Request

_EVENT_RE = re.compile(r"[a-z_.]+")

logger = logging.getLogger("ohmymatch")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def log_event(event: str, request_id: str) -> None:
    if not _EVENT_RE.fullmatch(event):
        raise ValueError("event types are fixed identifiers, never data")
    logger.info("event=%s request_id=%s", event, request_id)


def event(request: Request, name: str) -> None:
    log_event(name, request_id_of(request))
