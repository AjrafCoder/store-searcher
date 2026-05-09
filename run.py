"""Orchestrator: scrape retailers (with EANs), look up each EAN on CeX, write JSON.

Adding a retailer = drop a module in scrapers/ exposing
`fetch_all(cache=None) -> list[dict]` whose rows include:
   retailer, title, platform, price, url, in_stock, delivery_estimate, ean
Then add one line to RETAILERS below.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import config
from match import build_deals
from scrapers import (
    argos,
    cex,
    base as base_com,
    shopto,
    smyths,
    thegamecollection,
)
from scrapers.cache import Cache

log = logging.getLogger("run")
DATA_DIR = Path(__file__).parent / "data"
CACHE_PATH = DATA_DIR / "cache.sqlite"

RETAILERS = [
    ("The Game Collection", thegamecollection.fetch_all),
    ("ShopTo",              shopto.fetch_all),
    ("Base.com",            base_com.fetch_all),
    ("Argos",               argos.fetch_all),
    ("Smyths",              smyths.fetch_all),
]


def run(use_cache: bool = True) -> int:
    DATA_DIR.mkdir(exist_ok=True)
    cache: Cache | None = Cache(CACHE_PATH) if use_cache else None
    errors: list[dict] = []

    try:
        retailer_rows: list[dict] = []
        for name, fetcher in RETAILERS:
            log.info("scraping %s", name)
            try:
                rows = fetcher(cache=cache)
                log.info("%s: %d rows with EAN", name, len(rows))
                retailer_rows.extend(rows)
            except Exception as e:
                log.exception("%s scrape failed", name)
                errors.append({
                    "source": name,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })

        eans = sorted({r["ean"] for r in retailer_rows if r.get("ean")})
        log.info("looking up %d unique EANs on CeX", len(eans))
        cex_by_ean: dict[str, dict] = {}
        if eans:
            try:
                cex_by_ean = cex.lookup_many(eans, cache=cache, gaming_only=True)
            except Exception as e:
                log.exception("CeX bulk lookup failed")
                errors.append({
                    "source": "cex",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })

        deals, unmatched = build_deals(retailer_rows, cex_by_ean)

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "min_profit_voucher": config.MIN_PROFIT_VOUCHER,
            "deal_count": len(deals),
            "total_potential_profit": round(sum(d["profit_voucher"] for d in deals), 2),
            "retailer_rows": len(retailer_rows),
            "unique_eans": len(eans),
            "cex_matched": len(cex_by_ean),
            "errors": errors,
            "deals": deals,
        }
        (DATA_DIR / "deals.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (DATA_DIR / "unmatched.json").write_text(
            json.dumps(
                {"generated_at": payload["generated_at"], "items": unmatched[:1000]},
                indent=2, ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        log.info("wrote %d deals, %d unmatched, %d scraper errors",
                 len(deals), len(unmatched), len(errors))

        # Fail only when we produced nothing AND something errored — partial
        # success (some deals + some retailer errors) is normal and shouldn't
        # spam the GH issue tracker.
        return 1 if errors and not deals else 0
    finally:
        if cache is not None:
            cache.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-cache", action="store_true",
                        help="bypass on-disk caches (force fresh fetches)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    return run(use_cache=not args.no_cache)


if __name__ == "__main__":
    sys.exit(main())
