# Spec: OhMyMatch MVP (web, no Telegram)

Oct 18, 2026 · @Lorividi

Translated from the original spec (formerly `docs/TZ.md`, see git history); section numbering and meaning are unchanged.

## 1. Goal and context

OhMyMatch is a closed web app that matches people from one community with each other based on their bdsmtest.org results. This version of the spec covers only the web part; the Telegram bot and contact between people are a separate spec.

- **Audience:** a closed community, on the order of hundreds of users, all 18+.
- **No test of our own.** A person takes bdsmtest.org and brings the result: pastes the text of the list or uploads a screenshot.
- **Highly sensitive data.** Gender, orientation and intimate preferences are special-category personal data. The app is pseudonymous, not anonymous, and says so honestly on the "what we store" page.
- **Principle:** store only what matching cannot work without. No screenshots on disk, no original pasted text, no email, phones, photos, bio or free text.
- **No paid APIs.** OCR and parsing run locally, with no calls to the Claude API or external services.

## 2. MVP scope

The first version covers the full path from registration to a mutual match, without Telegram. Everything left out is postponed explicitly, and the data model leaves room and stubs for it.

**In scope:**

- registration by invite, 18+ confirmation, consent;
- profile: "who I am", "who I am looking for", search mode;
- entering the test result: pasting text and recognising a screenshot, with mandatory confirmation;
- the "no" list (what I definitely do not want);
- matching: hard filters, normal and experimental modes, explanation of the match;
- likes, skip, block, mutual match;
- account deletion, "what we store" page.

**Postponed (not doing now):**

| What | Why postponed | Groundwork in MVP |
| --- | --- | --- |
| Telegram bot and contact | separate spec | ContactGateway interface with an empty implementation |
| Verifying members | separate decision | invite codes via CLI |
| "By point" mode (a sub looks for a dominant, etc.) | refined after launch | nullable field focus in users, no logic |
| "How did it go" loop after contact | needs contact through the bot | no table is created, described in section 6 |
| Legal review | owner's decision | "what we store" page, versioned consent |

## 3. Stack, repository and deployment

We write in Python (FastAPI) with PostgreSQL; the front end is server-side templates with HTMX; everything runs in Docker Compose on the existing VPS under a separate user. Use current stable library versions and pin them in a lock file.

