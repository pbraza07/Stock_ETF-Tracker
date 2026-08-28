from pathlib import Path

import pandas as pd


def test_v592_ui_contract():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    css = (root / "styles.css").read_text(encoding="utf-8")
    assert 'def cached_etf_holdings' in app
    assert 'def _holdings_panel_html' in app
    assert 'key=f"holdings_{symbol}_{page_start}"' in app
    assert 'prev_cards_bottom' in app
    assert 'next_cards_bottom' in app
    assert 'TOP 10 HOLDINGS' in app
    assert 'TOP 5 HOLDINGS' in app
    assert '.holdings-panel' in css


def test_top_holdings_10_then_5(monkeypatch):
    from providers import yahoo as yahoo_module

    def make_frame(n):
        return pd.DataFrame(
            {
                "Name": [f"Company {i}" for i in range(n)],
                "Holding Percent": [0.10 - i * 0.001 for i in range(n)],
            },
            index=pd.Index([f"T{i}" for i in range(n)], name="Symbol"),
        )

    class FakeFunds:
        def __init__(self, n):
            self.top_holdings = make_frame(n)

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol
            self.funds_data = FakeFunds(10 if symbol == "TEN" else 8)

    monkeypatch.setattr(yahoo_module.yf, "Ticker", FakeTicker)
    provider = yahoo_module.YahooFinanceProvider()

    ten = provider.get_top_holdings("TEN")
    eight = provider.get_top_holdings("EIGHT")
    assert len(ten) == 10
    assert len(eight) == 5
    assert ten[0]["symbol"] == "T0"
    assert ten[0]["weight_pct"] == 10.0
