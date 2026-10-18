from app.config import BACKUP_RETENTION_DAYS, PROXY_LOG_RETENTION_DAYS, SESSION_TTL
from app.db.base import Base
from app.i18n import LANG_COOKIE, LOCALES, translate

# What /privacy says per table. A new table must be described there before this passes.
DESCRIBED = {
    "users": ("privacy.stored_account", "privacy.stored_profile"),
    "test_scores": ("privacy.stored_result",),
    "dislikes": ("privacy.stored_dislikes",),
    "reactions": ("privacy.stored_reactions",),
    "matches": ("privacy.stored_reactions",),
    "sessions": ("privacy.stored_sessions",),
    "invites": ("privacy.stored_invites",),
}
FORBIDDEN_COLUMNS = {
    "ip",
    "ip_address",
    "email",
    "phone",
    "name",
    "first_name",
    "last_seen",
    "bio",
    "photo",
}


def test_every_table_is_described():
    assert set(Base.metadata.tables) == set(DESCRIBED)


def test_no_forbidden_columns():
    for table in Base.metadata.tables.values():
        assert not {c.name for c in table.c} & FORBIDDEN_COLUMNS, table.name


def test_page_is_public_in_both_languages(client):
    for locale in LOCALES:
        client.cookies.set(LANG_COOKIE, locale)
        page = client.get("/privacy")
        assert page.status_code == 200
        for keys in DESCRIBED.values():
            for key in keys:
                params = {"days": SESSION_TTL.days} if key == "privacy.stored_sessions" else {}
                assert translate(locale, key, **params) in page.text, key
        for key in ("privacy.inference", "privacy.not_stored", "privacy.memory", "consent.admin"):
            assert translate(locale, key) in page.text, key
        assert translate(locale, "privacy.backups", days=BACKUP_RETENTION_DAYS) in page.text
        assert translate(locale, "privacy.logs", days=PROXY_LOG_RETENTION_DAYS) in page.text


def test_numbers_match_configuration():
    assert BACKUP_RETENTION_DAYS == 14  # spec section 3 and 6
    assert PROXY_LOG_RETENTION_DAYS == 7  # spec section 9
    assert "{days}" in translate("en", "privacy.backups", days="{days}")


def test_consent_links_privacy_and_warns_about_inference(client, db):
    from tests.helpers import make_invite, post

    code = make_invite(db)
    page = post(client, "/register", {"step": "code", "invite_code": code}).text
    assert 'href="/privacy"' in page
    assert translate("uk", "consent.inference") in page


def test_footer_links_privacy_everywhere(client):
    assert 'href="/privacy"' in client.get("/login").text
