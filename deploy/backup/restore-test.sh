#!/usr/bin/env bash
# Backup round trip on synthetic data: encrypted backup, rotation, restore, compare.
# Uses throwaway containers and a throwaway age key pair; never touches real backups or keys.
set -euo pipefail
cd "$(dirname "$0")/../.."

work="$(mktemp -d)"
chmod 700 "$work"
export RT_DIR="$work"
compose=(docker compose -f deploy/backup/restore-test.yml)
cleanup() { "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true; rm -rf "$work"; }
trap cleanup EXIT

docker compose build -q app
docker compose --profile ops build -q backup
"${compose[@]}" up -d --wait src dst >/dev/null
"${compose[@]}" run --rm -T migrate >/dev/null 2>&1
"${compose[@]}" exec -T src psql -q -U rt -d rt -v ON_ERROR_STOP=1 < deploy/backup/seed-synthetic.sql

# Throwaway key pair, for this test only.
"${compose[@]}" run --rm -T --no-deps keys age-keygen 2>/dev/null > "$work/identity.txt"
"${compose[@]}" run --rm -T --no-deps keys age-keygen -y < "$work/identity.txt" > "$work/recipients.txt"

# Rotation fixtures: one copy older than 14 days, one recent.
touch -d '15 days ago' "$work/ohmymatch-19990101T000000Z.dump.age"
touch -d '13 days ago' "$work/ohmymatch-19990102T000000Z.dump.age"

"${compose[@]}" run --rm -T backup >/dev/null
fresh="$(cd "$work" && ls ohmymatch-*.dump.age | grep -v '^ohmymatch-1999' | tail -n 1)"
[ -n "$fresh" ] || { echo "FAIL: no backup written"; exit 1; }
[ ! -e "$work/ohmymatch-19990101T000000Z.dump.age" ] || { echo "FAIL: stale copy kept"; exit 1; }
[ -e "$work/ohmymatch-19990102T000000Z.dump.age" ] || { echo "FAIL: recent copy deleted"; exit 1; }
head -c 21 "$work/$fresh" | grep -q '^age-encryption.org/v1' || { echo "FAIL: not age format"; exit 1; }
if grep -aq 'restoretest-otter-11' "$work/$fresh"; then echo "FAIL: plaintext in backup"; exit 1; fi
echo "backup: encrypted, $(stat -c %s "$work/$fresh") bytes, mode $(stat -c %a "$work/$fresh"); rotation: stale deleted, recent kept"

"${compose[@]}" run --rm -T restore restore.sh "/backups/$fresh" >/dev/null

src="$("${compose[@]}" exec -T src psql -U rt -d rt -At < deploy/backup/digest.sql)"
dst="$("${compose[@]}" exec -T dst psql -U rt -d rt -At < deploy/backup/digest.sql)"
if [ "$src" != "$dst" ]; then echo "FAIL: restored data differs"; echo "src: $src"; echo "dst: $dst"; exit 1; fi
echo "restore: identical ($(echo "$src" | tr ' ' '\n' | cut -d: -f1,2 | tr '\n' ' '))"
echo "OK"
