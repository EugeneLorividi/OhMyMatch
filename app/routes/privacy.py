from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.auth import CurrentUser
from app.config import BACKUP_RETENTION_DAYS, PROXY_LOG_RETENTION_DAYS, SESSION_TTL
from app.templating import render

router = APIRouter()


@router.get("/privacy")
def privacy_page(request: Request, user: CurrentUser) -> Response:
    context = {
        "user": user,
        "session_days": SESSION_TTL.days,
        "backup_days": BACKUP_RETENTION_DAYS,
        "log_days": PROXY_LOG_RETENTION_DAYS,
    }
    return render(request, "privacy.html", context)
