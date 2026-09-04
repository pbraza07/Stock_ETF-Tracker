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

MARKER = (
    'MarketScope Portfolio Split Simulator v37 - v5.9.82 monthly reset + monthly start-year RB/NR depletion dashboard + continuous monthly start-year paths + start-year RB/NR depletion dashboard + split start-year strategies + persistent Build Simulation withdrawal tabs + annual and monthly reset views + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
)


def _hydrate_function():
    tree = ast.parse(APP)
    selected = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {
            "_valid_price_target", "_price_target_registry", "_remember_price_targets",
            "_apply_remembered_price_targets", "_hydrate_price_targets",
        }
    ]
    ns = {
        "pd": pd,
        "np": np,
        "PRICE_TARGET_COLS": ["Price Target Low", "Price Target Average", "Price Target High"],
        "format_et": lambda: "Sep 02, 2026 09:00 AM ET",
        "_PRICE_TARGET_REGISTRY_FALLBACK": {},
    }
    calls = []

    def fake_cached(symbols):
        calls.append(tuple(symbols))
        return {
            "CAT": {"low": 650.0, "mean": 725.0, "high": 810.0},
            "LLY": {"low": 900.0, "mean": 1100.0, "high": 1300.0},
        }

    class FakeProvider:
        def get_price_targets(self, symbol):
            return fake_cached((symbol,)).get(symbol, {})
    ns["cached_price_targets"] = fake_cached
    ns["provider"] = FakeProvider()
    exec(compile(ast.Module(body=selected, type_ignores=[]), "app.py", "exec"), ns)
    return ns["_hydrate_price_targets"], calls


def test_release_version_5964():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.11.2"
    assert "v5.9.66" in APP


def test_shared_hydrator_fills_low_average_high_and_preserves_other_rows():
    hydrate, calls = _hydrate_function()
    df = pd.DataFrame(
        [
            {
                "Symbol": "CAT",
                "Type": "Stock",
                "Price Target Low": np.nan,
                "Price Target Average": np.nan,
                "Price Target High": np.nan,
                "Price Target Updated ET": "—",
            },
            {
                "Symbol": "SPY",
                "Type": "ETF",
                "Price Target Low": np.nan,
                "Price Target Average": np.nan,
                "Price Target High": np.nan,
                "Price Target Updated ET": "—",
            },
        ]
    )
    out = hydrate(df, ["CAT", "SPY"])
    row = out.loc[out["Symbol"] == "CAT"].iloc[0]
    assert row["Price Target Low"] == 650.0
    assert row["Price Target Average"] == 725.0
    assert row["Price Target High"] == 810.0
    assert "Sep 02, 2026" in row["Price Target Updated ET"]
    assert calls == [("CAT",)]
    spy = out.loc[out["Symbol"] == "SPY"].iloc[0]
    assert pd.isna(spy["Price Target Average"])


def test_shared_hydrator_repairs_partial_target_range_not_only_all_blank():
    hydrate, calls = _hydrate_function()
    df = pd.DataFrame(
        [
            {
                "Symbol": "LLY",
                "Type": "Stock",
                "Price Target Low": 950.0,
                "Price Target Average": np.nan,
                "Price Target High": 1275.0,
                "Price Target Updated ET": "old",
            }
        ]
    )
    out = hydrate(df, ["LLY"])
    row = out.iloc[0]
    assert row["Price Target Low"] == 950.0
    assert row["Price Target Average"] == 1100.0
    assert row["Price Target High"] == 1275.0
    assert calls == [("LLY",)]


def test_all_major_app_surfaces_use_shared_target_hydration():
    assert "card_rows = _hydrate_price_targets(card_rows, visible_stock_symbols)" in APP
    assert "table_df = _hydrate_price_targets(table_df, table_target_symbols)" in APP
    assert "comparison_df = _hydrate_price_targets(comparison_df, comparison_symbols)" in APP
    assert "detail_source = _hydrate_price_targets(detail_source, (selected,))" in APP
    assert "portfolio_market = _hydrate_price_targets(market, tuple(selected_portfolio_symbols))" in APP
    assert "lookup_source = _hydrate_price_targets(market_df, symbols)" in APP


def test_pdf_saved_record_keeps_all_three_target_fields_and_forces_current_rebuild():
    assert APP.count(MARKER) >= 2
    for token in [
        '"price_target_low"',
        '"price_target_average"',
        '"price_target_high"',
    ]:
        assert token in APP
    assert 'f"LOW {low}   AVG/CONS {avg}   HIGH {high}"' in PDF


def test_provider_has_low_concurrency_batch_plus_individual_retry():
    assert "def get_price_targets_many" in YAHOO
    assert "workers = max(1, min(int(max_workers or 1), 4, len(symbols)))" in YAHOO
    assert "missing = [symbol for symbol in symbols if symbol not in output]" in YAHOO
    assert "values = self.get_price_targets(symbol)" in YAHOO
    assert "for pass_no in range(2)" in YAHOO


def test_scheduled_snapshot_persists_price_target_range():
    assert '"Price Target Low"' in SNAPSHOT
    assert '"Price Target Average"' in SNAPSHOT
    assert '"Price Target High"' in SNAPSHOT
    assert 'provider.get_price_targets_many(stock_batch, max_workers=3)' in SNAPSHOT


def test_bootstrap_schema_contains_target_columns():
    header = pd.read_csv(ROOT / "data" / "market_snapshot.bootstrap.csv", nrows=0).columns
    for col in ["Price Target Low", "Price Target Average", "Price Target High", "Price Target Updated ET"]:
        assert col in header
