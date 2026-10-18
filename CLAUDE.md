# OhMyMatch: rules for Claude Code

Spec: docs/SPEC.uk.md. It is the source of truth. Follow section 12 stage by stage.

## Workflow
- Work on ONE stage at a time. Run tests and ruff before finishing a stage. Do not start the next stage until tests are green.
- Commit after each stage. Commit messages in English, imperative mood, up to ~50 chars (e.g. "Add FastAPI skeleton").
- Never run `git push` unless the user asks. Never rewrite pushed history.
- Code, comments, identifiers, docs, commit messages and tests: English.
- UI: Ukrainian and English only, through i18n (both languages say the same thing).
- Never write Russian anywhere: code, comments, docs, UI, tests, fixtures, nickname lists.

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

## Autonomy
- Decide routine things yourself: library versions (look them up, never guess), file layout, naming, test design, small refactors, fixing failing tests and lint. Pick the safer, simpler option and note the decision in one line in docs/DECISIONS.md.
- Go through stages 2, 3, 4... in order without waiting for me. After each stage: ruff, pytest and a docker compose check must pass, then commit locally in English. Never push.
- STOP and ask me ONLY if: a stage needs a decision that changes the spec or data model; something must be installed or changed outside ~/ohmymatch; a secret or real user data would be touched; two attempts to fix a failing check did not work; you want to deviate from docs/SPEC.uk.md.
- Never ask for confirmation of things already covered by CLAUDE.md or docs/SPEC.uk.md.
- Stop after the end of stage 5 (matching) and give me a summary: what was done, decisions made, open risks.

## Reports
- After every finished stage or larger task (including the Russian-removal and i18n work), write a report to ~/reports/ (outside the repo, never committed). File names: stage-N.md, or task-<short-name>.md for non-stage work. English only.
- Contents: what was done, decisions made and why, deviations from docs/SPEC.uk.md, test and check results (counts, not full logs), open risks, anything touching privacy or logging, git log --oneline and git diff --stat for the work. Never include secrets, key values or the contents of ~/secrets. Under 150 lines.
- When you stop and wait for me, write the report first.
