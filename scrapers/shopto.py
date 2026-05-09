"""ShopTo scraper.

Stub: ShopTo's sitemap structure needs investigation (the index didn't list
product sub-sitemaps under the names I expected). Until updated, returns [].
Pattern to follow when implementing: discover product URLs → fetch detail
pages with `respect_robots=False` if needed → `extract_ean()` → return rows
shaped like TGC's `fetch_all` output.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

RETAILER = "ShopTo"


def fetch_all(cache=None) -> list[dict]:
    log.info("ShopTo: scraper not yet implemented for EAN flow — skipping")
    return []
