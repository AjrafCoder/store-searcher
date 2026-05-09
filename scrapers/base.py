"""Base.com scraper — stub.

Base's robots.txt blocks listing pages. With the user's permission to override
robots for category listings, the implementation should fetch
`/games/department/<slug>` with `respect_robots=False`, parse the cards, then
visit each detail page to pull the EAN from JSON-LD.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

RETAILER = "Base.com"


def fetch_all(cache=None) -> list[dict]:
    log.info("Base.com: scraper not yet implemented for EAN flow — skipping")
    return []
