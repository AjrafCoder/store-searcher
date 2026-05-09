"""Tunable constants for the arbitrage pipeline.

Kept deliberately flat — these are the dials you'd turn when tuning behaviour
without touching scraper logic.
"""
from __future__ import annotations

# --- Profit thresholds ---
MIN_PROFIT_VOUCHER = 1.00

# Skip retailer listings priced above this. CeX voucher prices on games rarely
# exceed the upper £40s, so anything pricier won't yield £5+ profit. Drop this
# to 35 if you want a tighter filter and faster runs.
PROFITABLE_PRICE_CEILING = 45.00

# --- Concurrency + politeness ---
# Per-host minimum interval between requests, enforced across all worker
# threads. 0.4s = 2.5 RPS per host. Lower = faster + more aggressive.
HOST_INTERVAL_SECONDS = 0.4

# Worker pool sizes. Higher than ~8 doesn't help much because the per-host
# rate limiter caps effective throughput.
DETAIL_FETCH_WORKERS = 6
CEX_LOOKUP_WORKERS = 6

# --- Cache TTLs ---
RETAILER_CACHE_TTL_SECONDS = 7 * 24 * 3600   # 7 days for retailer detail pages
CEX_CACHE_TTL_SECONDS = 12 * 3600             # 12h — voucher prices change daily

# --- CeX API ---
CEX_API = "https://wss2.cex.uk.webuy.io/v3"

# --- Stock saturation flags (CeX ecomQuantityOnHand) ---
SATURATION_MEDIUM = 10
SATURATION_HIGH = 30
