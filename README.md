# UK Game Arbitrage

Static site that surfaces UK retail games priced **at least £1 below CeX's
We-Buy voucher**. Scrapes daily via GitHub Actions, writes `data/deals.json`,
renders a sortable table.

## Stack

- **Hosting:** any static host (Cloudflare Pages, GitHub Pages, Netlify free).
- **Refresh:** `.github/workflows/scrape.yml` runs daily at 06:00 UTC.
- **Storage:** committed `data/deals.json` — no DB.
- **Frontend:** plain HTML + vanilla JS + Tailwind CDN. No build step.
- **Scrapers:** Python 3.12, `curl_cffi` (Chrome TLS impersonation, required
  to talk to CeX through Cloudflare) + `tenacity`.

## Architecture

CeX changed: their bulk listing endpoint (`/v3/boxes`) is now Cloudflare-WAF
blocked for every TLS fingerprint. The per-box detail endpoint
(`/v3/boxes/{id}/detail`) is open and accepts EAN/UPC barcodes. So:

1. **Scrape retailers** for product listings → fetch each candidate's detail
   page → pull the EAN from JSON-LD.
2. **Look up each EAN** on CeX's per-box endpoint to get
   `sellPrice / cashPrice / exchangePrice / stock`.
3. **Profit calc** joins on the EAN (exact match — no fuzzy needed).

### Performance

- Detail-page fetches and CeX lookups run in `ThreadPoolExecutor`s with a
  central per-host token-bucket rate limiter (`scrapers.common.HostRateLimiter`),
  so concurrency goes up while a single host never sees more than
  `1 / HOST_INTERVAL_SECONDS` RPS.
- A SQLite cache (`data/cache.sqlite`, restored from `actions/cache` in CI)
  keys retailer detail pages on `(retailer, url, listed_price)` and CeX
  lookups on EAN. Repeat runs only re-fetch entries whose listed price has
  moved or whose CeX TTL has expired.
- Cold run: ~5 min for the full TGC catalog. Warm run: tens of seconds.

## Run locally

```powershell
pip install -r requirements.txt
python run.py                  # full scrape with on-disk cache
python run.py --no-cache       # force-refresh everything
python run.py -v               # verbose logging
python -m http.server 8080     # serve the static site
```

For development:
```powershell
pip install -r requirements-dev.txt
pytest
```

## Add a retailer

1. Drop a module in `scrapers/yourstore.py` exposing
   `fetch_all(cache=None) -> list[dict]`. Each row must include:
   `retailer, title, platform, price, url, in_stock, delivery_estimate, ean`.
2. Add one line to `RETAILERS` in `run.py`.

`scrapers/thegamecollection.py` is the reference implementation (Shopify
products.json listing → threaded detail-page EAN extraction with cache).
ShopTo / Base.com / Argos / Smyths exist as stubs.

## Tunables

All in `config.py`:

| Constant | Default | What |
|---|---|---|
| `MIN_PROFIT_VOUCHER` | £1.00 | Floor to count as a deal. |
| `PROFITABLE_PRICE_CEILING` | £45.00 | Skip retailer items priced above this. |
| `HOST_INTERVAL_SECONDS` | 0.4 | Min seconds between requests to the same host. |
| `DETAIL_FETCH_WORKERS` | 6 | TGC detail-page worker pool size. |
| `CEX_LOOKUP_WORKERS` | 6 | CeX lookup worker pool size. |
| `RETAILER_CACHE_TTL_SECONDS` | 7 days | When to refetch unchanged retailer detail pages. |
| `CEX_CACHE_TTL_SECONDS` | 12 h | When to refetch CeX lookups. |
| `SATURATION_MEDIUM` / `SATURATION_HIGH` | 10 / 30 | Stock thresholds for risk pills. |

## Profit logic

```
profit_voucher = cex.exchangePrice - retail.price - delivery_estimate
profit_cash    = cex.cashPrice     - retail.price - delivery_estimate
```

Deals require `profit_voucher >= MIN_PROFIT_VOUCHER`. Saturation flags items
where CeX already has 10+ (medium) or 30+ (high) on hand — those voucher
prices tend to drop fast.

## Disclaimers

- Prices may be **up to 24h stale**.
- CeX We-Buy prices change without notice; stock saturation drops them
  further, sometimes between you walking into the store and reaching the
  counter.
- Some sites' Terms of Service prohibit scraping. Listing-page robots.txt
  rules are overridden for retailers (Base.com, Argos) where required by the
  pipeline; rate-limit yourself politely and use at your own risk.
- **Not financial advice.** Verify every price before buying.
