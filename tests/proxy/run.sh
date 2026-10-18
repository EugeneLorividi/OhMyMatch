#!/usr/bin/env bash
# Verifies per-IP limits behind nginx: two clients with different addresses, one forging
# X-Forwarded-For. Expects: A limited after the per-IP budget, B unaffected, forging useless.
set -euo pipefail
cd "$(dirname "$0")"
compose=(docker compose -f compose.yml)
trap '"${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true' EXIT

(cd ../.. && docker compose build -q app && docker compose -f compose.test.yml build -q tests)
"${compose[@]}" up -d --wait db >/dev/null 2>&1
"${compose[@]}" run --rm -T migrate >/dev/null 2>&1
"${compose[@]}" up -d app nginx >/dev/null 2>&1
for _ in $(seq 1 30); do
  "${compose[@]}" run --rm -T client_b 0 >/dev/null 2>&1 && break
  sleep 1
done

limit="$(cd ../.. && .venv/bin/python -c 'import os; os.environ.setdefault("SECRET_KEY", "x" * 32); from app.config import LOGIN_PER_IP; print(LOGIN_PER_IP.limit)')"
run() { "${compose[@]}" run --rm -T "$@" 2>/dev/null; }

a="$(run client_a "$limit")"
a_next="$(run client_a 1)"
a_forged="$(run client_a 1 "198.51.100.77")"
b="$(run client_b 1 "10.231.1.10")"   # B pretends to be A

count_400="$(tr ' ' '\n' <<<"$a" | grep -c '^400$' || true)"
echo "client A: $count_400/$limit attempts accepted (400 = wrong password), next: $a_next"
echo "client A with forged X-Forwarded-For: $a_forged"
echo "client B claiming to be A: $b"
[ "$count_400" = "$limit" ] && [ "$a_next" = "429" ] && [ "$a_forged" = "429" ] && [ "$b" = "400" ] \
  && echo "OK" || { echo "FAIL"; exit 1; }
