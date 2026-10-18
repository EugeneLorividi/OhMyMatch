"""Client address for rate limiting only. Never stored, never logged."""

import ipaddress
from functools import lru_cache

from fastapi import Request

from app.config import settings


@lru_cache
def _trusted() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    parts = [p.strip() for p in settings.trusted_proxies.split(",") if p.strip()]
    return tuple(ipaddress.ip_network(part, strict=False) for part in parts)


def _is_trusted(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in _trusted())


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else ""
    if not _is_trusted(peer):
        return peer
    # nginx sets X-Forwarded-For to the address it saw; take the rightmost entry, which the
    # trusted proxy wrote, so a client-supplied header cannot pick its own address.
    forwarded = request.headers.get("x-forwarded-for", "")
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    return hops[-1] if hops else peer
