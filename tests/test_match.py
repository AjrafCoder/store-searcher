from match import build_deals

CEX_BASE = {
    "boxId": "SPS5GTAV",
    "boxName": "GTA V",
    "categoryId": 1141,
    "platform": "PS5",
    "exchangePrice": 25.0,
    "cashPrice": 18.0,
    "sellPrice": 30.0,
    "ecomQuantityOnHand": 5,
    "url": "https://uk.webuy.com/product-detail?id=SPS5GTAV",
}


def make_retail(price, ean="111", delivery=0.0, **extra):
    base = {
        "retailer": "TestStore",
        "title": "Test Game",
        "platform": "PS5",
        "price": price,
        "url": "https://test/p/x",
        "in_stock": True,
        "delivery_estimate": delivery,
        "ean": ean,
    }
    base.update(extra)
    return base


def test_includes_deal_above_threshold():
    deals, unm = build_deals([make_retail(15.0)], {"111": CEX_BASE})
    assert len(deals) == 1
    assert deals[0]["profit_voucher"] == 10.0
    assert unm == []


def test_excludes_deal_below_threshold():
    # Voucher £25, retail £24.50 → £0.50 profit, below £1 threshold.
    deals, _ = build_deals([make_retail(24.5)], {"111": CEX_BASE})
    assert deals == []


def test_unmatched_when_ean_missing():
    deals, unm = build_deals([make_retail(15.0, ean=None)], {"111": CEX_BASE})
    assert deals == []
    assert "missing EAN" in unm[0]["reason"]


def test_unmatched_when_ean_not_in_cex():
    deals, unm = build_deals([make_retail(15.0, ean="999")], {"111": CEX_BASE})
    assert deals == []
    assert "not in CeX" in unm[0]["reason"]


def test_delivery_subtracted_from_profit():
    deals, _ = build_deals([make_retail(15.0, delivery=3.0)], {"111": CEX_BASE})
    assert deals[0]["profit_voucher"] == 7.0


def test_saturation_high_when_stock_above_threshold():
    cex = {**CEX_BASE, "ecomQuantityOnHand": 50}
    deals, _ = build_deals([make_retail(15.0)], {"111": cex})
    assert deals[0]["saturation_risk"] == "high"


def test_saturation_medium():
    cex = {**CEX_BASE, "ecomQuantityOnHand": 15}
    deals, _ = build_deals([make_retail(15.0)], {"111": cex})
    assert deals[0]["saturation_risk"] == "medium"


def test_sorted_by_profit_voucher_desc():
    rows = [
        make_retail(20.0, ean="a", title="small"),
        make_retail(10.0, ean="b", title="big"),
    ]
    cex = {
        "a": {**CEX_BASE, "boxName": "small"},
        "b": {**CEX_BASE, "boxName": "big"},
    }
    deals, _ = build_deals(rows, cex)
    assert [d["title"] for d in deals] == ["big", "small"]
    assert deals[0]["profit_voucher"] > deals[1]["profit_voucher"]
