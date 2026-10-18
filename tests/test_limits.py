from app.config import MAX_BODY_BYTES
from tests.helpers import csrf


def test_regular_post_body_is_limited(client):
    token = csrf(client)
    response = client.post(
        "/login", data={"csrf_token": token, "handle": "x" * (MAX_BODY_BYTES + 10)}
    )
    assert response.status_code == 413


def test_upload_path_allows_bigger_body(client):
    token = csrf(client)
    # Bigger than the default limit, but CSRF fails later: proves the size gate let it through.
    files = [("images", ("a.png", b"0" * (MAX_BODY_BYTES * 2), "image/png"))]
    response = client.post("/result/parse-image", data={"csrf_token": "x" + token}, files=files)
    assert response.status_code == 403


def test_streamed_body_without_length_is_limited(client):
    csrf(client)

    def chunks():
        for _ in range(3):
            yield b"a" * MAX_BODY_BYTES

    response = client.post(
        "/login",
        content=chunks(),
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 413
