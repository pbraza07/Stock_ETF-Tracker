from providers.nasdaq import NasdaqScreenerProvider


def test_rating_normalization():
    p = NasdaqScreenerProvider()
    assert p.normalize_rating("strong_buy") == "Strong Buy"
    assert p.normalize_rating("Buy") == "Buy"
    assert p.normalize_rating("neutral") == "Hold"
    assert p.normalize_rating("underperform") == "Sell"
    assert p.normalize_rating("strong-sell") == "Strong Sell"
    assert p.normalize_rating(None) == "Not Rated"


def test_symbol_normalization():
    assert NasdaqScreenerProvider.normalize_symbol("brk/b") == "BRK-B"
    assert NasdaqScreenerProvider.normalize_symbol("brk.b") == "BRK-B"
