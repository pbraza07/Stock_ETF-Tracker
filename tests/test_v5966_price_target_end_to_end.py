from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
YAHOO = (ROOT / "providers" / "yahoo.py").read_text(encoding="utf-8")
SNAPSHOT = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")


def test_release_version_5966():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.69"
    assert "v5.9.66" in APP


def test_provider_does_not_disable_info_fallback_when_analyst_endpoint_throws(monkeypatch):
    import providers.yahoo as yahoo_module
    from providers.yahoo import YahooFinanceProvider

    class FakeTicker:
        def get_analyst_price_targets(self):
            raise RuntimeError("temporary target endpoint failure")

        @property
        def analyst_price_targets(self):
            raise RuntimeError("property failure")

        def get_info(self):
            return {
                "targetLowPrice": 175.0,
                "targetMeanPrice": 210.0,
                "targetHighPrice": 245.0,
            }

    monkeypatch.setattr(yahoo_module.yf, "Ticker", lambda symbol: FakeTicker())
    values = YahooFinanceProvider().get_price_targets("TEST")
    assert values["low"] == 175.0
    assert values["mean"] == 210.0
    assert values["high"] == 245.0


def test_provider_uses_current_public_yfinance_method_first():
    assert "ticker.get_analyst_price_targets()" in YAHOO
    assert "ticker.analyst_price_targets" in YAHOO
    assert "ticker.get_info()" in YAHOO
    method_pos = YAHOO.index("ticker.get_analyst_price_targets()")
    property_pos = YAHOO.index("ticker.analyst_price_targets", method_pos)
    info_pos = YAHOO.index("ticker.get_info()", property_pos)
    assert method_pos < property_pos < info_pos


def test_provider_handles_nested_raw_target_payloads(monkeypatch):
    import providers.yahoo as yahoo_module
    from providers.yahoo import YahooFinanceProvider

    class FakeTicker:
        def get_analyst_price_targets(self):
            return {
                "low": {"raw": 100.0},
                "mean": {"raw": 125.0},
                "high": {"raw": 150.0},
                "median": {"raw": 124.0},
            }

        @property
        def analyst_price_targets(self):
            return {}

        def get_info(self):
            return {}

    monkeypatch.setattr(yahoo_module.yf, "Ticker", lambda symbol: FakeTicker())
    values = YahooFinanceProvider().get_price_targets("RAW")
    assert values["low"] == 100.0
    assert values["mean"] == 125.0
    assert values["high"] == 150.0


def _app_functions(*names):
    tree = ast.parse(APP)
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in set(names)
    ]
    return nodes


def test_snapshot_quality_prefers_target_populated_candidate_when_history_is_equal():
    nodes = _app_functions(
        "_annual_coverage_stats",
        "_price_target_coverage_stats",
        "_populated_price_count",
        "_snapshot_quality_key",
    )
    ns = {
        "pd": pd,
        "np": np,
        "PRICE_TARGET_COLS": ["Price Target Low", "Price Target Average", "Price Target High"],
        "YEAR_RETURN_COLS": ["2025", "2024"],
        "OLDEST_FIVE_YEAR_COLS": ["2025", "2024"],
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "app.py", "exec"), ns)

    base = pd.DataFrame([
        {
            "Symbol": "AAPL", "Type": "Stock", "Price": 200.0,
            "2025": 10.0, "2024": 20.0,
            "Price Target Low": np.nan,
            "Price Target Average": np.nan,
            "Price Target High": np.nan,
        }
    ])
    targets = base.copy()
    targets.loc[0, ["Price Target Low", "Price Target Average", "Price Target High"]] = [180.0, 220.0, 250.0]
    assert ns["_snapshot_quality_key"](targets) > ns["_snapshot_quality_key"](base)


def test_hydrator_bypasses_cached_empty_result_with_direct_symbol_retry():
    nodes = _app_functions(
        "_valid_price_target", "_price_target_registry", "_remember_price_targets",
        "_apply_remembered_price_targets", "_hydrate_price_targets"
    )
    calls = []

    class FakeProvider:
        def get_price_targets(self, symbol):
            calls.append(symbol)
            return {
                "low": 90.0,
                "mean": 110.0,
                "high": 130.0,
                "source": "Yahoo Finance analyst consensus",
            }

    ns = {
        "pd": pd,
        "np": np,
        "PRICE_TARGET_COLS": ["Price Target Low", "Price Target Average", "Price Target High"],
        "format_et": lambda: "Sep 02, 2026 10:00 AM EDT",
        "cached_price_targets": lambda symbols: {},
        "provider": FakeProvider(),
        "_PRICE_TARGET_REGISTRY_FALLBACK": {},
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "app.py", "exec"), ns)
    frame = pd.DataFrame([{
        "Symbol": "TEST",
        "Type": "Stock",
        "Price Target Low": np.nan,
        "Price Target Average": np.nan,
        "Price Target High": np.nan,
    }])
    out = ns["_hydrate_price_targets"](frame, ["TEST"])
    row = out.iloc[0]
    assert calls == ["TEST"]
    assert row["Price Target Low"] == 90.0
    assert row["Price Target Average"] == 110.0
    assert row["Price Target High"] == 130.0
    assert row["Price Target Source"] == "Yahoo Finance analyst consensus"


def test_table_view_and_every_major_surface_use_same_hydrator():
    for token in [
        "card_rows = _hydrate_price_targets(card_rows, visible_stock_symbols)",
        "detail_source = _hydrate_price_targets(detail_source, (selected,))",
        "table_df = _hydrate_price_targets(table_df, table_target_symbols)",
        "comparison_df = _hydrate_price_targets(comparison_df, comparison_symbols)",
        "portfolio_market = _hydrate_price_targets(market, tuple(selected_portfolio_symbols))",
        "lookup_source = _hydrate_price_targets(market_df, symbols)",
    ]:
        assert token in APP


def test_pdf_first_page_reads_same_saved_low_average_high_keys():
    for token in [
        '"price_target_low":',
        '"price_target_average":',
        '"price_target_high":',
        'item.get("price_target_low")',
        'item.get("price_target_average")',
        'item.get("price_target_high")',
        'f"LOW {low}   AVG/CONS {avg}   HIGH {high}"',
    ]:
        assert token in APP or token in PDF


def test_snapshot_has_post_history_target_completion_pass_and_metadata():
    assert "v5.9.66 target completion pass" in SNAPSHOT
    assert "provider.get_price_targets_many(target_batch, max_workers=1)" in SNAPSHOT
    assert '"Price Target Source"' in SNAPSHOT
    assert '"price_target_complete_stock_rows"' in SNAPSHOT
    assert '"price_target_populated_cells"' in SNAPSHOT


def test_pdf_contract_bumped_to_v25():
    marker = (
        "MarketScope Portfolio Split Simulator v27 - v5.9.69 saved-card inline withdrawal summary + "
        "PDF withdrawal summary + Market Table target transcription + responsive withdrawal KPI layout + "
        "required instrument market data on page 1"
    )
    assert APP.count(marker) >= 2


def test_market_table_places_targets_next_to_price_and_shows_source():
    order = APP.index('"Symbol", "Name", "Type", "Sector", "Industry", "Price", "Market Cap ($B)"')
    target = APP.index('"Price Target Low", "Price Target Average", "Price Target High", "Avg Target Implied %"', order)
    rating = APP.index('"Analyst Rating", "Worst Year"', target)
    assert order < target < rating
    assert '"Price Target Source", "Price Target Updated ET"' in APP
    assert 'st.column_config.TextColumn("Target Source")' in APP
    assert 'st.column_config.TextColumn("Target Updated ET")' in APP
