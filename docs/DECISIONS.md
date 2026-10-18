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

## Stage 3: profile and result
- Category slugs: lowercase, spaces and `/` become `-`, parentheses dropped (`rope-bunny`, `master-mistress`, `primal-hunter`).
- `categories.py` also defines the axes and pairs from section 7 and checks at import that every category has exactly one role.
- Text parser uses the spec regex verbatim with `re.ASCII` digits; Unicode spaces, tabs, zero-width chars, full-width `％` and Unicode dashes are normalized first.
- Lines that do not match the regex are ignored (including `100%Switch` without a space); the missing category is then highlighted, so nothing is lost silently.
- Duplicates: always an error and flagged; same value is kept, different values leave the field empty for manual input.
- Aliases are deliberately few (spelling variants of the 25 names); no short forms like `Dom`.
- Paste limited to 20 000 chars; the pasted text is never echoed back or stored.
- `test_scores` CHECK: value is a JSON object and every value is an integer 0..100 (via `jsonb_path_exists`); the set of keys is validated in the app.
- No DB CHECK on gender, seeking or dislike keys: their value sets live in `config.py` / `categories.py` and change without migrations.
- Gender keys `man`, `woman`, `other` (labels in Russian, in `config.GENDERS`); `seeking` needs at least one value.
- `is_active` is recomputed on profile and result save: true when gender, seeking and scores are all present.
- Pages are plain server-rendered forms (no HTMX yet); HTMX gets vendored when the feed needs it.
- The screenshot tab shows a placeholder until stage 4.
- Result pages are sent with `Cache-Control: no-store` because they contain the user's own percentages.

## Stage 4: OCR
- Tesseract 5.5.0 (`tesseract-ocr`, `tesseract-ocr-eng` from Debian trixie) is installed in the app image; apt package versions follow the pinned base image.
- Tesseract is not installed on the host (would need sudo); the full suite runs in the `test` image via `docker compose -f compose.test.yml run --rm tests`. On the host, Tesseract-dependent tests skip; with `REQUIRE_TESSERACT=1` (CI, test image) they fail instead.
- CI installs `tesseract-ocr` from Ubuntu apt on the runner.
- App container runs with `read_only: true` and tmpfs `/tmp`; uploads spooled by Starlette and pytesseract temp files only ever land in tmpfs.
- Images are validated by content with Pillow (JPEG, PNG, WEBP only), max 8 MB and 40 MP, EXIF orientation applied, then rebuilt from raw pixels so no metadata survives.
- Preprocessing: grayscale, upscale x3 (longest side < 1000 px) or x2, capped at 30 MP; invert if mean < 128; OpenCV Gaussian adaptive threshold (block 31, C 15).
- Lines are grouped from `image_to_data` by page/block/paragraph/line; line confidence is the lowest word confidence.
- Name matching: exact or alias first, then rapidfuzz `ratio` over names and aliases. >= 85 is certain; 70..85 is filled but flagged; < 70 is not a category. A runner-up within 5 points also flags.
- Flagged: fuzzy score below 85, ambiguous name, Tesseract confidence below 60, out of range, category name without a percent, conflicting readings, missing.
- Across several screenshots, repeated lines with the same value merge quietly (screenshots overlap); different values keep the more confident one, flag it and report it.
- Concurrency: process-wide semaphore of 2 OCR jobs, wait up to 30 s, then 503. `OMP_THREAD_LIMIT=1` keeps Tesseract from taking every core on the shared VPS.
- Per-user OCR rate limit is deferred to stage 7 with the other limits.
- Body size limit middleware (pure ASGI, outermost): 1 MiB by default, 25 MiB on `/result/parse-image`, same as nginx. Overflow returns 413 even for chunked bodies.
- Wait indicator: tiny same-origin `static/app.js` (shows the indicator, disables submit). No HTMX yet.
- Synthetic OCR fixtures are rendered at test time with Pillow's built-in font; no image files are committed.

## Stage 5: matching
- HTMX 2.0.11 vendored as `static/vendor/htmx-2.0.11.min.js` (from the npm tarball, sha512 integrity verified; sha256 `d6fdc75f...f717`), license alongside. Config: no indicator styles (CSP), no eval, no script tags, same-origin requests only.
- Filters use raw scores; the Switch expansion (step 2) applies only to scoring.
- Gender filter runs in SQL (`gender IN viewer.seeking AND viewer.gender = ANY(seeking)`) and again in Python, so the pure filter stays mutual and testable.
- Curiosity bounds: `CURIOUS_LOW <= lower < ACTIVE_THRESHOLD` and the higher value `>= ACTIVE_THRESHOLD`; the viewer's mode decides both the curiosity zone and the weights, so A's score for B can differ from B's for A (filters stay mutual).
- A pair counts in the role_fit denominator if either person has either side active, using effective (post-Switch) scores.
- Explanation lists only role axes: strict axes first ("совпали по"), then curiosity-only axes ("можно попробовать"), at most 5 in total, ranked by strength then spec order. The style axis is not listed: the spec gives no threshold for it.
- Tie order: SHA-256 of viewer id, UTC date and candidate id. Random, but stable within a day.
- Reaction filters (blocks, likes, passes) are wired through `excluded_ids()`, which returns nothing until the reactions table arrives in stage 6.
- Feed paging uses `?page=N` (1..1000); HTMX requests get the fragment, plain requests the full page. Feed responses are `no-store`.
- The card carries only the handle and axis labels. Like/pass/block buttons come with `POST /react` in stage 6.
- Daily feed page limit (20) is deferred to stage 7 with the other limits.
- Performance check: 1000 active synthetic users, feed built in ~40 ms locally (test asserts < 500 ms, median of 3).
