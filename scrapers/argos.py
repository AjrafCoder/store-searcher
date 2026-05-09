"""Argos scraper — stub.

Argos's finder-api endpoint shape changes frequently. Implementation pattern:
hit `/finder-api/product;...search/<query>/` with `respect_robots=False`, parse
JSON, look up each SKU's detail page for EAN, return rows.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

RETAILER = "Argos"


def fetch_all(cache=None) -> list[dict]:
    log.info("Argos: scraper not yet implemented for EAN flow — skipping")
    return []
