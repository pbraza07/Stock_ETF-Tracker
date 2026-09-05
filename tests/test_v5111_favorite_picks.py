from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from favorite_picks import (
    PERCENTILES,
    build_favorite_picks,
    favorite_candidate_symbols,
    screen_favorite_candidates,
)


ROOT = Path(__file__).resolve().parents[1]
YEARS = [str(year) for year in range(2025, 2013, -1)]
STOCKS = ["AAA", "AAB", "AAC", "AAD", "BBB", "BBC", "BBD", "BBE"]


def market_fixture() -> pd.DataFrame:
    rows = []
    for index, symbol in enumerate(STOCKS):
        sector = "Technology" if index < 4 else "Health Care"
        row = {
            "Symbol": symbol,
            "Name": f"Company {symbol}",
            "Type": "Stock",
            "Sector": sector,
            "Price": 95.0 + index * 8.0,
            "MarketCap": 500_000_000_000 - index * 25_000_000_000,
            "1M": 1.0 + index * 0.2,
            "3M": 2.5 + index * 0.4,
            "6M": 4.0 + index * 0.7,
            "YTD": 6.0 + index * 0.8,
            "Analyst Rating": "Buy" if index % 3 else "Hold",
            "Short Buy": index % 2 == 0,
            "Long Buy": index % 3 == 0,
            "Fundamental Buy": index % 4 == 0,
        }
        rng = np.random.default_rng(1000 + index)
        for year in YEARS:
            row[year] = float(rng.normal(8.0 + index * 0.6, 12.0 + index))
        rows.append(row)
    etf = rows[0].copy()
    etf.update({"Symbol": "QQQX", "Name": "Excluded Test ETF", "Type": "ETF"})
    rows.append(etf)
    insufficient = rows[0].copy()
    insufficient.update({"Symbol": "NEW", "Name": "Short History Stock", "Sector": "Industrials"})
    for year in YEARS[2:]:
        insufficient[year] = np.nan
    rows.append(insufficient)
    return pd.DataFrame(rows)


def price_history(seed: int, drift: float, volatility: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-01-02", periods=320, freq="B")
    close = 100.0 * np.exp(
        np.cumsum(rng.normal(drift / 252.0, volatility / np.sqrt(252.0), len(dates)))
    )
    return pd.DataFrame(
        {"Close": close, "Volume": np.full(len(dates), 1_000_000 + seed * 10_000)},
        index=dates,
    )


def live_fixture() -> dict:
    histories = {
        symbol: price_history(index + 1, 0.07 + index * 0.006, 0.17 + index * 0.01)
        for index, symbol in enumerate(STOCKS)
    }
    histories.update(
        {
            "SPY": price_history(80, 0.07, 0.16),
            "QQQ": price_history(81, 0.08, 0.21),
            "IWM": price_history(82, 0.06, 0.23),
            "^VIX": price_history(83, 0.00, 0.35),
        }
    )
    fundamentals = {}
    for index, symbol in enumerate(STOCKS):
        fundamentals[symbol] = {
            "instrument_type": "Stock",
            "forward_pe": 16.0 + index,
            "trailing_pe": 18.0 + index,
            "revenue_growth": 0.06 + index * 0.005,
            "earnings_growth": 0.08 + index * 0.006,
            "operating_margin": 0.18,
            "free_cash_flow": 1_000_000_000 + index * 10_000_000,
            "debt_to_equity": 42.0,
            "return_on_equity": 0.20,
            "eps_revision_direction": 0.20,
            "market_cap": 500_000_000_000 - index * 25_000_000_000,
            "sector": "Technology" if index < 4 else "Health Care",
            "retrieved_at": "2026-09-04T12:00:00+00:00",
        }
    return {
        "retrieved_at": "2026-09-04T12:00:00+00:00",
        "history_through": "2026-09-03",
        "histories": histories,
        "prices": {symbol: 100.0 + index for index, symbol in enumerate(STOCKS)},
        "fundamentals": fundamentals,
        "macro": {
            "federal_funds_rate": {"value": 3.5, "observation_date": "2026-08-01"},
            "yield_spread_10y_2y": {"value": 0.5, "observation_date": "2026-09-03"},
            "yield_spread_10y_3m": {"value": 0.3, "observation_date": "2026-09-03"},
            "credit_spread": {"value": 1.5, "observation_date": "2026-09-03"},
            "cpi": {
                "observations": [{"value": 100.0 + i * 0.2} for i in range(14)],
                "observation_date": "2026-08-01",
            },
            "unemployment_rate": {
                "observations": [{"value": 4.0}] * 4,
                "observation_date": "2026-08-01",
            },
            "payrolls": {
                "observations": [{"value": 100.0}, {"value": 100.15}],
                "observation_date": "2026-08-01",
            },
            "real_gdp": {
                "observations": [{"value": 100.0 + i} for i in range(5)],
                "observation_date": "2026-06-30",
            },
        },
        "breadth_symbols": STOCKS,
        "failures": [],
    }


def build_result(seed: int = 4242) -> dict:
    return build_favorite_picks(
        market_fixture(),
        YEARS,
        live_context=live_fixture(),
        projection_years=5,
        simulations=160,
        random_seed=seed,
        shortlist_per_sector=4,
        data_as_of="2026-09-04 08:00 ET",
    )


def test_release_and_main_navigation_include_favorite_picks():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    css = (ROOT / "styles.css").read_text(encoding="utf-8")
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.11.6"
    assert '"Favorite Picks"' in app
    assert '"Pick Fav"' in app
    assert "build_favorite_picks" in app
    assert ".favorite-regime-grid" in css
    assert "@media (max-width: 720px)" in css


def test_screen_uses_stocks_only_and_requires_credible_completed_history():
    screened = screen_favorite_candidates(market_fixture(), YEARS, shortlist_per_sector=4)
    assert set(screened["Type"]) == {"Stock"}
    assert "QQQX" not in set(screened["Symbol"])
    assert "NEW" not in set(screened["Symbol"])
    assert screened["Observed Years"].min() >= 3
    assert set(favorite_candidate_symbols(market_fixture(), YEARS, 4)) == set(STOCKS)


def test_result_selects_at_most_two_per_sector_and_explains_each_pick():
    result = build_result()
    table = result["table"]
    assert result["eligible_stock_count"] == len(STOCKS)
    assert result["sector_count"] == 2
    assert result["pick_count"] == 4
    assert table.groupby("Sector")["Symbol"].count().max() == 2
    assert table.groupby("Sector")["Sector Rank"].apply(list).tolist() == [[1, 2], [1, 2]]
    assert table["Why Selected"].str.len().gt(20).all()
    assert table["Key Risk"].str.len().gt(20).all()
    assert table["Data As Of"].eq("2026-09-04 08:00 ET").all()


def test_favorite_projection_percentiles_are_present_and_ascending():
    table = build_result()["table"]
    columns = [f"P{percentile} 5Y CAGR %" for percentile in PERCENTILES]
    assert list(PERCENTILES) == [10, 25, 50, 75, 90]
    assert table.columns.get_loc(columns[0]) < table.columns.get_loc(columns[-1])
    assert np.all(np.diff(table[columns].to_numpy(dtype=float), axis=1) >= -1e-10)
    assert not any(column.startswith("P5 ") or column.startswith("P95 ") for column in table.columns)


def test_fixed_seed_produces_the_same_favorites_and_model_values():
    first = build_result(seed=8181)
    second = build_result(seed=8181)
    assert_frame_equal(first["table"], second["table"])
    assert first["random_seed"] == second["random_seed"] == 8181
    assert first["ensemble_weights"] == second["ensemble_weights"]


def test_live_context_conditions_the_ranking_and_reports_auditable_state():
    result = build_result()
    state = result["market_state"]
    assert state["live_conditioning_active"] is True
    assert np.isclose(sum(state["regime_probabilities"].values()), 100.0)
    assert set(result["ensemble_weights"]) == {
        "Adaptive Regime Monte Carlo",
        "Historical Block Bootstrap",
        "Factor/CMA Model",
    }
    assert result["walk_forward_validation"]["no_future_leakage"] is True
    assert result["table"]["Live Data Quality"].isin(["High", "Medium"]).all()


def test_historical_fallback_still_returns_picks_and_labels_low_confidence():
    result = build_favorite_picks(
        market_fixture(),
        YEARS,
        live_context={"failures": ["Live provider unavailable"]},
        projection_years=5,
        simulations=120,
        random_seed=55,
        shortlist_per_sector=3,
    )
    assert result["pick_count"] == 4
    assert result["market_state"]["live_conditioning_active"] is False
    assert result["table"]["Model Confidence"].eq("Low").all()
    assert any("Live provider unavailable" in warning for warning in result["warnings"])


def test_sector_with_one_eligible_stock_is_kept_and_warned():
    market = market_fixture()
    one = market.loc[market["Symbol"].eq("AAA")].copy()
    one.loc[:, "Sector"] = "Utilities"
    result = build_favorite_picks(one, YEARS, simulations=100, random_seed=77, shortlist_per_sector=4)
    assert result["pick_count"] == 1
    assert result["table"].iloc[0]["Sector Rank"] == 1
    assert any("only 1 eligible stock" in warning for warning in result["warnings"])
