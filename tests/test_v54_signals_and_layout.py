from pathlib import Path

import numpy as np
import pandas as pd

from analytics import calculate_buy_signals, calculate_performance


def _long_history():
    idx = pd.bdate_range("2018-01-02", periods=2200)
    x = np.arange(len(idx), dtype=float)
    # Upward long-term trend with enough oscillation to avoid a permanently overbought RSI.
    close = 100 + 0.05 * x + 2.0 * np.sin(x / 12.0) + 0.5 * np.sin(x / 3.0)
    return pd.DataFrame({"Close": close}, index=idx)


def test_three_year_and_one_year_average_are_computed():
    perf = calculate_performance(_long_history())
    assert perf.avg_1y is not None
    assert perf.avg_3y is not None
    assert perf.avg_5y is not None


def test_strong_buy_can_create_long_fundamental_signal():
    sig = calculate_buy_signals(_long_history(), analyst_rating="Strong Buy", instrument_type="Stock")
    assert sig.fundamental_buy is True
    assert sig.long_buy is True
    assert "Nasdaq Strong Buy" in sig.reasons


def test_main_table_contract_matches_requested_return_order_and_omits_removed_columns():
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    start = app.index("DISPLAY_COLS = [")
    end = app.index("]\nfiltered = apply_dynamic_filters", start)
    block = app[start:end]
    for removed in ["Inception Date", "Exchange", "Return Basis", "Rating Source", "Data As Of", "Rating Updated ET", "Snapshot Updated ET"]:
        assert removed not in block
    assert '"1D", "1M", "3M", "6M", "YTD"' in (ROOT := Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "*PERF_COLS" in block


def test_main_navigator_uses_cards_instead_of_dataframe():
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    card_section = app[app.index("with card_view_tab:"):app.index("with table_view_tab:")]
    assert "instrument-card" in card_section
    assert "st.dataframe(" not in card_section
    assert "Short Buy" in card_section and "Long Buy" in card_section
