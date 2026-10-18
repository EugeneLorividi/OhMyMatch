# OhMyMatch

Invite-only web app that matches members of one community by their bdsmtest.org results.
Pseudonymous by design: it stores only what matching and login need. The full spec is in
[`docs/SPEC.uk.md`](docs/SPEC.uk.md) (Ukrainian); implementation decisions are in [`docs/DECISIONS.md`](docs/DECISIONS.md).

License: AGPL-3.0 (see `LICENSE`).

## Languages
- UI: Ukrainian (default) and English. All UI strings are in `app/locales/uk.json` and `app/locales/en.json`; both files must have the same keys.
- `docs/SPEC.uk.md` is the spec and the source of truth, written in Ukrainian; if the spec changes, change only that file.
- Every other doc, this README, code, comments, tests and commit messages: English.
- No Russian anywhere in the repository; `tests/test_no_russian.py` guards this.

## Stack
Python 3.12, FastAPI, Jinja2 + HTMX (self-hosted), PostgreSQL 17, SQLAlchemy 2, Alembic,
argon2id, Tesseract OCR (local, English data), pytest, ruff, uv. Runs in rootless Docker
Compose behind the system nginx.

## Privacy rules (short)
- No email, phone, name, IP, free text or photos in the database. Screenshots and pasted text are never stored.
- Other users see only a nickname and the names of matching axes; never percentages, roles or "no" lists.
- Logs carry no percentages, gender, pairs, request bodies or query strings; the access log is off.
- No third-party scripts, fonts, analytics or CDNs; no paid or external APIs.

## Development
Secrets live outside the repo in `~/secrets/ohmymatch.env` (mode 600); `.env.example` lists the keys.

```sh
python3.12 -m venv .venv && .venv/bin/pip install uv
.venv/bin/uv sync                              # dependencies from uv.lock
docker compose up -d --build                   # app on 127.0.0.1:8000, db on an internal network
docker compose run --rm app alembic upgrade head
docker compose run --rm app python -m app.cli invite --count 1 --ttl-days 7
```

## Tests
The full suite needs PostgreSQL and Tesseract and runs in a container:

```sh
docker compose -f compose.test.yml run --rm --build tests
```

On the host (OCR image tests are skipped without Tesseract):

```sh
docker compose -f compose.test.yml up -d testdb
TEST_DATABASE_URL=postgresql+psycopg://test:test@127.0.0.1:55432/test .venv/bin/uv run pytest
.venv/bin/uv run ruff check . && .venv/bin/uv run ruff format --check .
```

All test data is synthetic. Never add real results, screenshots or user data.

## Deployment
nginx config is managed outside the repo; `deploy/*.example` are the reference files.
See section 3 of the spec for the VPS checklist. nginx must overwrite `X-Forwarded-For` with
`$remote_addr` (as in the example): the app uses it for per-IP rate limits.

## Backups
Encrypted with [age](https://age-encryption.org) on the server; no plaintext dump touches the disk.

```sh
# Once, on a machine you trust (not the server): create the key pair, keep identity.txt offline.
age-keygen -o identity.txt && age-keygen -y identity.txt > backup-recipients.txt
# On the server: only the public key.
install -m 600 backup-recipients.txt ~/secrets/backup-recipients.txt
mkdir -m 700 -p ~/ohmymatch/backups

# Backup (e.g. daily from cron); deletes copies older than 14 days.
docker compose --profile ops run --rm backup

# Restore into the running database (brings the private key in for this one run only).
docker compose --profile ops run --rm -v /path/to/identity.txt:/keys/identity.txt:ro \
  backup restore.sh /backups/ohmymatch-<stamp>.dump.age
```

## Extra checks (Docker, synthetic data only)
- `deploy/backup/restore-test.sh`: backup, rotation and restore round trip with a throwaway key.
- `tests/proxy/run.sh`: per-IP rate limits behind a real nginx with `X-Forwarded-For`.
