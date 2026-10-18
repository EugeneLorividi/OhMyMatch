# OhMyMatch: rules for Claude Code

Spec: docs/TZ.md (in Russian). It is the source of truth. Follow section 12 stage by stage.

## Workflow
- Work on ONE stage at a time. Run tests and ruff before finishing a stage. Do not start the next stage until tests are green.
- Commit after each stage. Commit messages in English, imperative mood, up to ~50 chars (e.g. "Add FastAPI skeleton").
- Never run `git push` unless the user asks. Never rewrite pushed history.
- Code, comments, identifiers: English. UI texts: Russian.

## Hard rules (privacy, public repo)
- Never commit secrets, .env, keys, dumps, backups, real user data, real bdsmtest screenshots or results. Only .env.example with empty values. OCR fixtures must be synthetic.
- Never log percentages, gender, pairs, request bodies or query strings. Log only event type and request id.
- No third-party scripts, fonts, analytics, trackers, CDNs. No paid APIs, no Claude API: OCR and parsing run locally.
- Never expose other users' percentages, roles or dislikes in any HTML/JSON response.
- No email, phone, name, IP, free text or photos in the database.

## Environment
- Python 3.12, FastAPI, Jinja2 + HTMX, PostgreSQL, SQLAlchemy 2, Alembic, pytest, ruff. Pin versions in a lock file.
- Docker is ROOTLESS under user `ohmymatch`. App container listens only on 127.0.0.1:8000.
- Reverse proxy is the existing system nginx (not Caddy). Its config is managed by root, not by you. Only edit deploy/*.example files in the repo.
- No sudo. Do not touch anything outside ~/ohmymatch and this user's Docker. Other sites and services on this server are off limits.
