"""CeX lookup via the still-open per-box detail endpoint.

The bulk listing endpoint (`/v3/boxes`) is now Cloudflare-WAF blocked. The
per-box endpoint (`/v3/boxes/{id}/detail`) accepts box IDs and EAN/UPC
barcodes; that's our entry point. EANs come from retailer scrapers.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

from tenacity import retry, stop_after_attempt, wait_exponential

import config

from .cache import Cache
from .common import session

log = logging.getLogger(__name__)

# Match by `categoryName` substring (e.g. "Playstation5 Software"). Robust
# against CeX renumbering categoryIds. Order matters: "Switch 2" before
# "Switch", "Xbox Series" before "Xbox One".
PLATFORM_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("Switch 2",     ("switch 2",)),
    ("PS5",          ("playstation5", "ps5")),
    ("PS4",          ("playstation4", "ps4")),
    ("Xbox Series",  ("xbox series",)),
    ("Xbox One",     ("xbox one", "xbox 1")),
    ("Switch",       ("switch",)),
]


def _platform_from_category(category_name: str | None) -> str | None:
    if not category_name:
        return None
    s = category_name.lower()
    for label, needles in PLATFORM_PATTERNS:
        if any(n in s for n in needles):
            return label
    return None


def _normalise(raw: dict) -> dict:
    cat_name = raw.get("categoryName") or raw.get("categoryFriendlyName")
    return {
        "boxId": raw.get("boxId"),
        "boxName": raw.get("boxName"),
        "categoryId": raw.get("categoryId"),
        "categoryName": cat_name,
        "superCatFriendlyName": raw.get("superCatFriendlyName"),
        "platform": _platform_from_category(cat_name),
        "sellPrice": float(raw.get("sellPrice") or 0),
        "cashPrice": float(raw.get("cashPrice") or 0),
        "exchangePrice": float(raw.get("exchangePrice") or 0),
        "ecomQuantityOnHand": int(raw.get("ecomQuantityOnHand") or 0),
        "outOfStock": int(raw.get("outOfStock") or 0),
        "outOfEcomStock": int(raw.get("outOfEcomStock") or 0),
        "url": f"https://uk.webuy.com/product-detail?id={raw.get('boxId')}",
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _get_detail(box_id: str) -> dict | None:
    r = session().get(f"{config.CEX_API}/boxes/{box_id}/detail", timeout=20)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    payload = json.loads(r.text)
    data = payload.get("response", {}).get("data")
    if not data:
        return None
    boxes = data.get("boxDetails") or []
    return boxes[0] if boxes else None


def lookup(box_id: str) -> dict | None:
    raw = _get_detail(box_id)
    return _normalise(raw) if raw else None


def _is_gaming_match(entry: dict) -> bool:
    return (entry.get("superCatFriendlyName") == "Gaming"
            and bool(entry.get("platform")))


def lookup_many(eans: Iterable[str], *, cache: Cache | None = None,
                gaming_only: bool = True) -> dict[str, dict]:
    """Bulk lookup with worker pool and optional cache."""
    unique = sorted({e for e in eans if e})

    def fetch_one(ean: str) -> tuple[str, dict | None]:
        if cache:
            hit, cached = cache.get_cex(ean, config.CEX_CACHE_TTL_SECONDS)
            if hit:
                return ean, cached
        try:
            entry = lookup(ean)
        except Exception as e:
            log.debug("CeX lookup %s failed: %s", ean, e)
            return ean, None
        if cache:
            cache.put_cex(ean, entry)
        return ean, entry

    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=config.CEX_LOOKUP_WORKERS) as ex:
        for ean, entry in ex.map(fetch_one, unique):
            if not entry:
                continue
            if gaming_only and not _is_gaming_match(entry):
                continue
            out[ean] = entry

    log.info("CeX lookup: %d / %d EANs matched (gaming_only=%s)",
             len(out), len(unique), gaming_only)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(lookup("5030943125299"))
