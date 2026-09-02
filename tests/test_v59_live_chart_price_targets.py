from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_live_chart_is_open_instrument_only_and_auto_refreshes():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    provider = (ROOT / "providers" / "yahoo.py").read_text(encoding="utf-8")
    assert '@st.fragment(run_every="60s")' in app
    assert 'render_live_intraday_chart(selected)' in app
    assert 'download_intraday_history(symbol, period="1d", interval="1m"' in app
    assert 'def download_intraday_history' in provider
    assert 'period="1d"' in provider
    assert 'interval: str = "1m"' in provider


def test_stock_cards_show_low_average_high_price_targets():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'Price Target Low' in app
    assert 'Price Target Average' in app
    assert 'Price Target High' in app
    assert 'ANALYST TARGETS' in app
    assert '_price_target_html(row)' in app
    assert 'if str(row.get("Type") or "").strip().upper() != "STOCK"' in app


def test_price_targets_refresh_and_persist_in_daily_snapshot():
    provider = (ROOT / "providers" / "yahoo.py").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
    assert 'def get_price_targets(' in provider
    assert 'analyst_price_targets' in provider
    assert 'def get_price_targets_many(' in provider
    assert 'provider.get_price_targets_many(stock_batch' in script
    assert '"Price Target Low"' in script
    assert '"Price Target Average"' in script
    assert '"Price Target High"' in script


def test_price_targets_have_upgrade_safe_lazy_fallback():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'cached_price_targets' in app
    assert 'def _hydrate_price_targets' in app
    assert 'card_rows = _hydrate_price_targets(card_rows, visible_stock_symbols)' in app
    assert 'table_df = _hydrate_price_targets(table_df, table_target_symbols)' in app


def test_213_etf_universe_is_still_exact():
    data = ROOT / "data"
    allow = pd.read_csv(data / "etf_allowlist.csv")
    generated = pd.read_csv(data / "default_universe.csv")
    bootstrap = pd.read_csv(data / "default_universe.bootstrap.csv")
    assert len(allow) == 213
    assert int((generated["Type"].astype(str).str.upper() == "ETF").sum()) == 213
    assert int((bootstrap["Type"].astype(str).str.upper() == "ETF").sum()) == 213
