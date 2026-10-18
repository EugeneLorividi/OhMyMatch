import re

from app.cli import create_invites
from app.csrf import CSRF_COOKIE

PASSWORD = "correct horse battery"


def csrf(client) -> str:
    if CSRF_COOKIE not in client.cookies:
        client.get("/login")
    return client.cookies[CSRF_COOKIE]


def post(client, url: str, data: dict | None = None, **kwargs):
    return client.post(url, data={"csrf_token": csrf(client), **(data or {})}, **kwargs)


def make_invite(db, ttl_days: int = 7) -> str:
    return create_invites(db, 1, ttl_days)[0]


def handle_from(html: str) -> str:
    return re.search(r'name="handle" value="([^"]+)"', html).group(1)


def recovery_code_from(html: str) -> str:
    return re.search(r'class="code">([A-Z0-9-]+)<', html).group(1)


def register(client, db, password: str = PASSWORD):
    """Full registration. Returns (handle, recovery code, final response)."""
    code = make_invite(db)
    step1 = post(client, "/register", {"step": "code", "invite_code": code})
    handle = handle_from(step1.text)
    done = post(
        client,
        "/register",
        {
            "step": "details",
            "invite_code": code,
            "handle": handle,
            "age_confirmed": "yes",
            "consent": "yes",
            "password": password,
            "password_confirm": password,
        },
    )
    assert done.status_code == 200, done.text
    return handle, recovery_code_from(done.text), done


def full_result_text(values: dict[str, int] | None = None) -> str:
    """Synthetic bdsmtest-like paste with all 25 categories."""
    from app.categories import CATEGORIES

    values = values or {}
    lines = ["== Results from bdsmtest.org ==", "https://bdsmtest.org/r/synthetic"]
    for index, category in enumerate(CATEGORIES):
        lines.append(f"{values.get(category.key, (index * 4) % 101)}% {category.name}")
    return "\n".join(lines)


def score_form(values: dict[str, int | str]) -> dict[str, str]:
    from app.routes.result import FIELD_PREFIX

    return {FIELD_PREFIX + key: str(value) for key, value in values.items()}