| Layer | Choice |
| --- | --- |
| Language and web | Python 3.12, FastAPI, Jinja2 + HTMX, no SPA |
| Database | PostgreSQL, SQLAlchemy 2, Alembic migrations |
| Passwords and sessions | argon2id, server-side sessions in the DB, CSRF tokens on every POST |
| OCR | Tesseract (pytesseract), Pillow/OpenCV for preprocessing, rapidfuzz for fuzzy name matching |
| Proxy | nginx (already on the server), HTTPS via certbot (Let's Encrypt) |
| Tests and lint | pytest, ruff |

**Repository layout:**

```text
ohmymatch/
  app/
    main.py            # FastAPI, routes
    config.py          # matching thresholds and weights, limits
    categories.py      # 25 categories, axes, pairs
    parsing/           # text_parser.py, ocr_parser.py
    matching/          # filters.py, scoring.py, explain.py
    contact/           # ContactGateway (stub)
    models/, db/, templates/, static/
    cli.py             # creating invites
  migrations/
  tests/
  docker-compose.yml
  deploy/nginx.conf.example
  .env.example
```

**Deployment and isolation (VPS checklist):**

- a separate unix user without sudo, a separate Postgres user with access only to its own database;
- rootless containers, own Docker network, the app listens only on `127.0.0.1:8000`, nginx exposes it on 80/443 (set up separately from the project, certificate via certbot);
- firewall: 80, 443 and SSH open, SSH login by key only, fail2ban;
- a proper domain instead of DuckDNS, HTTPS mandatory, HSTS enabled;
- secrets (session key, tokens) only in `.env` with mode 600 outside the repository;
- backups are encrypted on the server before being sent anywhere (age or gpg), the key is stored separately from the copies, rotation no longer than 14 days.

## 4. User scenarios

The user goes through seven steps from invite to match, and at no step enters anything other than choices from lists, numbers and a password.

1. **Sign-up by invite.** Enter the code, then the "I am 18+" screen and consent to the "what we store" text. The system offers a neutral nickname from a generator (can be regenerated); the user sets a password. A recovery code is shown once.
2. **Profile.** "Who I am" (one option), "who I am looking for" (multiple choice), search mode: normal or experimental.
3. **Test result.** Two tabs: "Paste text" and "Upload screenshot". Either way leads to the same form of 25 fields filled with the recognised values. The user fixes errors and confirms. Details in section 5.
4. **"No" list.** Multiple choice from the 25 categories: what the user definitely does not want in a partner.
5. **Feed.** Top candidates with a short caption "matched on: …" and buttons "like", "skip", "don't show again".
6. **Mutual like.** Both see the match in the "Matches" section. In the MVP the contact button shows a stub "contact will open via the bot".
7. **Settings.** Change mode and "who I am looking for", re-upload the result, edit the "no" list, delete the account.

## 5. Entering test results

Both input methods (pasting text and a screenshot) give the same result: a dictionary of 25 categories with integer percentages 0–100, which the user confirms on the form. Only these 25 numbers are written to the database; the text, screenshot and link are not stored.

**Canonical category list** (store keys in lowercase, as slugs): Switch, Vanilla, Rigger, Non-monogamist, Rope bunny, Dominant, Submissive, Voyeur, Exhibitionist, Experimentalist, Pet, Brat, Owner, Brat tamer, Master/Mistress, Sadist, Slave, Degrader, Masochist, Daddy/Mommy, Primal (Hunter), Degradee, Ageplayer, Little, Primal (Prey). The list lives in `categories.py`, not scattered across the code.

### 5.1. Pasting text (main method)

Format: a line `N% Name`. Other lines (link, heading) are ignored.

```text
100% Switch
92% Rigger
79% Dominant
```

- A line is parsed with a regular expression like `^\s*(\d{1,3})\s*%\s+(.+?)\s*$`; whitespace and case are normalised, Unicode spaces and NBSP count as ordinary spaces.
- The name is matched against the whitelist by exact match, then through an alias dictionary.
- A percentage outside 0–100, an unknown category, a duplicate: an error with a clear text; nothing is lost silently.
- If not all 25 categories are found, the form opens with the values found, and the missing fields are highlighted for manual input.
- The app neither opens nor stores the result link (`bdsmtest.org/r/...`): the page is rendered by JavaScript, and scraping someone else's site is not needed.

### 5.2. Screenshot (OCR)

Warning above the form, mandatory: "Recognition is inaccurate. Check the numbers before saving."

- **Limits:** up to 3 images, up to 8 MB each, jpeg/png/webp. Strip EXIF.
- **Preprocessing:** convert to grayscale, upscale 2–3x, auto-invert dark theme (mean brightness below half), adaptive binarisation.
- **Recognition:** Tesseract, `--psm 6` mode, output through `image_to_data` with words grouped into lines. Each line goes through the same parsing as the text in 5.1.
- **Names:** fuzzy matching against the whitelist via rapidfuzz, match threshold no lower than 85. Anything below the threshold is marked as uncertain.
- **Uncertain values** (low Tesseract confidence, number out of range, unpaired category) are highlighted in the form.
- **Nothing is written to disk.** pytesseract creates temporary files, so the container's `/tmp` is mounted as tmpfs, and the file is deleted right after recognition. The image lives only in the request's memory.
- **Load:** no more than two OCR jobs at once, a per-user request limit, a wait indicator on the page.

OCR test fixtures are generated synthetically (PNG from text in light and dark theme, two scales); real results of people are not put in the repository.

## 6. Data model

The schema consists of six main tables and a sessions table; all identifiers are random UUIDs (no sequential ids), and all relations to `users` are deleted by cascade. Exactly what is needed for matching and login is stored.

| Table | Fields | Notes |
| --- | --- | --- |
| users | id, handle (unique neutral nickname), password\_hash, gender, seeking (set of values), mode (normal or experimental), focus (nullable, groundwork), consent\_version, consent\_at, age\_confirmed\_at, created\_at | no email, phone, name, IP, last\_seen |
| invites | id, code\_hash, expires\_at, used\_by (nullable), used\_at | codes stored only as a hash |
| test\_scores | user\_id (PK, FK), scores (jsonb: category key → 0–100), updated\_at | key set validated in the app and a CHECK on the range |
| dislikes | user\_id, category\_key | PK from both fields |
| reactions | from\_user, to\_user, kind (like, pass, block), created\_at | PK from the from and to pair |
| matches | user\_a, user\_b, created\_at | user\_a less than user\_b, unique pair, created in the same transaction as the second like |

**Indexes:** users(is\_active, gender), reactions(to\_user).

**Sessions:** a separate sessions table (id, user\_id, expires\_at), lifetime limited, all sessions are wiped on password change and account deletion.

**Values of gender and seeking:** the set of options is defined in config (at least: man, woman, other). Orientation is not stored as a separate field; it is derived from the pair "who I am" and "who I am looking for".

**Deletion:** hard, no soft delete. `DELETE FROM users` removes rows in all tables by cascade. In backups the data disappears by rotation (no longer than 14 days); this is stated plainly on the "what we store" page.

**Phase 2 (do not create migrations now):** match\_feedback (match\_id, user\_id, rating: fire, ok, miss), contact via Telegram (a separate table without a foreign key to the profile, encrypted identifiers, schema in a separate spec).

## 7. Matching algorithm

The feed is built on the fly: SQL selects candidates by gender, Python applies the remaining filters and computes the score, and finished pairs are not stored in advance. All thresholds and weights live in `config.py` and change without migrations.

**Starting parameters** (we tune them by experience; these are hypotheses, not science):

| Parameter | Value | Meaning |
| --- | --- | --- |
| ACTIVE\_THRESHOLD | 65 | percentage from which an interest counts as "really want" |
| CURIOUS\_LOW | 30 | lower bound of the curiosity zone |
| CURIOUS\_FACTOR | 0.5 | how many times less "could try" weighs than "want" |
| NONMONO\_LOW | 35 | "don't want" bound for Non-monogamist |
| WEIGHT\_ROLES / WEIGHT\_STYLE (normal) | 0.75 / 0.25 | contribution of the role and style parts |
| WEIGHT\_ROLES / WEIGHT\_STYLE (experimental) | 0.6 / 0.4 | the same for the experimental mode |
| FEED\_PAGE\_SIZE | 20 | feed page size |

### Step 1. Hard filters (mutual)

A candidate gets into the feed only if all conditions hold:

1. both accounts are active, and the candidate is not the user;
2. there is no block reaction between them in either direction, and the user has not yet given the candidate a like or pass;
3. the candidate's gender is in the user's "who I am looking for", and vice versa;
4. Non-monogamist: excluded if one has a value no lower than ACTIVE\_THRESHOLD and the other no higher than NONMONO\_LOW;
5. "no" list: none of the candidate's active categories (no lower than ACTIVE\_THRESHOLD) is in the user's "no" list, and vice versa.

### Step 2. Effective profile

If a person has Switch no lower than ACTIVE\_THRESHOLD, in every role pair both sides get the value max(a, b). Switch takes no part anywhere else.

### Step 3. Axes and pairs

| Axis | Pairs (side A ↔ side B) | How computed |
| --- | --- | --- |
| Power | Dominant ↔ Submissive; Master/Mistress ↔ Slave; Owner ↔ Pet | complementary |
| Pain | Sadist ↔ Masochist | complementary |
| Rope | Rigger ↔ Rope bunny | complementary |
| Play | Brat ↔ Brat tamer; Primal (Hunter) ↔ Primal (Prey) | complementary |
| Humiliation | Degrader ↔ Degradee | complementary |
| Care | Daddy/Mommy ↔ Little | complementary |
| Display | Voyeur ↔ Exhibitionist | complementary |
| Style | Experimentalist, Vanilla, Ageplayer | by similarity |
| Structure | Non-monogamist | filter only (step 1) |

### Step 4. Role compatibility

For a pair of categories (a, b) and two people X and Y, the better of the two directions is taken. A direction works if the smaller of the two values is no lower than ACTIVE\_THRESHOLD.

```latex
v_p = \max\big(\min(X_a, Y_b),\ \min(X_b, Y_a)\big) \quad \text{(otherwise 0, if the smaller value is below the threshold)}
```

```latex
\text{role\_fit} = \frac{\sum_{p} w_p \, v_p}{\sum_{p \in P} w_p}
```

P is the set of pairs where at least one of the two has either side active. This way a person with a narrow set of interests is not penalised for what they do not have. If P is empty, role\_fit is 0. Pair weights w\_p default to 1.

**Experimental mode** adds the curiosity zone: if the larger of the two values is no lower than ACTIVE\_THRESHOLD and the smaller lies between CURIOUS\_LOW and the threshold, the direction gives CURIOUS\_FACTOR × the smaller value. In normal mode such directions are 0.

### Step 5. Style similarity

style\_sim is the mean over Experimentalist, Vanilla and Ageplayer of (100 − |X − Y|).

### Step 6. Total and ranking

score = WEIGHT\_ROLES × role\_fit + WEIGHT\_STYLE × style\_sim, with weights taken from the mode of whoever is viewing the feed. A candidate is shown only if there is at least one strictly working direction (not from the curiosity zone), even in experimental mode. Sort by descending score; ties are in random order that is stable within a day (seed from the user id and the date). Pages of FEED\_PAGE\_SIZE.

### Step 7. Explanation on the card

The candidate card contains the nickname and the caption "matched on: <axis names>", up to five axes. For the curiosity zone the caption is "could try: <axis>". Percentages, specific roles and the other side's "no" list are never sent, neither in HTML nor in the API. The numeric score is not shown to the user, and the interface says "matched on interests", not "psychological compatibility": the test is self-reported.

## 8. Likes, matches and the contact stub

A match appears only on a mutual like, and the contact itself is not implemented in the MVP: instead there is a stub interface, to which Telegram will be connected later.

- **Reactions.** Three kinds: `like`, `pass` (don't show this person again), `block` (hide mutually and remove from matches). A repeated reaction to the same person replaces the previous one only if it is a block.
- **Match.** When the second person gives a like, a row in `matches` is created in one transaction (the pair is ordered and unique). Both see each other in the "Matches" section.
- **Remove a match.** The "remove from matches" button deletes the match and sets a block on both sides.
- **Contact.** A `ContactGateway` class with an `on_match(match_id)` method; in the MVP it does nothing, and the match page shows the text "contact will open via the bot". No nicknames, usernames or messenger links in the interface.
- **No notifications.** A person sees a match when they open the app themselves.
- **Protection against scraping profiles.** A limit on feed pages and reactions per day (starting at 100 reactions and 20 pages), invite-only sign-up, the feed returns only the cards from section 7, not raw data.

## 9. Privacy and security

The main risk of the project is a database leak, because leaking such a database exposes people within their own community. So the requirements below are mandatory, not wishes.

**Consent, age, deletion**

- A consent screen at registration with the text "what we store and why"; the text version is written to `consent_version`, the time to `consent_at`.
- An "I am 18+" checkbox, the time in `age_confirmed_at`. There is no free text, photos or bio in the MVP at all: the nickname is generated from a dictionary.
- A `/privacy` page in plain language: what is stored (the fields from section 6), what is not (screenshots, original text, email, phone, name, IP in the DB), how to delete, that copies are wiped by rotation no later than 14 days.
- Account deletion: a button in settings, confirmation by password, hard cascade deletion, all sessions are revoked.

**Authentication and web protection**

- Passwords are stored as argon2id. Session cookie: HttpOnly, Secure, SameSite=Lax, limited lifetime. A CSRF token on every POST, including HTMX requests.
- Request limits on login, invite registration, OCR, the feed and reactions.
- A strict Content-Security-Policy, no third-party scripts, fonts, analytics or trackers. Fonts and scripts (including HTMX) are served from our own domain.
- Third-party error collection services (Sentry and the like) are not connected in the MVP.

**Logs and administration**

- The app logs only the event type and the request id. Percentages, gender, pairs, request bodies and query string parameters do not get into logs.
- Proxy logs without query parameters, kept no longer than 7 days.
- No web admin in the MVP. Invites are created by a CLI command (`python -m app.cli invite --count N --ttl-days 7`). Through the app's interface nobody, including the admin, sees other people's profiles.
- An honest statement for users: the administrator's access to the server technically allows reading the database, so the protection is designed against a leak, not against distrust of the admin.

**Encryption and backups**

- Passwords and recovery codes are stored only as hashes, invite codes too.
- The VPS disk is encrypted if the provider allows it. Backups are encrypted on the server before being sent anywhere; the key is stored separately.

## 10. Pages and endpoints

All pages except registration, login and `/privacy` require authorisation, and data-changing requests are protected by a CSRF token. Feed and card responses are built on the server and contain only allowed fields.

| Method and path | What it does | Access |
| --- | --- | --- |
| GET, POST /register | invite code, 18+, consent, nickname and password, showing the recovery code | guest |
| GET, POST /login; POST /logout | login and logout | guest, user |
| GET, POST /profile | gender, "who I am looking for", mode | user |
| GET /result | result entry page with two tabs | user |
| POST /result/parse-text | parses pasted text, returns the filled form | user |
| POST /result/parse-image | OCR of up to three images, returns the filled form with marks | user |
| POST /result/save | saving the 25 confirmed values | user |
| GET, POST /dislikes | the "no" list | user |
| GET /feed | feed page (HTMX fragment for loading more) | user |
| POST /react | like, pass or block for a candidate by public id | user |
| GET /matches; POST /matches/{id}/remove | list of matches, remove a match | user |
| GET /privacy | "what we store" page | everyone |
| POST /account/delete | account deletion with password confirmation | user |
| POST /account/password | password change | user |

The CLI command for invites is described in section 9. Public candidate identifiers in the feed are random UUIDs; there are no sequential numbers anywhere.

## 11. Non-functional requirements, tests and acceptance

The version is accepted when all items of the checklist below are met, and the tests pass in CI on every commit.

**Performance**

- Feed: no longer than 500 ms with 1000 active users.
- OCR of one screenshot: no longer than 10 seconds; the interface shows waiting.

**Tests (pytest)**

- **Text parser:** a correct list, garbage lines and the link, duplicates, missing categories, values outside 0–100, case and extra spaces, Unicode spaces.
- **OCR:** synthetic screenshots (light and dark theme, two scales), at least 90% of fields recognised, uncertain values are marked.
- **Matching:** synthetic profiles. Mutual filters, Switch, Non-monogamist, the "no" list, the curiosity zone, the difference between normal and experimental modes, an empty role\_fit denominator.
- **Integration:** registration by invite, profile, entering the result, feed, mutual like, match, account deletion.
- **Deletion:** after a user is deleted there is not a single row with their id in any table.

**Acceptance criteria**

- [ ] A pair of people see each other in the feed only when the filters hold mutually.
- [ ] No HTML or JSON response contains other people's percentages, roles or "no" list.
- [ ] Screenshots and original text get neither into the DB nor into files on disk (check: after OCR there are no new files outside tmpfs).
- [ ] After OCR the text about inaccurate recognition is always visible above the form.
- [ ] Logs contain no gender, percentage or pair fields; proxy requests contain no query string parameters.
- [ ] No external scripts, fonts or trackers; Content-Security-Policy is enabled.
- [ ] Deployment is done per the checklist in section 3; the backup is encrypted; restoring from it has been verified.
- [ ] The `/privacy` page matches the real behaviour of the system.

## 12. Work order and open questions

Work proceeds in eight stages; after each, the tests are run and a commit is made, and we move to the next stage only on green tests.

1. **Skeleton.** Repository, Docker Compose, PostgreSQL, Alembic, nginx, lint and tests in CI.
2. **Access.** Invites via CLI, registration, login, sessions, CSRF, 18+ and consent.
3. **Profile and result.** Profile, text parser, confirmation form, saving, "no" list.
4. **OCR.** Preprocessing, line parsing, marking uncertain values, warning, tests on synthetic screenshots.
5. **Matching.** Config, filters, scoring, feed with explanation, tests per section 7.
6. **Reactions and matches.** Reactions, mutual match, matches page, ContactGateway stub.
7. **Privacy.** `/privacy` page, account deletion, request limits, headers, logs, encrypted backup script.
8. **Deployment and acceptance.** Rollout to the VPS per the checklist in section 3, running the criteria from section 11.

**Open questions** (an assumption is made in the MVP; it can change without redesign):

| Question | MVP assumption |
| --- | --- |
| Verifying members and handing out invites | the admin hands out one-time codes manually via CLI |
| Restoring access | a recovery code shown once; lost it, create a new account |
| Is a city or region filter needed | not in the MVP, no geo in the schema |
| Accuracy of thresholds and weights | starting values from section 7, tuned after the first users |
| The category list on bdsmtest.org changes | the parser fails with a clear error, the list is fixed in `categories.py` |
| Domain | a proper domain is needed before rollout |
| Legal review (special-category data, EU and Ukraine) | owner's decision before opening beyond a narrow circle of acquaintances |
| Telegram contact and the "how did it go" loop | separate spec, only a stub in the MVP |
