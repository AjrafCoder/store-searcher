"""SQLite cache for retailer detail pages and CeX lookups.

The cache lets repeat runs skip work:

- Retailer detail pages: keyed on (retailer, url). Refetched if the listed
  price has moved (proxy for "product changed") or if the entry is older
  than RETAILER_CACHE_TTL_SECONDS.
- CeX lookups: keyed on EAN. Cached misses are remembered too, so we don't
  hammer the API for known-not-in-CeX barcodes.

Cache hits are differentiated from cache misses via a (hit, value) tuple so
callers can tell "we tried, it's not in CeX" apart from "never tried".
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS retailer_detail (
    retailer TEXT NOT NULL,
    url TEXT NOT NULL,
    listed_price REAL NOT NULL,
    ean TEXT,
    fetched_at REAL NOT NULL,
    PRIMARY KEY (retailer, url)
);
CREATE TABLE IF NOT EXISTS cex_lookup (
    ean TEXT PRIMARY KEY,
    payload TEXT,
    fetched_at REAL NOT NULL
);
"""


class Cache:
    def __init__(self, path: Path):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.executescript(SCHEMA)
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # --- Retailer detail cache ----------------------------------------

    def get_retailer_ean(self, retailer: str, url: str, listed_price: float,
                         ttl: float) -> tuple[bool, str | None]:
        """Returns (hit, ean). hit=False if missing / stale / price changed."""
        with self._lock:
            row = self._db.execute(
                "SELECT ean, fetched_at, listed_price FROM retailer_detail "
                "WHERE retailer=? AND url=?",
                (retailer, url),
            ).fetchone()
        if not row:
            return False, None
        ean, fetched_at, cached_price = row
        if abs(cached_price - listed_price) > 0.01:
            return False, None
        if (time.time() - fetched_at) > ttl:
            return False, None
        return True, ean

    def put_retailer_ean(self, retailer: str, url: str, listed_price: float,
                         ean: str | None) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO retailer_detail "
                "(retailer, url, listed_price, ean, fetched_at) VALUES (?,?,?,?,?)",
                (retailer, url, listed_price, ean, time.time()),
            )
            self._db.commit()

    # --- CeX lookup cache ---------------------------------------------

    def get_cex(self, ean: str, ttl: float) -> tuple[bool, dict | None]:
        """Returns (hit, entry). entry=None for a remembered miss."""
        with self._lock:
            row = self._db.execute(
                "SELECT payload, fetched_at FROM cex_lookup WHERE ean=?",
                (ean,),
            ).fetchone()
        if not row:
            return False, None
        payload, fetched_at = row
        if (time.time() - fetched_at) > ttl:
            return False, None
        return True, (json.loads(payload) if payload else None)

    def put_cex(self, ean: str, entry: dict | None) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO cex_lookup (ean, payload, fetched_at) "
                "VALUES (?,?,?)",
                (ean, json.dumps(entry) if entry else None, time.time()),
            )
            self._db.commit()
