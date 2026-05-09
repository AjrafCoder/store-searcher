from scrapers.common import HostRateLimiter, extract_ean, is_plausible_ean


def test_extract_from_jsonld():
    html = '<script>{"@type":"Product","gtin13":"5030943125299","name":"Game"}</script>'
    assert extract_ean(html) == "5030943125299"


def test_extract_from_microdata_meta_tag():
    html = '<meta itemprop="gtin13" content="5030943125299">'
    assert extract_ean(html) == "5030943125299"


def test_extract_from_attribute_form():
    html = '<div gtin13="5030943125299"></div>'
    assert extract_ean(html) == "5030943125299"


def test_extract_returns_none_when_missing():
    assert extract_ean("<html>nothing here</html>") is None


def test_extract_ignores_too_short_numbers():
    html = '<script>{"gtin":"123"}</script>'
    assert extract_ean(html) is None


def test_is_plausible_ean_accepts_valid_lengths():
    assert is_plausible_ean("12345678")        # 8
    assert is_plausible_ean("5030943125299")   # 13
    assert is_plausible_ean("12345678901234")  # 14


def test_is_plausible_ean_rejects_garbage():
    assert not is_plausible_ean("123")
    assert not is_plausible_ean("12345abc")
    assert not is_plausible_ean(None)
    assert not is_plausible_ean("")


def test_rate_limiter_serialises_per_host():
    import time
    limiter = HostRateLimiter(0.05)
    start = time.monotonic()
    for _ in range(4):
        limiter.wait("example.com")
    elapsed = time.monotonic() - start
    # 4 waits * 0.05s gap = ~0.15s minimum (first call passes immediately).
    assert 0.10 <= elapsed < 0.5


def test_rate_limiter_independent_hosts_dont_block():
    import time
    limiter = HostRateLimiter(0.5)
    start = time.monotonic()
    limiter.wait("a.com")
    limiter.wait("b.com")
    limiter.wait("c.com")
    # Different hosts → no waiting, all return ~immediately.
    assert (time.monotonic() - start) < 0.1
