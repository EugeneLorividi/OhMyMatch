import pytest
from fastapi.routing import APIRoute

from app.csrf import CSRF_COOKIE, CSRF_HEADER, verify_csrf
from app.main import ROUTERS, app
from tests.helpers import csrf, make_invite

POST_PATHS = sorted(
    route.path
    for router in ROUTERS
    for route in router.routes
    if isinstance(route, APIRoute) and "POST" in route.methods
)


def test_post_routes_exist():
    assert {"/register", "/login", "/logout", "/recover"} <= set(POST_PATHS)


def test_csrf_dependency_is_global():
    assert any(dep.dependency is verify_csrf for dep in app.router.dependencies)


@pytest.mark.parametrize("path", POST_PATHS)
def test_post_without_token_is_rejected(client, path):
    csrf(client)
    assert client.post(path, data={}).status_code == 403


@pytest.mark.parametrize("path", POST_PATHS)
def test_post_with_wrong_token_is_rejected(client, path):
    csrf(client)
    assert client.post(path, data={"csrf_token": "wrong"}).status_code == 403


def test_post_without_cookie_is_rejected(client):
    token = csrf(client)
    client.cookies.clear()
    assert client.post("/login", data={"csrf_token": token}).status_code == 403


def test_header_token_is_accepted(client, db):
    code = make_invite(db)
    response = client.post(
        "/register",
        data={"step": "code", "invite_code": code},
        headers={CSRF_HEADER: csrf(client)},
    )
    assert response.status_code == 200


def test_csrf_cookie_flags(client):
    response = client.get("/login")
    cookie = response.headers["set-cookie"].lower()
    assert cookie.startswith(CSRF_COOKIE.lower())
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie
