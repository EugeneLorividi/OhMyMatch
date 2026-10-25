# Deployment (stage 8)

Checklist from spec section 3, mapped to who does what. Domain: `ohmymatch.xyz` (Namecheap).
State on 2026-10-25 is in the last column; "root" steps cannot be done by the `ohmymatch` user.

| # | Item | Who | State |
| --- | --- | --- | --- |
| 1 | Separate unix user without sudo | root | done: `ohmymatch`, groups `ohmymatch, users` |
| 2 | Separate Postgres user with access to its own database only | app | done: Postgres runs in its own container on an internal network, only the app database exists |
| 3 | Rootless containers, own network, app only on `127.0.0.1:8000` | app | done: linger on, user `docker` service enabled, `restart: unless-stopped` |
| 4 | nginx on 80/443 proxies to the app, certificate via certbot | root | partly: vhost and certificate exist, but the vhost still returns a placeholder |
| 5 | Firewall: only 80, 443, SSH; SSH by key only; fail2ban | root | to confirm: fail2ban active; `ufw status` and effective `sshd -T` need root |
| 6 | Proper domain, HTTPS required, HSTS on | owner, root | done: A record points to this VPS, HTTP redirects to HTTPS, HSTS sent |
| 7 | Secrets only in `.env`, mode 600, outside the repo | owner | file ok (`~/secrets/ohmymatch.env`, 600, dir 700), but it still holds development values |
| 8 | Backups encrypted on the server (age), key kept apart, rotation at most 14 days | owner | tooling done and restore tested; needs the real key and the cron entry |
| 9 | Proxy logs without query strings, at most 7 days | root | format ok; logrotate points at the wrong file |

## Owner steps (no root needed)

1. Production secrets, before the site goes public. The development database is empty, so it can be recreated:
   ```sh
   cd ~/ohmymatch && docker compose down -v          # drops the empty dev database
   # edit ~/secrets/ohmymatch.env: new POSTGRES_PASSWORD (also inside DATABASE_URL)
   # and SECRET_KEY, e.g. from: openssl rand -base64 48 | tr -d '/+=' | head -c 48
   docker compose up -d --build && docker compose run --rm app alembic upgrade head
   ```
2. Backup key: run `age-keygen -o identity.txt` on an offline machine, keep `identity.txt` there,
   and put only its public line (`age1...`) into `~/secrets/backup-recipients.txt` (mode 600).
3. Backups: `mkdir -m 700 ~/ohmymatch/backups`, install `deploy/crontab.example` with `crontab -e`,
   run it once by hand and check that a `.dump.age` file appears. Copy backups off the server if wanted:
   they are already encrypted.
4. Optional: an AAAA record for `ohmymatch.xyz` to `2a00:c98:400f:109:1c00:3ff:fe00:8f9`
   (nginx already listens on IPv6).

## Root steps

1. nginx: replace `/etc/nginx/sites-available/ohmymatch.xyz` with `deploy/nginx.conf.example`
   (real `proxy_pass`, 1 MB body limit, 25 MB only on `/result/parse-image`, `X-Forwarded-For`
   overwritten, app header duplicates hidden, full CSP, `server_tokens off`), then
   `nginx -t && systemctl reload nginx`. Do this only after owner step 1.
2. logrotate: replace `/etc/logrotate.d/ohmymatch` with `deploy/logrotate-ohmymatch.example`.
   The current file rotates `/var/log/nginx/ohmymatch.access.log`, but nginx writes
   `/var/log/nginx-ohmymatch/access.log`, which is therefore never rotated (and is world-readable).
   Check with `logrotate -d /etc/logrotate.d/ohmymatch`, then `chmod 640` the current file.
3. Confirm and report back:
   `ufw status verbose` (incoming only 22, 80, 443),
   `sshd -T | grep -E '^(passwordauthentication|permitrootlogin)'` (expect `no`, `prohibit-password` or `no`),
   `fail2ban-client status sshd`.

## Checks after the switch (ohmymatch user)

```sh
curl -sI https://ohmymatch.xyz/login | grep -iE 'x-request-id|content-security-policy|strict-transport'
curl -s https://ohmymatch.xyz/healthz                     # {"status":"ok"}
grep -c '?' /var/log/nginx-ohmymatch/access.log            # 0: no query strings
docker diff "$(docker compose ps -q app)"                  # empty
```
