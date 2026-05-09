"""The Game Collection scraper.

TGC is a Shopify storefront. Two-stage flow:

1. List products cheaply via `collections/<slug>/products.json` (paginated).
2. For each in-stock candidate priced ≤ PROFITABLE_PRICE_CEILING, fetch the
   product detail page and extract the EAN from JSON-LD. The cache short-
   circuits step 2 when the listing price hasn't moved since the last run.

Detail fetches run concurrently; the host rate limiter caps RPS centrally.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import config

from .cache import Cache
from .common import extract_ean, fetch, is_plausible_ean

log = logging.getLogger(__name__)

RETAILER = "The Game Collection"
BASE = "https://www.thegamecollection.net"
DEFAULT_DELIVERY = 0.0

PLATFORM_COLLECTIONS = [
    ("PS5",          "ps5-games"),
    ("PS4",          "ps4-games"),
    ("Xbox Series",  "xbox-series-x-games"),
    ("Xbox One",     "xbox-one-games"),
    ("Switch",       "nintendo-switch-games"),
    ("Switch 2",     "nintendo-switch-2-games"),
]
PAGE_SIZE = 250


def _list_collection(slug: str, platform: str) -> list[dict]:
    out: list[dict] = []
    page = 1
    while True:
        url = f"{BASE}/collections/{slug}/products.json?limit={PAGE_SIZE}&page={page}"
        try:
            r = fetch(url, respect_robots=False)
        except Exception as e:
            log.warning("TGC list %s page %d failed: %s", slug, page, e)
            break
        try:
            products = json.loads(r.text).get("products", [])
        except json.JSONDecodeError:
            break
        if not products:
            break
        for p in products:
            v = (p.get("variants") or [{}])[0]
            try:
                price = float(v.get("price"))
            except (TypeError, ValueError):
                continue
            out.append({
                "retailer": RETAILER,
                "title": p.get("title"),
                "platform": platform,
                "price": price,
                "url": f"{BASE}/products/{p.get('handle')}",
                "in_stock": bool(v.get("available")),
                "delivery_estimate": DEFAULT_DELIVERY,
                "ean": None,
            })
        log.info("TGC %s page %d: %d products (running total %d)",
                 platform, page, len(products), len(out))
        if len(products) < PAGE_SIZE:
            break
        page += 1
    return out


def _enrich_one(row: dict, cache: Cache | None) -> dict | None:
    if cache is not None:
        hit, cached_ean = cache.get_retailer_ean(
            row["retailer"], row["url"], row["price"], config.RETAILER_CACHE_TTL_SECONDS,
        )
        if hit:
            if not is_plausible_ean(cached_ean):
                return None
            row["ean"] = cached_ean
            return row
    try:
        r = fetch(row["url"], respect_robots=False)
    except Exception as e:
        log.debug("TGC detail failed (%s): %s", row["url"], e)
        if cache is not None:
            cache.put_retailer_ean(row["retailer"], row["url"], row["price"], None)
        return None
    ean = extract_ean(r.text)
    if cache is not None:
        cache.put_retailer_ean(row["retailer"], row["url"], row["price"], ean)
    if not is_plausible_ean(ean):
        return None
    row["ean"] = ean
    return row


def _enrich_eans(candidates: list[dict], cache: Cache | None) -> list[dict]:
    out: list[dict] = []
    with ThreadPoolExecutor(max_workers=config.DETAIL_FETCH_WORKERS) as ex:
        futures = [ex.submit(_enrich_one, row, cache) for row in candidates]
        for i, fut in enumerate(as_completed(futures), start=1):
            try:
                result = fut.result()
            except Exception as e:
                log.debug("TGC enrich error: %s", e)
                continue
            if result:
                out.append(result)
            if i % 100 == 0 or i == len(futures):
                log.info("TGC EAN enrich: %d / %d done, %d with EAN",
                         i, len(futures), len(out))
    return out


def fetch_all(cache: Cache | None = None) -> list[dict]:
    listed: list[dict] = []
    for platform, slug in PLATFORM_COLLECTIONS:
        listed.extend(_list_collection(slug, platform))
    candidates = [r for r in listed
                  if r["in_stock"] and r["price"] <= config.PROFITABLE_PRICE_CEILING]
    # Cheapest first — best deals surface even if the run is timed out.
    candidates.sort(key=lambda r: r["price"])
    log.info("TGC: %d listed, %d candidates after price/stock filter",
             len(listed), len(candidates))
    return _enrich_eans(candidates, cache)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rows = fetch_all()
    print(f"got {len(rows)} TGC rows with EAN")
