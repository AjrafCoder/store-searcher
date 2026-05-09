"""EAN-driven matcher + profit calc.

Retailer rows already include an EAN; the orchestrator looks each EAN up on
CeX, then this module joins them. EAN is exact, so no fuzzy matching is
needed. Anything missing an EAN, or whose EAN doesn't resolve to a CeX
gaming SKU, is logged as unmatched.
"""
from __future__ import annotations

import logging

import config

log = logging.getLogger(__name__)


def _saturation(stock: int) -> str:
    if stock >= config.SATURATION_HIGH:
        return "high"
    if stock >= config.SATURATION_MEDIUM:
        return "medium"
    return "low"


def build_deals(retailer_rows: list[dict],
                cex_by_ean: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    deals: list[dict] = []
    unmatched: list[dict] = []
    for r in retailer_rows:
        ean = r.get("ean")
        if not ean:
            unmatched.append({**r, "reason": "retailer row missing EAN"})
            continue
        cex = cex_by_ean.get(ean)
        if not cex:
            unmatched.append({**r, "reason": "EAN not in CeX gaming catalog"})
            continue
        retail_price = float(r["price"])
        delivery = float(r.get("delivery_estimate") or 0)
        profit_voucher = round(cex["exchangePrice"] - retail_price - delivery, 2)
        profit_cash = round(cex["cashPrice"] - retail_price - delivery, 2)
        if profit_voucher < config.MIN_PROFIT_VOUCHER:
            continue
        deals.append({
            "title": cex["boxName"],
            "retailer_title": r["title"],
            "platform": cex.get("platform") or r.get("platform"),
            "retailer": r["retailer"],
            "ean": ean,
            "buy_price": retail_price,
            "delivery_estimate": delivery,
            "cex_cash": cex["cashPrice"],
            "cex_voucher": cex["exchangePrice"],
            "cex_sell": cex["sellPrice"],
            "profit_voucher": profit_voucher,
            "profit_cash": profit_cash,
            "saturation_risk": _saturation(cex["ecomQuantityOnHand"]),
            "cex_stock": cex["ecomQuantityOnHand"],
            "buy_url": r["url"],
            "cex_url": cex["url"],
            "cex_box_id": cex["boxId"],
        })
    deals.sort(key=lambda d: d["profit_voucher"], reverse=True)
    return deals, unmatched
