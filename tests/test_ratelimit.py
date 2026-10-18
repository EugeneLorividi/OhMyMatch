import ipaddress

import pytest

from app import clientip
from app.config import Rule
from app.ratelimit import RateLimiter

RULE = Rule("test", 3, 60)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_rolling_window():
    clock = Clock()
    limiter = RateLimiter(b"k" * 32, clock)
    assert [limiter.hit(RULE, "a") for _ in range(3)] == [None, None, None]
    assert limiter.hit(RULE, "a") == 60
    assert limiter.hit(RULE, "b") is None  # other subject, own bucket
    clock.now += 30
    assert limiter.retry_after(RULE, "a") == 30
    clock.now += 30
    assert limiter.hit(RULE, "a") is None


def test_check_without_recording():
    limiter = RateLimiter(b"k" * 32, Clock())
    for _ in range(5):
        assert limiter.retry_after(RULE, "a") is None
    for _ in range(3):
        limiter.record(RULE, "a")
    assert limiter.retry_after(RULE, "a") is not None


def test_rules_have_separate_buckets():
    limiter = RateLimiter(b"k" * 32, Clock())
    for _ in range(3):
        limiter.hit(RULE, "a")
    assert limiter.hit(Rule("other", 3, 60), "a") is None


def test_subjects_are_kept_only_as_keyed_hashes():
    limiter = RateLimiter(b"k" * 32, Clock())
    limiter.hit(RULE, "203.0.113.7")
    stored = b"".join(limiter._hits)
    assert b"203.0.113.7" not in stored
    assert RateLimiter(b"x" * 32, Clock())._key(RULE, "a") != limiter._key(RULE, "a")


def test_expired_buckets_are_pruned():
    clock = Clock()
    limiter = RateLimiter(b"k" * 32, clock)
    for index in range(999):
        limiter.hit(RULE, f"s{index}")
    clock.now += 61
    limiter.hit(RULE, "last")  # 1000th call triggers pruning
    assert limiter.size() == 1


@pytest.fixture
def trusted(monkeypatch):
    def set_trusted(value: str):
        monkeypatch.setattr(clientip.settings, "trusted_proxies", value)
        clientip._trusted.cache_clear()

    yield set_trusted
    clientip._trusted.cache_clear()


class FakeRequest:
    def __init__(self, peer, forwarded=None):
        self.client = type("C", (), {"host": peer})()
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}


def test_untrusted_peer_ignores_forwarded_header(trusted):
    trusted("")
    assert clientip.client_ip(FakeRequest("198.51.100.9", "1.2.3.4")) == "198.51.100.9"


def test_trusted_proxy_rightmost_entry_wins(trusted):
    trusted("172.31.240.1, 10.0.0.0/8")
    assert clientip.client_ip(FakeRequest("172.31.240.1", "203.0.113.5")) == "203.0.113.5"
    # A client-forged first entry cannot choose the address.
    assert clientip.client_ip(FakeRequest("10.1.2.3", "6.6.6.6, 203.0.113.5")) == "203.0.113.5"
    assert clientip.client_ip(FakeRequest("172.31.240.1")) == "172.31.240.1"
    assert clientip.client_ip(FakeRequest("testclient", "1.1.1.1")) == "testclient"


def test_trusted_networks_parse():
    assert ipaddress.ip_address("172.31.240.1") in ipaddress.ip_network("172.31.240.0/28")
