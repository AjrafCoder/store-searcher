"""Smyths Toys scraper — stub.

Listing pages return 200 but their markup uses a JS-rendered grid. Implementation
should either use the JSON used to hydrate the grid, or fall back to product
detail pages where JSON-LD `gtin13` is reliably present.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

RETAILER = "Smyths"


def fetch_all(cache=None) -> list[dict]:
    log.info("Smyths: scraper not yet implemented for EAN flow — skipping")
    return []
