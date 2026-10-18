def test_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "OhMyMatch" in response.text


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_docs_disabled(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_robots_disallow_all(client):
    assert "Disallow: /" in client.get("/robots.txt").text
