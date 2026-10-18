"""Keeps deploy files, the proxy check and the app's assumptions in sync."""

import ipaddress
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def proxy_headers(text: str) -> list[str]:
    return sorted(set(re.findall(r"proxy_set_header\s+[^;]+;", text)))


def test_nginx_example_overwrites_forwarded_for():
    example = (ROOT / "deploy/nginx.conf.example").read_text()
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in example
    assert "$proxy_add_x_forwarded_for" not in example


def test_proxy_check_uses_the_example_headers():
    example = (ROOT / "deploy/nginx.conf.example").read_text()
    check = (ROOT / "tests/proxy/nginx.conf").read_text()
    assert proxy_headers(check) == proxy_headers(example)


def test_trusted_proxy_is_the_edge_gateway():
    compose = (ROOT / "docker-compose.yml").read_text()
    trusted = re.search(r'TRUSTED_PROXIES: "([^"]+)"', compose).group(1)
    subnet = re.search(r"subnet: ([0-9./]+)", compose).group(1)
    gateway = re.search(r"gateway: ([0-9.]+)", compose).group(1)
    assert trusted == gateway
    assert ipaddress.ip_address(gateway) in ipaddress.ip_network(subnet)
    assert '"127.0.0.1:8000:8000"' in compose


def test_backup_retention_and_mounts():
    from app.config import BACKUP_RETENTION_DAYS

    compose = (ROOT / "docker-compose.yml").read_text()
    assert f'RETENTION_DAYS: "{BACKUP_RETENTION_DAYS}"' in compose
    settings = re.findall(r"^\s+create_host_path: false$", compose, re.MULTILINE)
    assert len(settings) == 2
    script = (ROOT / "deploy/backup/backup.sh").read_text()
    assert "pg_dump" in script and "| age --encrypt" in script
    assert "set -o pipefail" in script and "umask 077" in script


def test_csp_matches_between_app_and_nginx():
    from app.middleware import CSP

    example = (ROOT / "deploy/nginx.conf.example").read_text()
    assert f'add_header Content-Security-Policy "{CSP}" always;' in example
