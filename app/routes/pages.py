from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response

from app.auth import CurrentUser
from app.templating import render

router = APIRouter()


@router.get("/")
def index(request: Request, user: CurrentUser) -> Response:
    return render(request, "index.html", {"user": user})


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots() -> str:
    return "User-agent: *\nDisallow: /\n"
