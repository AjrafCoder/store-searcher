from scrapers.cex import _normalise, _platform_from_category


def test_ps5_category():
    assert _platform_from_category("Playstation5 Software") == "PS5"


def test_ps4_category():
    assert _platform_from_category("Playstation4 Software") == "PS4"


def test_switch_category():
    assert _platform_from_category("Switch Software") == "Switch"


def test_switch_2_takes_precedence_over_switch():
    assert _platform_from_category("Switch 2 Software") == "Switch 2"


def test_xbox_series_takes_precedence_over_xbox_one():
    assert _platform_from_category("Xbox Series X Games") == "Xbox Series"


def test_unknown_category_returns_none():
    assert _platform_from_category("DVD") is None
    assert _platform_from_category("") is None
    assert _platform_from_category(None) is None


def test_normalise_extracts_pricing_and_url():
    raw = {
        "boxId": "SPS5GTAV",
        "boxName": "GTA V",
        "categoryId": 1141,
        "categoryName": "Playstation5 Software",
        "superCatFriendlyName": "Gaming",
        "sellPrice": 30,
        "cashPrice": 15,
        "exchangePrice": 22,
        "ecomQuantityOnHand": 7,
    }
    out = _normalise(raw)
    assert out["platform"] == "PS5"
    assert out["sellPrice"] == 30.0
    assert out["exchangePrice"] == 22.0
    assert out["url"] == "https://uk.webuy.com/product-detail?id=SPS5GTAV"


def test_normalise_handles_missing_optional_fields():
    out = _normalise({"boxId": "X", "boxName": "Y"})
    assert out["platform"] is None
    assert out["sellPrice"] == 0.0
    assert out["ecomQuantityOnHand"] == 0
