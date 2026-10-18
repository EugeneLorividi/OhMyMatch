#!/bin/sh
# Restore an encrypted backup into $PGDATABASE on $PGHOST.
# Usage (identity = the age private key, brought in only for the restore):
#   restore.sh /backups/ohmymatch-<stamp>.dump.age
set -eu
set -o pipefail

export PGUSER="${PGUSER:-$POSTGRES_USER}"
export PGPASSWORD="${PGPASSWORD:-$POSTGRES_PASSWORD}"
export PGDATABASE="${PGDATABASE:-$POSTGRES_DB}"
IDENTITY="${IDENTITY:-/keys/identity.txt}"

[ "$#" -eq 1 ] || { echo "usage: restore.sh FILE" >&2; exit 2; }
age --decrypt --identity "$IDENTITY" "$1" \
  | pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error --dbname "$PGDATABASE"
echo "restore_done"
