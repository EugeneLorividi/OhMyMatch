# Decisions

One line per decision. Newest at the bottom of each stage.

## Stage 1: skeleton
- Dependencies managed with uv; `uv.lock` is the lock file.
- Images pinned by exact tag including OS: `postgres:17.11-alpine3.24`, `python:3.12.15-slim-trixie`, `ghcr.io/astral-sh/uv:0.13.1`.
- Secrets live in `~/secrets/ohmymatch.env` (chmod 600, outside the repo); only `.env.example` is committed.
- uvicorn runs with `--no-access-log` (access log would contain query strings and client IPs).
- FastAPI `/docs`, `/redoc` and `/openapi.json` are disabled.
- CI actions pinned by commit SHA, `permissions: contents: read`, `persist-credentials: false`.
- `SECRET_KEY` is required, at least 32 chars; validation errors hide the input value.
- Kept `httpx` (not `httpx2`) for the test client; the Starlette deprecation warning is accepted for now.

## Stage 2: access
- Owner decision: added `users.recovery_code_hash` (argon2id); not in the section 6 field list but required by sections 4 and 9.
- Owner decision: added `GET, POST /recover` (handle + recovery code + new password; issues a new code, wipes all sessions).
- Owner decision: added `users.is_active` (default false; set in stage 3 once profile and scores are complete), matching the section 6 index.
- `users.gender` and `users.seeking` are nullable: they are filled on the profile page after registration.
- Session cookie holds a random token; `sessions.id` is a UUID built from its SHA-256, so a DB leak does not leak live tokens.
- Session lifetime is 7 days (`SESSION_TTL`); expired sessions are deleted on access and on login.
- Cookies use the `__Host-` prefix: Secure, HttpOnly, SameSite=Lax, Path=/.
- CSRF: double-submit token in a `__Host-csrf` cookie, checked by an app-wide dependency on every non-GET request; accepted from form field `csrf_token` or header `X-CSRF-Token` (HTMX via `hx-headers` on `<body>`). Rotated on login, logout, registration and recovery.
- Invite and recovery codes: 16 chars from a 30-char unambiguous alphabet (~78 bits), shown as `XXXX-XXXX-XXXX-XXXX`, case/dash insensitive.
- Invite codes are stored as SHA-256 (high entropy, looked up by hash); passwords and recovery codes as argon2id.
- Handles are `adjective-noun-NN` from fixed word lists; the server only accepts strings that match the generator, so no free text gets in.
- Registration is two steps: invite code, then 18+, consent, handle, password; the invite is re-checked under `SELECT ... FOR UPDATE` at the final step.
- Password length 10 to 128 chars, no other composition rules.
- Login and recovery errors are identical for unknown handles and wrong secrets; a dummy argon2 verify keeps timing similar.
- `CONSENT_VERSION = "2026-10-18"`; consent text lives in `templates/_consent.html` and will be reused by `/privacy` in stage 7.
- Password change (`POST /account/password`) is deferred to stage 7 together with account deletion on the settings page.
- Rate limits for login, registration and recovery are deferred to stage 7 as the spec plans.
- Tests run against real PostgreSQL: `compose.test.yml` (tmpfs, 127.0.0.1:55432, synthetic credentials) locally, a service container in CI. Tests refuse to run without `TEST_DATABASE_URL`.
- `/robots.txt` disallows all crawling.
