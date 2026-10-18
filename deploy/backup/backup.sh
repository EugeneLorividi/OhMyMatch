#!/bin/sh
# Encrypted logical backup of the database (spec sections 3 and 9).
# The dump is piped straight into age: no plaintext ever touches the disk.
set -eu
set -o pipefail
umask 077

export PGUSER="${PGUSER:-$POSTGRES_USER}"
export PGPASSWORD="${PGPASSWORD:-$POSTGRES_PASSWORD}"
export PGDATABASE="${PGDATABASE:-$POSTGRES_DB}"
RECIPIENTS="${RECIPIENTS:-/keys/recipients.txt}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DIR="${BACKUP_DIR:-/backups}"

[ -f "$RECIPIENTS" ] && [ -s "$RECIPIENTS" ] || { echo "backup_failed: no age recipients file" >&2; exit 1; }

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="$DIR/ohmymatch-$stamp.dump.age"
pg_dump --format=custom --no-owner --no-privileges \
  | age --encrypt --recipients-file "$RECIPIENTS" --output "$out.partial"
mv "$out.partial" "$out"

# Rotation: keep copies younger than RETENTION_DAYS days, delete the rest.
find "$DIR" -maxdepth 1 -type f -name 'ohmymatch-*.dump.age' -mtime +"$((RETENTION_DAYS - 1))" -delete
find "$DIR" -maxdepth 1 -type f -name 'ohmymatch-*.partial' -mmin +60 -delete
echo "backup_written"
