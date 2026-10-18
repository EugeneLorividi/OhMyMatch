# pg_dump/pg_restore from the same Postgres image as the database, plus age for encryption.
# Runs as container root, which rootless Docker maps to the unprivileged host user.
FROM postgres:17.11-alpine3.24
RUN apk add --no-cache age=1.3.2-r1
COPY backup.sh restore.sh /usr/local/bin/
ENTRYPOINT []
