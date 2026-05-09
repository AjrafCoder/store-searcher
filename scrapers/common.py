"""HTTP client + politeness primitives.

Sessions are thread-local so worker threads in a ThreadPoolExecutor each get
their own curl_cffi handle. A token-bucket rate limiter caps per-host RPS
across all workers — concurrency goes up, but a host never sees more than
one request per HOST_INTERVAL_SECONDS.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from urllib import robotparser
from urllib.parse import urlparse

from curl_cffi import requests as cffi_requests
from tenacity import retry, stop_after_attempt, wait_exponential

import config

log = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
IMPERSONATE = "chrome131"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}


class HostRateLimiter:
    """At most one request every `interval` seconds to any given host."""

    def __init__(self, interval: float):
        self._interval = interval
        self._next: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                next_at = self._next.get(host, 0.0)
                if now >= next_at:
                    self._next[host] = now + self._interval
                    return
                wait_for = next_at - now
            time.sleep(wait_for)


_limiter = HostRateLimiter(config.HOST_INTERVAL_SECONDS)
_thread_local = threading.local()
_robots_cache: dict[str, robotparser.RobotFileParser | None] = {}
_robots_lock = threading.Lock()


def session() -> cffi_requests.Session:
    s = getattr(_thread_local, "session", None)
    if s is None:
        s = cffi_requests.Session(impersonate=IMPERSONATE)
        s.headers.update(DEFAULT_HEADERS)
        _thread_local.session = s
    return s


def allowed_by_robots(url: str) -> bool:
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    with _robots_lock:
        cached = _robots_cache.get(base, "missing")
    if cached == "missing":
        rp = robotparser.RobotFileParser()
        rp.set_url(f"{base}/robots.txt")
        try:
            rp.read()
        except Exception as e:
            log.warning("robots.txt fetch failed for %s: %s", base, e)
            rp = None
        with _robots_lock:
            _robots_cache[base] = rp
        cached = rp
    if cached is None:
        return True
    return cached.can_fetch(UA, url)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch(url: str, *, respect_robots: bool = True,
          timeout: int = 30) -> cffi_requests.Response:
    if respect_robots and not allowed_by_robots(url):
        raise PermissionError(f"robots.txt disallows {url}")
    _limiter.wait(urlparse(url).netloc)
    r = session().get(url, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} for {url}")
    return r


# Match GTIN/EAN in three common shapes: JSON-LD (`"gtin13": "..."`),
# attribute markup (`gtin13="..."`), and microdata (`itemprop="gtin13" ... content="..."`).
_GTIN_RE = re.compile(
    r'(?:"(?:gtin13|gtin12|gtin8|gtin|barcode)"\s*:\s*"?([0-9]{8,14})"?'
    r'|gtin\d*\s*=\s*"([0-9]{8,14})"'
    r'|itemprop\s*=\s*["\']gtin\d*["\'][^>]*content\s*=\s*["\']([0-9]{8,14}))',
    re.I,
)


def extract_ean(html: str) -> str | None:
    """Pull a GTIN/EAN from JSON-LD, attribute, or microdata markup."""
    m = _GTIN_RE.search(html)
    if not m:
        return None
    for group in m.groups():
        if group and is_plausible_ean(group):
            return group
    return None


def is_plausible_ean(s: str | None) -> bool:
    return bool(s and s.isdigit() and 8 <= len(s) <= 14)
