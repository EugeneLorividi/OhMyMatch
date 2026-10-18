from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "OhMyMatch" in response.text


def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_docs_disabled():
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
