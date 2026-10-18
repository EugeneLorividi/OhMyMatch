from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from app.config import settings

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.state.settings = settings


@app.get("/", response_class=PlainTextResponse)
def index() -> str:
    return "OhMyMatch: скоро здесь что-то будет"


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
