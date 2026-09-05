from __future__ import annotations
# v5.11.7: recovered dual Top 12 rankings and presentation performance release.

import json
import os
import subprocess
import sys
from pathlib import Path
from html import escape
from typing import Dict, List

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from analytics import (
    as_percent,
    calculate_buy_signals,
    calculate_calendar_year_returns,
    calculate_monthly_returns,
    calculate_performance,
    completed_year_labels,
)
from history_config import (
    ANNUAL_HISTORY_FIRST_YEAR,
    ANNUAL_HISTORY_START,
    annual_history_year_count,
    annual_history_year_labels,
    annual_horizon_options,
    chart_year_labels,
    latest_completed_year,
    rolling_completed_year_labels,
)
from persistence import (
    format_et,
    load_remote_csv,
    load_remote_favorite_picks_history,
    load_remote_metadata,
    load_remote_snapshot,
    load_remote_universe_metadata,
    load_remote_universe_change_history,
    now_et,
    persist_snapshot,
    persist_favorite_picks_history,
    persist_universe_refresh,
)
from portfolio_simulations import (
    add_simulation,
    build_portfolio_simulation_pdf,
    delete_simulation,
    load_saved_simulations,
    persist_saved_simulations,
    safe_filename,
    simulation_id,
)
from pdf_storage import (
    delete_pdf_artifact,
    load_pdf_artifact,
    pdf_viewer_url,
    persist_pdf_artifact,
)
from future_projection import projection_payload_from_simulator
from future_projection_live import fetch_live_projection_context
from future_projection_ui import render_future_projection
from favorite_picks import build_favorite_picks, favorite_candidate_symbols
from favorite_picks_history import (
    favorite_change_history_frame,
    favorite_run_history_frame,
    merge_favorite_picks_ledgers,
    record_favorite_picks_run,
)
from providers import YahooFinanceProvider
from providers.nasdaq import NasdaqScreenerProvider
from universe import is_render_runtime, load_default_universe

BASE_DIR = Path(__file__).resolve().parent

def _marketscope_version() -> str:
    try:
        return (BASE_DIR / "VERSION.txt").read_text(encoding="utf-8").strip() or "unknown"
    except Exception:
        return "unknown"

MARKETSCOPE_VERSION = _marketscope_version()
# v5.9.66: manual Nasdaq-universe refresh + durable refresh timestamp recovery.
SNAPSHOT_FILE = BASE_DIR / "data" / "market_snapshot.csv"
BOOTSTRAP_SNAPSHOT_FILE = BASE_DIR / "data" / "market_snapshot.bootstrap.csv"
SNAPSHOT_META_FILE = BASE_DIR / "data" / "snapshot_metadata.json"
BOOTSTRAP_META_FILE = BASE_DIR / "data" / "snapshot_metadata.bootstrap.json"
UNIVERSE_META_FILE = BASE_DIR / "data" / "universe_metadata.json"
BOOTSTRAP_UNIVERSE_META_FILE = BASE_DIR / "data" / "universe_metadata.bootstrap.json"
UNIVERSE_CHANGE_HISTORY_FILE = BASE_DIR / "data" / "universe_change_history.json"
FAVORITE_PICKS_HISTORY_FILE = BASE_DIR / "data" / "favorite_picks_history.json"
FAVORITE_PICKS_HISTORY_BOOTSTRAP_FILE = BASE_DIR / "data" / "favorite_picks_history.bootstrap.json"
MONTHLY_RETURNS_FILE = BASE_DIR / "data" / "monthly_returns_10y.csv"
MONTHLY_RETURNS_REPO_PATH = "data/monthly_returns_10y.csv"
MONTHLY_RETURNS_FULL_FILE = BASE_DIR / "data" / "monthly_returns_full_history.csv"
MONTHLY_RETURNS_FULL_REPO_PATH = "data/monthly_returns_full_history.csv"
# v5.9.58 compatibility fallback; v5.9.58+ writes the future-proof full-history file.
MONTHLY_RETURNS_25Y_FILE = BASE_DIR / "data" / "monthly_returns_25y.csv"
MONTHLY_RETURNS_25Y_REPO_PATH = "data/monthly_returns_25y.csv"

ANNUAL_HISTORY_YEARS = annual_history_year_count(as_of=now_et())
YEAR_RETURN_COLS = annual_history_year_labels(as_of=now_et())
ANNUAL_HORIZON_OPTIONS = annual_horizon_options(as_of=now_et())
LATEST_COMPLETED_YEAR = latest_completed_year(as_of=now_et())
OLDEST_FIVE_YEAR_COLS = list(YEAR_RETURN_COLS[-5:])
PERF_COLS = ["1D", "1M", "3M", "6M", "YTD", *YEAR_RETURN_COLS]
ALL_RETURN_COLS = ["Since Inception"] + PERF_COLS

# v5.9.37: one display convention for every year-based timeframe across all tabs.
# Internal keys remain unchanged so calculations, saved state, URLs, and historical data stay compatible.
_TIMEFRAME_YEAR_BY_HORIZON = {f"{i}Y": year for i, year in enumerate(YEAR_RETURN_COLS, start=1)}
_TIMEFRAME_HORIZON_BY_YEAR = {year: f"{i}Y" for i, year in enumerate(YEAR_RETURN_COLS, start=1)}

def timeframe_display_label(value) -> str:
    text = str(value or "")
    if text in _TIMEFRAME_YEAR_BY_HORIZON:
        return f"{text} ({_TIMEFRAME_YEAR_BY_HORIZON[text]})"
    if text in _TIMEFRAME_HORIZON_BY_YEAR:
        return f"{_TIMEFRAME_HORIZON_BY_YEAR[text]} ({text})"
    return text

def timeframe_column_config(columns):
    return {col: st.column_config.NumberColumn(timeframe_display_label(col), format="%.2f%%") for col in columns}

def worst_completed_year_label(row: pd.Series) -> str:
    """Return the weakest available completed calendar year as '-12.34% (YYYY)'."""
    worst_year = None
    worst_return = None
    for year in YEAR_RETURN_COLS:
        value = pd.to_numeric(pd.Series([row.get(year)]), errors="coerce").iloc[0]
        if pd.isna(value) or not np.isfinite(value):
            continue
        value = float(value)
        if worst_return is None or value < worst_return:
            worst_year = str(year)
            worst_return = value
    if worst_year is None or worst_return is None:
        return "N/A"
    return f"{worst_return:+.2f}% ({worst_year})"
SIGNAL_COLS = ["Short Buy", "Long Buy", "Fundamental Buy"]
PRICE_TARGET_COLS = ["Price Target Low", "Price Target Average", "Price Target High"]
RATINGS = ["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell", "Not Rated"]
MIN_STOCK_MARKET_CAP = 100_000_000_000.0

# v5.9.53: ranked portfolio families are hidden behind separate buttons; recession-balanced presets added.
COMBO_5Y_PROFIT_FILE = BASE_DIR / "data" / "top200_profit_generators_5y.csv"
COMBO_5Y_WORST_FILE = BASE_DIR / "data" / "top200_best_worst_year_5y.csv"
COMBO_10Y_PROFIT_FILE = BASE_DIR / "data" / "top200_profit_generators_10y.csv"
COMBO_10Y_WORST_FILE = BASE_DIR / "data" / "top200_best_worst_year_10y.csv"
COMBO_10Y_REBALANCED_WITHDRAWAL_FILE = BASE_DIR / "data" / "top100_rebalanced_withdrawal_10y.csv"
COMBO_10Y_NOT_REBALANCED_WITHDRAWAL_FILE = BASE_DIR / "data" / "top100_not_rebalanced_withdrawal_10y.csv"
COMBO_10Y_REBALANCED_WITHDRAWAL_160K_FILE = BASE_DIR / "data" / "top100_rebalanced_withdrawal_10y_160k_max5.csv"
COMBO_10Y_NOT_REBALANCED_WITHDRAWAL_160K_FILE = BASE_DIR / "data" / "top100_not_rebalanced_withdrawal_10y_160k_max5.csv"
COMBO_20Y_REBALANCED_WITHDRAWAL_160K_FILE = BASE_DIR / "data" / "top250_rebalanced_withdrawal_20y_160k_max10.csv"
COMBO_20Y_NOT_REBALANCED_WITHDRAWAL_160K_FILE = BASE_DIR / "data" / "top250_not_rebalanced_withdrawal_20y_160k_max10.csv"
COMBO_10Y_REBALANCED_MONTHLY_WITHDRAWAL_FILE = BASE_DIR / "data" / "top100_rebalanced_monthly_withdrawal_10y_no_hwm.csv"
COMBO_10Y_NOT_REBALANCED_MONTHLY_WITHDRAWAL_FILE = BASE_DIR / "data" / "top100_not_rebalanced_monthly_withdrawal_10y_no_hwm.csv"
COMBO_RECESSION_REBALANCED_FILE = BASE_DIR / "data" / "top100_recession_balanced_rebalanced_10y.csv"
COMBO_RECESSION_NOT_REBALANCED_FILE = BASE_DIR / "data" / "top100_recession_balanced_not_rebalanced_10y.csv"
COMBO_SOURCE_FILE = BASE_DIR / "data" / "portfolio_combo_source_latest.csv"
COMBO_WITHDRAWAL_START = 300_000.0
COMBO_WITHDRAWAL_ANNUAL = 85_000.0
COMBO_WITHDRAWAL_ANNUAL_160K = 160_000.0
COMBO_WITHDRAWAL_MONTHLY = 5_000.0
COMBO_RANK_YEARS_BY_PERIOD = {
    "5Y": rolling_completed_year_labels(5, as_of=now_et()),
    "10Y": rolling_completed_year_labels(10, as_of=now_et()),
}

st.set_page_config(
    page_title="MarketScope — Stock & ETF Performance",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(f"<style>{(BASE_DIR / 'styles.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

provider = YahooFinanceProvider()
nasdaq = NasdaqScreenerProvider()
default_universe = load_default_universe()
default_meta = default_universe.set_index("Symbol").to_dict(orient="index")
IS_RENDER = is_render_runtime()


def _query_list(key: str) -> List[str]:
    try:
        raw = st.query_params.get(key, "")
    except Exception:
        return []
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    return list(dict.fromkeys(x.strip().upper() for x in str(raw).split(",") if x.strip()))


def _query_scalar_early(key: str, default: str = "") -> str:
    try:
        raw = st.query_params.get(key, default)
    except Exception:
        return default
    if isinstance(raw, list):
        raw = raw[0] if raw else default
    text = str(raw or "").strip()
    return text if text else default


def _query_csv_early(key: str) -> list[str]:
    text = _query_scalar_early(key, "")
    return [item for item in (x.strip() for x in text.split(",")) if item]


def _save_extras_to_url() -> None:
    if not IS_RENDER:
        return
    extras = st.session_state.extra_symbols
    if extras:
        st.query_params["extra"] = ",".join(extras[:100])
    else:
        try:
            del st.query_params["extra"]
        except Exception:
            pass


if "extra_symbols" not in st.session_state:
    st.session_state.extra_symbols = _query_list("extra")
if "live_prices" not in st.session_state:
    st.session_state.live_prices = {}
if "manual_refreshed_at" not in st.session_state:
    st.session_state.manual_refreshed_at = None
if "session_rows" not in st.session_state:
    st.session_state.session_rows = {}
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "comparison_search_result_query" not in st.session_state:
    st.session_state.comparison_search_result_query = ""
if "comparison_search_message" not in st.session_state:
    st.session_state.comparison_search_message = None
if "persistence_message" not in st.session_state:
    st.session_state.persistence_message = None
if "last_refresh_summary" not in st.session_state:
    st.session_state.last_refresh_summary = None
if "universe_refresh_message" not in st.session_state:
    st.session_state.universe_refresh_message = None
if "universe_change_history_open" not in st.session_state:
    st.session_state.universe_change_history_open = False
if "favorite_picks_history_open" not in st.session_state:
    st.session_state.favorite_picks_history_open = False
if "favorite_picks_history_message" not in st.session_state:
    st.session_state.favorite_picks_history_message = None
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = None
if "card_page" not in st.session_state:
    try:
        st.session_state.card_page = max(0, int(_query_scalar_early("card_page", "0")))
    except ValueError:
        st.session_state.card_page = 0
if "card_sort_choice" not in st.session_state:
    st.session_state.card_sort_choice = _query_scalar_early("sort_choice", "Market Cap")
if "card_sort_ascending" not in st.session_state:
    st.session_state.card_sort_ascending = _query_scalar_early("sort_asc", "0").lower() in {"1", "true", "yes"}
if "sort_menu_open" not in st.session_state:
    st.session_state.sort_menu_open = False
if "scroll_to_chart" not in st.session_state:
    st.session_state.scroll_to_chart = False
if "news_symbol" not in st.session_state:
    st.session_state.news_symbol = None
if "holdings_symbol" not in st.session_state:
    st.session_state.holdings_symbol = None
if "comparison_detail_symbol" not in st.session_state:
    st.session_state.comparison_detail_symbol = None
if "portfolio_symbols" not in st.session_state:
    st.session_state.portfolio_symbols = [x.upper() for x in _query_csv_early("portfolio")]
if "simulation_library_open" not in st.session_state:
    st.session_state.simulation_library_open = True
if "pending_delete_simulation" not in st.session_state:
    st.session_state.pending_delete_simulation = None
if "simulation_library_message" not in st.session_state:
    st.session_state.simulation_library_message = None
if "compare_symbols" not in st.session_state:
    st.session_state.compare_symbols = []
if "stock_compare_selector" not in st.session_state:
    st.session_state.stock_compare_selector = []
if "compare_page" not in st.session_state:
    st.session_state.compare_page = 0
if "buy_signal_alerts_open" not in st.session_state:
    st.session_state.buy_signal_alerts_open = False
if "portfolio_simulator_open" not in st.session_state:
    st.session_state.portfolio_simulator_open = False
if "portfolio_manager_open" not in st.session_state:
    st.session_state.portfolio_manager_open = False
if "combo_autoload_message" not in st.session_state:
    st.session_state.combo_autoload_message = None
if "market_table_price_targets" not in st.session_state:
    # Exact in-session bridge from Market Table target values to PDF page 1.
    st.session_state.market_table_price_targets = {}


def _queue_current_portfolio_for_future_projection() -> None:
    """Bridge the current historical/ranked portfolio into Future Projection."""
    payload = projection_payload_from_simulator(dict(st.session_state))
    if len(payload.get("holdings") or []) != 4:
        return
    st.session_state.future_projection_pending_payload = payload
    st.session_state.future_projection_focus = True


@st.cache_data(show_spinner=False)
def _load_ranked_combo_file(path_text: str) -> pd.DataFrame:
    path = Path(path_text)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    if df.empty or "Combo" not in df.columns:
        return pd.DataFrame()
    return df


def _load_actual_monthly_ranked_combo_file(path_text: str) -> pd.DataFrame:
    """Use only ranking files generated from real monthly market history."""
    path = Path(path_text)
    candidates: list[pd.DataFrame] = []
    local = _load_ranked_combo_file(path_text)
    if not local.empty:
        candidates.append(local)
    remote = load_remote_csv(f"data/{path.name}", timeout=12)
    if remote is not None and not remote.empty:
        candidates.append(remote)
    for frame in reversed(candidates):  # prefer remote/newer
        if frame.empty or "Combo" not in frame.columns:
            continue
        if _monthly_csv_actual(frame):
            return frame
    return pd.DataFrame()


def _ranked_combo_symbols(row) -> list[str]:
    symbols = []
    for idx in range(1, 5):
        value = str(row.get(f"Stock {idx}") or "").strip().upper()
        if value and value not in symbols:
            symbols.append(value)
    return symbols


def _ranked_combo_label(row, mode: str) -> str:
    rank = int(row.get("Rank") or 0)
    combo = str(row.get("Combo") or "—")
    try:
        profit = float(row.get("Total Profit ($)"))
    except Exception:
        profit = 0.0
    try:
        worst = float(row.get("Worst Year %"))
    except Exception:
        worst = float("nan")
    worst_year = str(row.get("Worst Year") or "—")
    if mode == "worst":
        return f"#{rank} {combo} • Worst {worst:+.2f}% ({worst_year}) • Profit ${profit:,.0f}"
    return f"#{rank} {combo} • Profit ${profit:,.0f} • Worst {worst:+.2f}% ({worst_year})"

def _apply_ranked_combo_selection(select_key: str, lookup_key: str, ranking_name: str, period: str) -> None:
    selected = st.session_state.get(select_key)
    lookup = st.session_state.get(lookup_key) or {}
    symbols = list(lookup.get(selected) or [])
    if len(symbols) != 4:
        return
    period = str(period or "10Y").upper()
    if period not in {"5Y", "10Y"}:
        period = "10Y"
    st.session_state.portfolio_symbols = symbols
    st.session_state.portfolio_symbol_picker = symbols
    st.session_state.portfolio_period = period
    st.session_state.portfolio_allocation_mode = "Equal split"
    st.session_state.portfolio_include_ytd = False
    st.session_state.combo_autoload_message = (
        f"Loaded {ranking_name}: {' + '.join(symbols)}. Simulator set to {period} / Equal split."
    )


def _ranked_withdrawal_combo_label(row, strategy: str) -> str:
    rank = int(row.get("Rank") or 0)
    combo = str(row.get("Combo") or "—")
    try:
        remaining = float(row.get("Remaining Balance ($)"))
    except Exception:
        remaining = 0.0
    try:
        net_profit = float(row.get("Net Profit incl. Withdrawals ($)"))
    except Exception:
        net_profit = 0.0
    short_strategy = "Rebalanced" if str(strategy).lower().startswith("reb") else "Not Rebalanced"
    coverage = ""
    try:
        funded = int(float(row.get("Withdrawals Fully Funded")))
        target = int(float(row.get("Target Withdrawals") or 10))
        coverage = f" • Funded {funded}/{target}"
    except Exception:
        coverage = ""
    return (
        f"#{rank} {combo} • {short_strategy} remaining ${remaining:,.0f} "
        f"• Net profit ${net_profit:,.0f}{coverage}"
    )


def _apply_withdrawal_ranked_combo_selection(
    select_key: str,
    lookup_key: str,
    ranking_name: str,
    annual_withdrawal: float = COMBO_WITHDRAWAL_ANNUAL,
    period: str = "10Y",
) -> None:
    selected = st.session_state.get(select_key)
    lookup = st.session_state.get(lookup_key) or {}
    symbols = list(lookup.get(selected) or [])
    if len(symbols) != 4:
        return
    annual_withdrawal = float(annual_withdrawal)
    st.session_state.portfolio_symbols = symbols
    st.session_state.portfolio_symbol_picker = symbols
    st.session_state.portfolio_period = str(period)
    st.session_state.portfolio_allocation_mode = "Equal split"
    st.session_state.portfolio_include_ytd = False
    st.session_state.portfolio_total_amount = float(COMBO_WITHDRAWAL_START)
    st.session_state.portfolio_withdrawals_enabled = True
    st.session_state.portfolio_monthly_withdrawals_enabled = False
    if abs(annual_withdrawal - float(COMBO_WITHDRAWAL_ANNUAL)) < 0.005:
        st.session_state.portfolio_annual_withdrawal = float(COMBO_WITHDRAWAL_ANNUAL)
    else:
        st.session_state.portfolio_annual_withdrawal = annual_withdrawal
    st.session_state.combo_autoload_message = (
        f"Loaded {ranking_name}: {' + '.join(symbols)}. Simulator set to $300,000 start, "
        f"{period} / Equal split, with ${annual_withdrawal:,.0f} annual withdrawals."
    )


def _withdrawal_combo_rank_table(df: pd.DataFrame) -> pd.DataFrame:
    """Display detailed yearly-withdrawal rankings for any saved horizon/list size."""
    if df is None or df.empty:
        return pd.DataFrame()

    years = sorted(
        [str(col) for col in df.columns if str(col).isdigit() and len(str(col)) == 4],
        reverse=True,
    )

    identity_cols = []
    usage_cols = []
    for idx in range(1, 5):
        identity_cols.extend([f"Stock {idx}", f"Sector {idx}", f"Name {idx}"])
        for candidate in (f"Stock {idx} Top250 Uses", f"Stock {idx} Top100 Uses"):
            if candidate in df.columns:
                identity_cols.append(candidate)
                usage_cols.append(candidate)
                break

    balance_cols = [f"{year} Balance After Withdrawal ($)" for year in sorted(years)]
    coverage_candidates = [
        "Target Withdrawals", "Withdrawals Fully Funded",
        "Full 20Y Withdrawal Goal", "Full 10Y Withdrawal Goal",
        "Depleted Year", "Max Ticker Repeats",
        "Distinct Tickers in Top 250", "Distinct Tickers in Top 100",
    ]
    coverage_cols = [col for col in coverage_candidates if col in df.columns]
    source_cols = ["Ranking Window Start", "Ranking Window End", "Ranking Source", "Ranking Method"]
    cols = [
        "Rank", "Combo", "Strategy", *identity_cols, *years,
        "Worst Year", "Worst Year %", "Best Year", "Best Year %",
        *coverage_cols,
        "Starting Value ($)", "Annual Withdrawal ($)", "Total Withdrawn ($)",
        "Remaining Balance ($)", "Net Value incl. Withdrawals ($)",
        "Net Profit incl. Withdrawals ($)", *balance_cols, *source_cols,
    ]
    available = [c for c in cols if c in df.columns]
    out = df[available].copy()

    for col in years + ["Worst Year %", "Best Year %"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(2)
    for col in [
        "Starting Value ($)", "Annual Withdrawal ($)", "Total Withdrawn ($)",
        "Remaining Balance ($)", "Net Value incl. Withdrawals ($)",
        "Net Profit incl. Withdrawals ($)", *balance_cols,
    ]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(2)
    integer_cols = [
        "Rank", "Target Withdrawals", "Withdrawals Fully Funded",
        "Max Ticker Repeats", "Distinct Tickers in Top 250",
        "Distinct Tickers in Top 100", *usage_cols,
    ]
    for col in integer_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")
    return out


def _apply_recession_ranked_combo_selection(select_key: str, lookup_key: str, ranking_name: str) -> None:
    selected = st.session_state.get(select_key)
    lookup = st.session_state.get(lookup_key) or {}
    symbols = list(lookup.get(selected) or [])
    if len(symbols) != 4:
        return
    st.session_state.portfolio_symbols = symbols
    st.session_state.portfolio_symbol_picker = symbols
    st.session_state.portfolio_period = "10Y"
    st.session_state.portfolio_allocation_mode = "Equal split"
    st.session_state.portfolio_include_ytd = False
    st.session_state.portfolio_total_amount = float(COMBO_WITHDRAWAL_START)
    st.session_state.portfolio_withdrawals_enabled = False
    st.session_state.portfolio_monthly_withdrawals_enabled = False
    st.session_state.combo_autoload_message = (
        f"Loaded {ranking_name}: {' + '.join(symbols)}. Simulator set to $300,000 start, "
        "10Y / Equal split, with no cash withdrawals so recession-resilience and growth stay isolated."
    )


def _recession_combo_rank_table(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    years = COMBO_RANK_YEARS_BY_PERIOD["10Y"]
    identity_cols = []
    for idx in range(1, 5):
        identity_cols.extend([
            f"Stock {idx}", f"Sector {idx}", f"Name {idx}", f"Role {idx}",
            f"Stock {idx} Top100 Uses",
        ])
    balance_cols = [f"{year} Balance After Withdrawal ($)" for year in sorted(years)]
    cols = [
        "Rank", "Combo", "Strategy", *identity_cols, *years,
        "Worst Year", "Worst Year %", "Best Year", "Best Year %",
        "Defense Recession Worst %", "Defense Recession Avg %",
        "Defense Recession Positive Years", "Defense Recession Observations", "Recession Stress Years",
        "Max Ticker Repeats", "Distinct Tickers in Top 100",
        "Starting Value ($)", "Annual Withdrawal ($)", "Total Withdrawn ($)",
        "Remaining Balance ($)", "Net Value incl. Withdrawals ($)",
        "Net Profit incl. Withdrawals ($)", *balance_cols,
    ]
    available = [c for c in cols if c in df.columns]
    out = df[available].copy()
    pct_cols = years + [
        "Worst Year %", "Best Year %", "Defense Recession Worst %", "Defense Recession Avg %",
    ]
    for col in pct_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(2)
    for col in [
        "Starting Value ($)", "Annual Withdrawal ($)", "Total Withdrawn ($)",
        "Remaining Balance ($)", "Net Value incl. Withdrawals ($)",
        "Net Profit incl. Withdrawals ($)", *balance_cols,
    ]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(2)
    return out


def _apply_monthly_withdrawal_ranked_combo_selection(select_key: str, lookup_key: str, ranking_name: str) -> None:
    selected = st.session_state.get(select_key)
    lookup = st.session_state.get(lookup_key) or {}
    symbols = list(lookup.get(selected) or [])
    if len(symbols) != 4:
        return
    st.session_state.portfolio_symbols = symbols
    st.session_state.portfolio_symbol_picker = symbols
    st.session_state.portfolio_period = "10Y"
    st.session_state.portfolio_allocation_mode = "Equal split"
    st.session_state.portfolio_include_ytd = False
    st.session_state.portfolio_total_amount = float(COMBO_WITHDRAWAL_START)
    st.session_state.portfolio_withdrawals_enabled = False
    st.session_state.portfolio_monthly_withdrawals_enabled = True
    st.session_state.portfolio_monthly_withdrawal = float(COMBO_WITHDRAWAL_MONTHLY)
    st.session_state.combo_autoload_message = (
        f"Loaded {ranking_name}: {' + '.join(symbols)}. Simulator set to $300,000 start, "
        f"10Y / Equal split, with $5,000 monthly withdrawals. HWM is excluded from this ranking."
    )


def _monthly_withdrawal_combo_rank_table(df: pd.DataFrame) -> pd.DataFrame:
    """Show actual-monthly rankings with the same detail depth as the yearly withdrawal table."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    years = COMBO_RANK_YEARS_BY_PERIOD["10Y"]

    # Backward compatibility: enrich older ranking files from the durable actual-monthly series.
    needs_enrichment = (
        "Positive Months" not in df.columns
        or any(year not in df.columns for year in years)
        or "Worst Year" not in df.columns
        or "Best Year" not in df.columns
        or any(f"Name {idx}" not in df.columns for idx in range(1, 5))
    )
    if needs_enrichment:
        symbols = []
        for _, row in df.iterrows():
            for idx in range(1, 5):
                sym = str(row.get(f"Stock {idx}") or "").strip().upper()
                if sym and sym not in symbols:
                    symbols.append(sym)
        actual = cached_actual_monthly_returns(tuple(symbols), tuple(sorted(years))) if symbols else {"unavailable": True}
        market_names = {}
        try:
            for _, mrow in market.iterrows():
                market_names[str(mrow.get("Symbol") or "").upper()] = str(mrow.get("Name") or "")
        except Exception:
            market_names = {}
        if not actual.get("unavailable"):
            month_returns = actual.get("returns") or {}
            month_labels = list(actual.get("months") or [])
            for row_idx, row in df.iterrows():
                combo = [str(row.get(f"Stock {idx}") or "").strip().upper() for idx in range(1, 5)]
                combo = [sym for sym in combo if sym]
                if len(combo) != 4:
                    continue
                for idx, sym in enumerate(combo, 1):
                    if not str(row.get(f"Name {idx}") or "").strip():
                        df.at[row_idx, f"Name {idx}"] = market_names.get(sym, sym)
                rebalance = str(row.get("Strategy") or "").lower().startswith("rebalanced")
                withdrawal_raw = pd.to_numeric(pd.Series([row.get("Monthly Withdrawal ($)")]), errors="coerce").iloc[0]
                withdrawal = float(withdrawal_raw) if pd.notna(withdrawal_raw) else float(COMBO_WITHDRAWAL_MONTHLY)
                start_raw = pd.to_numeric(pd.Series([row.get("Starting Value ($)")]), errors="coerce").iloc[0]
                starting_value = float(start_raw) if pd.notna(start_raw) else float(COMBO_WITHDRAWAL_START)
                balances = {sym: starting_value / 4.0 for sym in combo}
                positive = 0
                year_factor = {year: 1.0 for year in sorted(years)}
                year_end = {}
                funded = 0
                for label in month_labels:
                    year = label[:4]
                    if year not in year_factor:
                        continue
                    start_balance = sum(balances.values())
                    if start_balance <= 0:
                        break
                    missing = False
                    for sym in balances:
                        value = (month_returns.get(sym) or {}).get(label)
                        if value is None or not np.isfinite(value):
                            missing = True
                            break
                        balances[sym] *= 1.0 + float(value)
                    if missing:
                        break
                    before = sum(balances.values())
                    month_factor = before / start_balance if start_balance > 0 else 1.0
                    year_factor[year] *= month_factor
                    if month_factor > 1.0:
                        positive += 1
                    actual_withdrawal = min(withdrawal, before)
                    ending = max(0.0, before - actual_withdrawal)
                    scale = ending / before if before > 0 else 0.0
                    for sym in balances:
                        balances[sym] *= scale
                    funded += 1
                    if rebalance and ending > 0:
                        equal = ending / 4.0
                        for sym in balances:
                            balances[sym] = equal
                    if label.endswith("-12"):
                        year_end[year] = ending
                df.at[row_idx, "Positive Months"] = positive
                df.at[row_idx, "Months Funded"] = funded
                annual_values = []
                for year in sorted(years):
                    annual_pct = (year_factor[year] - 1.0) * 100.0
                    df.at[row_idx, year] = annual_pct
                    annual_values.append((year, annual_pct))
                    if year in year_end:
                        df.at[row_idx, f"{year} Ending Balance ($)"] = year_end[year]
                if annual_values:
                    worst_year, worst_value = min(annual_values, key=lambda item: item[1])
                    best_year, best_value = max(annual_values, key=lambda item: item[1])
                    df.at[row_idx, "Worst Year"] = worst_year
                    df.at[row_idx, "Worst Year %"] = worst_value
                    df.at[row_idx, "Best Year"] = best_year
                    df.at[row_idx, "Best Year %"] = best_value

    identity_cols = []
    for idx in range(1, 5):
        identity_cols.extend([f"Stock {idx}", f"Sector {idx}", f"Name {idx}"])
    year_balance_cols = [f"{year} Ending Balance ($)" for year in sorted(years)]
    cols = [
        "Rank", "Combo", "Strategy", *identity_cols, *years,
        "Worst Year", "Worst Year %", "Best Year", "Best Year %",
        "Positive Months", "Months Funded",
        "Starting Value ($)", "Monthly Withdrawal ($)", "Total Withdrawn ($)",
        "Remaining Balance ($)", "Net Value incl. Withdrawals ($)",
        "Net Profit incl. Withdrawals ($)", *year_balance_cols, "HWM Excluded",
    ]
    available = [c for c in cols if c in df.columns]
    out = df[available].copy()
    if "Positive Months" in out.columns:
        total = pd.to_numeric(out.get("Months Funded"), errors="coerce")
        pos = pd.to_numeric(out["Positive Months"], errors="coerce")
        out["Positive Months"] = [
            f"{int(p)}/{int(t)}" if pd.notna(p) and pd.notna(t) and int(t) > 0 else "N/A"
            for p, t in zip(pos, total)
        ]
    for col in years + ["Worst Year %", "Best Year %"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(2)
    for col in year_balance_cols + [
        "Starting Value ($)", "Monthly Withdrawal ($)", "Total Withdrawn ($)",
        "Remaining Balance ($)", "Net Value incl. Withdrawals ($)",
        "Net Profit incl. Withdrawals ($)",
    ]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(2)
    return out


def _on_yearly_withdrawal_toggle() -> None:
    if bool(st.session_state.get("portfolio_withdrawals_enabled")):
        st.session_state["portfolio_monthly_withdrawals_enabled"] = False


def _on_monthly_withdrawal_toggle() -> None:
    if bool(st.session_state.get("portfolio_monthly_withdrawals_enabled")):
        st.session_state["portfolio_withdrawals_enabled"] = False


def _combo_rank_table(df: pd.DataFrame, period: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    period = str(period or "10Y").upper()
    years = COMBO_RANK_YEARS_BY_PERIOD.get(period, COMBO_RANK_YEARS_BY_PERIOD["10Y"])
    cagr_col = f"{len(years)}Y CAGR %"
    cols = [
        "Rank", "Combo",
        *years,
        "Worst Year", "Worst Year %",
        "Best Year", "Best Year %",
        "Starting Value ($)", "Ending Value ($)", "Total Profit ($)",
        "Total Return %", cagr_col,
    ]
    available = [c for c in cols if c in df.columns]
    out = df[available].copy()
    for col in years + ["Worst Year %", "Best Year %", "Total Return %", cagr_col]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(2)
    for col in ["Starting Value ($)", "Ending Value ($)", "Total Profit ($)"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(2)
    return out

def _normalize_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "Symbol" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["Symbol"] = df["Symbol"].astype(str).str.upper().str.strip()
    # v5.7 intentionally does not map legacy CAGR columns into calendar-year returns.
    # Annual return cells remain blank until a real historical refresh computes
    # each completed calendar year from adjusted year-end closes.
    numeric = [
        "MarketCap", "Price", "NAV", *PRICE_TARGET_COLS, *ALL_RETURN_COLS,
        "Verified Years", "Verification Available Years", "Verification Compared Years",
        "Verification Discrepancies", "Max Verification Diff (pp)", "Verification Tolerance (pp)",
    ]
    for col in numeric:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in [
        "Analyst Rating", "Rating Source", "Rating Updated ET", "Price Target Updated ET", "Price Target Source", "Snapshot Updated ET",
        "History Verification", "Verification Coverage", "Verification Exceptions",
        "Verification Source", "Verification Updated ET",
    ]:
        if col not in df.columns:
            df[col] = "Not Rated" if col == "Analyst Rating" else ("Pending" if col == "History Verification" else "—")
    df["Analyst Rating"] = df["Analyst Rating"].fillna("Not Rated").replace({"": "Not Rated", "nan": "Not Rated"})
    for col in SIGNAL_COLS + ["Short Signal New", "Long Signal New"]:
        if col not in df.columns:
            df[col] = False
        df[col] = df[col].fillna(False).astype(str).str.lower().isin({"true", "1", "yes", "buy"})
    for col in ["Signal Reasons", "Signal Updated ET"]:
        if col not in df.columns:
            df[col] = ""
    df = _enforce_100b_market(df)
    return df.drop_duplicates("Symbol", keep="last")


def _annual_coverage_stats(df: pd.DataFrame) -> dict:
    """Summarize real saved annual-return coverage for the dynamically growing completed-year window."""
    if df is None or df.empty:
        return {
            "rows": 0, "years_with_any": 0, "annual_cells": 0, "oldest_five_cells": 0,
            "oldest_year_with_data": None, "counts_by_year": {year: 0 for year in YEAR_RETURN_COLS},
        }
    counts = {}
    for year in YEAR_RETURN_COLS:
        if year not in df.columns:
            counts[year] = 0
            continue
        counts[year] = int(pd.to_numeric(df[year], errors="coerce").notna().sum())
    oldest = None
    for year in reversed(YEAR_RETURN_COLS):
        if counts.get(year, 0) > 0:
            oldest = year
            break
    return {
        "rows": int(len(df)),
        "years_with_any": int(sum(1 for year in YEAR_RETURN_COLS if counts.get(year, 0) > 0)),
        "annual_cells": int(sum(counts.values())),
        "oldest_five_cells": int(sum(counts.get(year, 0) for year in OLDEST_FIVE_YEAR_COLS)),
        "oldest_year_with_data": oldest,
        "counts_by_year": counts,
    }


def _price_target_coverage_stats(df: pd.DataFrame) -> dict:
    """Count genuine saved analyst-target coverage for snapshot selection/QA."""
    if df is None or df.empty:
        return {"target_cells": 0, "complete_stock_rows": 0}
    work = df.copy()
    types = (
        work["Type"].astype(str).str.upper().str.strip()
        if "Type" in work.columns else pd.Series("", index=work.index)
    )
    stocks = work.loc[types.eq("STOCK")].copy()
    if stocks.empty:
        return {"target_cells": 0, "complete_stock_rows": 0}
    valid_cols = []
    for col in PRICE_TARGET_COLS:
        if col not in stocks.columns:
            stocks[col] = np.nan
        numeric = pd.to_numeric(stocks[col], errors="coerce")
        valid = numeric.notna() & np.isfinite(numeric) & (numeric > 0)
        valid_cols.append(valid)
    target_cells = int(sum(int(mask.sum()) for mask in valid_cols))
    complete = valid_cols[0] & valid_cols[1] & valid_cols[2]
    return {
        "target_cells": target_cells,
        "complete_stock_rows": int(complete.sum()),
    }


def _snapshot_quality_key(df: pd.DataFrame) -> tuple:
    """Prefer genuine annual history first, then analyst-target coverage and prices."""
    stats = _annual_coverage_stats(df)
    targets = _price_target_coverage_stats(df)
    return (
        int(stats["years_with_any"]),
        int(stats["oldest_five_cells"]),
        int(stats["annual_cells"]),
        int(targets["complete_stock_rows"]),
        int(targets["target_cells"]),
        int(_populated_price_count(df)),
        int(stats["rows"]),
    )


def _populated_price_count(df: pd.DataFrame) -> int:
    if df is None or df.empty or "Price" not in df.columns:
        return 0
    return int(pd.to_numeric(df["Price"], errors="coerce").notna().sum())


def _valid_status_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "none", "null", "nan", "nat", "—"} else text


def _enforce_100b_market(df: pd.DataFrame) -> pd.DataFrame:
    """Keep ETFs, manually persisted symbols, and Nasdaq-screened stocks > $100B."""
    if df is None or df.empty or "Type" not in df.columns:
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    out = df.copy()
    types = out["Type"].astype(str).str.upper().str.strip()
    caps = pd.to_numeric(out["MarketCap"], errors="coerce") if "MarketCap" in out.columns else pd.Series(float("nan"), index=out.index)
    if "Universe Source" in out.columns:
        source = out["Universe Source"].astype(str).str.lower()
    elif "Source" in out.columns:
        source = out["Source"].astype(str).str.lower()
    else:
        source = pd.Series("", index=out.index)
    manual = source.str.contains("manual", regex=False, na=False)
    keep = types.ne("STOCK") | (caps > MIN_STOCK_MARKET_CAP) | manual
    return out.loc[keep].copy()


def _latest_display_timestamp(values) -> str:
    candidates = [_valid_status_text(v) for v in list(values)]
    candidates = [v for v in candidates if v]
    if not candidates:
        return ""
    parsed = []
    for text in candidates:
        core = text.rsplit(" ", 1)[0] if text.endswith((" EST", " EDT")) else text
        ts = pd.to_datetime(core, errors="coerce")
        parsed.append((ts, text))
    valid = [(ts, text) for ts, text in parsed if pd.notna(ts)]
    return max(valid, key=lambda item: item[0])[1] if valid else candidates[-1]


@st.cache_data(ttl=60, show_spinner=False)
def load_snapshot() -> pd.DataFrame:
    """Load the snapshot with the strongest genuine dynamic annual coverage.

    v5.9.58 preserves the migration fix where where an older local 20-year snapshot
    could win simply because it already had prices, even after GitHub held a
    newer full-history snapshot. Local, GitHub and bootstrap candidates are all
    normalized, then ranked by annual-year coverage first and populated prices
    second. No annual value is synthesized.
    """
    candidates: list[tuple[str, pd.DataFrame]] = []

    if SNAPSHOT_FILE.exists():
        try:
            local = _normalize_snapshot(pd.read_csv(SNAPSHOT_FILE))
            if not local.empty:
                candidates.append(("local", local))
        except Exception:
            pass

    try:
        remote = _normalize_snapshot(load_remote_snapshot())
        if not remote.empty:
            candidates.append(("github", remote))
    except Exception:
        pass

    if BOOTSTRAP_SNAPSHOT_FILE.exists():
        try:
            bootstrap = _normalize_snapshot(pd.read_csv(BOOTSTRAP_SNAPSHOT_FILE))
            if not bootstrap.empty:
                candidates.append(("bootstrap", bootstrap))
        except Exception:
            pass

    if not candidates:
        return pd.DataFrame()

    populated = [(name, df) for name, df in candidates if _populated_price_count(df) > 0]
    pool = populated or candidates
    # Python max is stable; local/GitHub/bootstrap order breaks exact ties without
    # changing data. A complete dynamic-history remote snapshot outranks a stale shorter local one.
    source_priority = {"bootstrap": 0, "local": 1, "github": 2}
    _, best = max(
        pool,
        key=lambda pair: (
            _snapshot_quality_key(pair[1]),
            int(source_priority.get(pair[0], 0)),
        ),
    )
    return best


def _read_metadata_file(path: Path) -> dict:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    return {}


def _run_manual_universe_refresh() -> tuple[bool, bool, str, dict]:
    """Run the same Nasdaq universe generator used by the scheduled workflow.

    Returns (local_success, durable_success, message, metadata). This intentionally
    refreshes universe membership + Nasdaq analyst ratings only; the existing
    full market refresh remains responsible for Yahoo history/prices and rankings.
    """
    script = BASE_DIR / "scripts" / "update_universe.py"
    if not script.exists():
        return False, False, "Nasdaq universe refresh script is missing.", {}
    # Manual Render refresh must start from the durable append-only history,
    # otherwise ephemeral local storage could forget older historical events.
    history_path = BASE_DIR / "data" / "universe_change_history.json"
    try:
        local_history = []
        if history_path.exists():
            local_payload = json.loads(history_path.read_text(encoding="utf-8"))
            if isinstance(local_payload, list):
                local_history = local_payload
        remote_history = load_remote_universe_change_history(timeout=12)
        merged_history = _merge_universe_change_history(local_history, remote_history)
        history_path.write_text(json.dumps(merged_history, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass

    try:
        completed = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, False, "Nasdaq universe refresh timed out after 5 minutes.", {}
    except Exception as exc:
        return False, False, f"Nasdaq universe refresh could not start: {exc}", {}

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown error").strip()
        return False, False, f"Nasdaq universe refresh failed: {detail[-800:]}", {}

    generated_universe = BASE_DIR / "data" / "default_universe.csv"
    generated_metadata = BASE_DIR / "data" / "universe_metadata.json"
    metadata_payload = _read_metadata_file(generated_metadata)
    if not generated_universe.exists() or not metadata_payload:
        return False, False, "Nasdaq universe refresh finished but did not produce the expected generated files.", {}

    generated_history = BASE_DIR / "data" / "universe_change_history.json"
    durable_ok, durable_message = persist_universe_refresh(
        generated_universe,
        generated_metadata,
        generated_history,
    )
    stock_count = int(metadata_payload.get("stock_count") or 0)
    etf_count = int(metadata_payload.get("etf_count") or 0)
    added_count = int(metadata_payload.get("added_count") or 0)
    removed_count = int(metadata_payload.get("removed_count") or 0)
    stamp = _valid_status_text(metadata_payload.get("refreshed_at_display_et")) or format_et(now_et())
    summary = (
        f"Nasdaq universe refreshed at {stamp}: {stock_count:,} stocks >$100B + {etf_count:,} ETFs; "
        f"membership changes +{added_count}/-{removed_count}. {durable_message}"
    )
    return True, durable_ok, summary, metadata_payload


@st.cache_data(ttl=60, show_spinner=False)
def load_snapshot_metadata() -> dict:
    # Prefer a real generated/remote timestamp; bootstrap metadata is last resort.
    local = _read_metadata_file(SNAPSHOT_META_FILE)
    remote = load_remote_metadata()
    bootstrap = _read_metadata_file(BOOTSTRAP_META_FILE)

    for candidate in (remote, local, bootstrap):
        if isinstance(candidate, dict) and _valid_status_text(candidate.get("updated_at_display_et")):
            return candidate
    return remote or local or bootstrap or {}


@st.cache_data(ttl=60, show_spinner=False)
def load_universe_metadata() -> dict:
    """Load Nasdaq universe refresh membership metadata from GitHub/local/bootstrap."""
    local = _read_metadata_file(UNIVERSE_META_FILE)
    remote = load_remote_universe_metadata()
    bootstrap = _read_metadata_file(BOOTSTRAP_UNIVERSE_META_FILE)

    for candidate in (remote, local, bootstrap):
        if isinstance(candidate, dict) and _valid_status_text(candidate.get("refreshed_at_display_et")):
            return candidate
    return remote or local or bootstrap or {}


def _universe_history_event_key(event: dict) -> tuple:
    return (
        str(event.get("occurred_at_et") or ""),
        str(event.get("change_type") or ""),
        str(event.get("symbol") or "").upper(),
        str(event.get("from") or ""),
        str(event.get("to") or ""),
    )


def _merge_universe_change_history(*collections) -> list[dict]:
    """Merge local/durable events without pruning old history."""
    output: list[dict] = []
    known = set()
    for collection in collections:
        if not isinstance(collection, list):
            continue
        for item in collection:
            if not isinstance(item, dict):
                continue
            key = _universe_history_event_key(item)
            if key in known:
                continue
            output.append(dict(item))
            known.add(key)
    output.sort(key=lambda item: str(item.get("occurred_at_et") or ""))
    return output


@st.cache_data(ttl=60, show_spinner=False)
def load_universe_change_history() -> list[dict]:
    """Load the append-only Nasdaq membership/rating history from local + GitHub."""
    local = []
    try:
        payload = json.loads(UNIVERSE_CHANGE_HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            local = payload
    except Exception:
        local = []
    remote = load_remote_universe_change_history(timeout=10)
    return _merge_universe_change_history(local, remote)


@st.cache_data(ttl=60, show_spinner=False)
def load_favorite_picks_history() -> dict:
    """Merge local, GitHub, and bootstrap ledgers while preserving first-event dates."""

    payloads = []
    for path in (FAVORITE_PICKS_HISTORY_FILE, FAVORITE_PICKS_HISTORY_BOOTSTRAP_FILE):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payloads.append(payload)
        except Exception:
            pass
    remote = load_remote_favorite_picks_history(timeout=10)
    if isinstance(remote, dict) and remote:
        payloads.append(remote)
    return merge_favorite_picks_ledgers(*payloads)


def _current_metadata_change_events(metadata: dict) -> list[dict]:
    """Bridge the most recent pre-v5.9.78 metadata change into the history view."""
    if not isinstance(metadata, dict):
        return []
    stamp = str(metadata.get("refreshed_at_et") or "").strip()
    display = str(metadata.get("refreshed_at_display_et") or "").strip()
    if not stamp:
        return []
    source = str(metadata.get("source") or "Nasdaq Stock Screener")
    events = []
    for symbol in metadata.get("added_symbols") or []:
        sym = str(symbol or "").upper().strip()
        if sym:
            events.append({
                "occurred_at_et": stamp,
                "occurred_at_display_et": display,
                "first_detected_at_et": stamp,
                "first_detected_display_et": display,
                "change_type": "Stock Added",
                "symbol": sym,
                "name": sym,
                "from": "Outside >$100B universe",
                "to": "Included >$100B universe",
                "source": source,
            })
    for symbol in metadata.get("removed_symbols") or []:
        sym = str(symbol or "").upper().strip()
        if sym:
            events.append({
                "occurred_at_et": stamp,
                "occurred_at_display_et": display,
                "first_detected_at_et": stamp,
                "first_detected_display_et": display,
                "change_type": "Stock Removed",
                "symbol": sym,
                "name": sym,
                "from": "Included >$100B universe",
                "to": "Outside >$100B universe",
                "source": source,
            })
    for change in metadata.get("analyst_rating_changes") or []:
        if not isinstance(change, dict):
            continue
        sym = str(change.get("symbol") or "").upper().strip()
        if sym:
            events.append({
                "occurred_at_et": stamp,
                "occurred_at_display_et": display,
                "first_detected_at_et": stamp,
                "first_detected_display_et": display,
                "change_type": "Analyst Rating",
                "symbol": sym,
                "name": str(change.get("name") or sym),
                "from": str(change.get("from") or "Not Rated"),
                "to": str(change.get("to") or "Not Rated"),
                "source": source,
            })
    return events


def _six_month_universe_history_frame(history: list[dict], as_of=None, months: int | None = 6) -> pd.DataFrame:
    """Format universe history; optionally filter the view without touching storage."""
    columns = ["Date / Time (ET)", "Change Type", "Symbol", "Name", "Previous", "New", "Source"]
    if not history:
        return pd.DataFrame(columns=columns)

    now_value = pd.Timestamp(as_of if as_of is not None else now_et())
    if now_value.tzinfo is None:
        now_value = now_value.tz_localize("America/New_York")
    else:
        now_value = now_value.tz_convert("America/New_York")
    cutoff = now_value - pd.DateOffset(months=int(months)) if months is not None else None

    rows = []
    for event in history:
        if not isinstance(event, dict):
            continue
        occurred = pd.to_datetime(event.get("first_detected_at_et") or event.get("occurred_at_et"), errors="coerce")
        if pd.isna(occurred):
            continue
        if getattr(occurred, "tzinfo", None) is None:
            occurred = occurred.tz_localize("America/New_York")
        else:
            occurred = occurred.tz_convert("America/New_York")
        if (cutoff is not None and occurred < cutoff) or occurred > now_value:
            continue
        display = str(event.get("first_detected_display_et") or event.get("occurred_at_display_et") or "").strip()
        if not display:
            display = occurred.strftime("%b %d, %Y %I:%M:%S %p ET")
        rows.append({
            "_occurred": occurred,
            "Date / Time (ET)": display,
            "Change Type": str(event.get("change_type") or "Change"),
            "Symbol": str(event.get("symbol") or "").upper(),
            "Name": str(event.get("name") or event.get("symbol") or ""),
            "Previous": str(event.get("from") or "—"),
            "New": str(event.get("to") or "—"),
            "Source": str(event.get("source") or "Nasdaq Stock Screener"),
        })

    if not rows:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(rows).sort_values("_occurred", ascending=False).drop(columns="_occurred")
    return frame[columns].reset_index(drop=True)


@st.cache_data(ttl=30, show_spinner=False)
def cached_saved_simulations() -> list[dict]:
    return load_saved_simulations(BASE_DIR / "data")


@st.cache_data(ttl=60 * 60, show_spinner=False)
def cached_simulation_pdf(record_json: str) -> bytes:
    record = json.loads(record_json)
    if bool(record.pop("_force_pdf_rebuild", False)):
        rebuilt = build_portfolio_simulation_pdf(record)
        persist_pdf_artifact(
            rebuilt,
            record,
            BASE_DIR,
            f"data: upgrade MarketScope PDF page-1 contract {record.get('id') or 'simulation'}",
        )
        return rebuilt
    return load_pdf_artifact(record, BASE_DIR, builder=build_portfolio_simulation_pdf)


@st.cache_data(ttl=60 * 60, show_spinner=False)
def cached_chart_history(symbol: str, period: str) -> pd.DataFrame:
    return provider.download_chart_history(symbol, period)


@st.cache_data(ttl=60 * 60, show_spinner=False)
def cached_max_chart_history(symbol: str) -> pd.DataFrame:
    return provider.download_chart_history(symbol, "MAX")


def _actual_month_labels(calendar_years: tuple[str, ...] | list[str]) -> list[str]:
    years = sorted({int(str(y)) for y in calendar_years if str(y).isdigit()})
    return [f"{year}-{month:02d}" for year in years for month in range(1, 13)]


def _monthly_csv_actual(frame: pd.DataFrame) -> bool:
    if frame is None or frame.empty or "Monthly Return Method" not in frame.columns:
        return False
    methods = frame["Monthly Return Method"].dropna().astype(str)
    return bool(len(methods)) and methods.str.contains(
        "Actual adjusted month-end return", case=False, regex=False
    ).all()


def _monthly_year_compound(month_map: dict[str, float], year: str) -> float | None:
    """Compound 12 actual monthly decimal returns for one completed calendar year."""
    factor = 1.0
    for month in range(1, 13):
        label = f"{year}-{month:02d}"
        value = month_map.get(label)
        if value is None or not np.isfinite(value) or float(value) <= -1.0:
            return None
        factor *= 1.0 + float(value)
    return (factor - 1.0) * 100.0


def _monthly_matches_market_table(
    market_df: pd.DataFrame,
    symbol: str,
    years: tuple[str, ...] | list[str],
    month_map: dict[str, float],
    tolerance_pp: float = 0.05,
) -> tuple[bool, list[str]]:
    """Require actual monthly history to reconcile to the annual return shown in Market Table.

    Both values come from adjusted daily history. This prevents a stale monthly CSV
    from silently driving a withdrawal simulation that disagrees with Table View.
    """
    if market_df is None or market_df.empty or "Symbol" not in market_df.columns:
        return True, []
    lookup = market_df.copy()
    lookup["Symbol"] = lookup["Symbol"].astype(str).str.upper().str.strip()
    lookup = lookup.drop_duplicates("Symbol", keep="first").set_index("Symbol", drop=False)
    sym = str(symbol).upper().strip()
    if sym not in lookup.index:
        return True, []
    row = lookup.loc[sym]
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]
    mismatches: list[str] = []
    for year in years:
        annual = pd.to_numeric(pd.Series([row.get(str(year))]), errors="coerce").iloc[0]
        if pd.isna(annual) or not np.isfinite(annual):
            continue
        compounded = _monthly_year_compound(month_map, str(year))
        if compounded is None:
            mismatches.append(f"{year}: missing monthly anchors")
            continue
        diff = abs(float(annual) - float(compounded))
        if diff > float(tolerance_pp):
            mismatches.append(
                f"{year}: Market Table {float(annual):+.3f}% vs monthly compound {float(compounded):+.3f}% (Δ {diff:.3f}pp)"
            )
    return not mismatches, mismatches


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def cached_actual_monthly_returns(
    symbols: tuple[str, ...],
    calendar_years: tuple[str, ...],
) -> dict:
    # Internal source order only. This function intentionally emits no Streamlit
    # text; data-source implementation details must never render in the UI.
    clean_symbols = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
    years = tuple(str(y) for y in calendar_years if str(y).isdigit())
    labels = _actual_month_labels(years)
    if not clean_symbols or not labels:
        return {"unavailable": True, "reason": "No symbols or completed calendar years were supplied.", "returns": {}}

    sources: list[pd.DataFrame] = []
    for local_path in (MONTHLY_RETURNS_FILE, MONTHLY_RETURNS_25Y_FILE, MONTHLY_RETURNS_FULL_FILE):
        if local_path.exists():
            try:
                sources.append(pd.read_csv(local_path))
            except Exception:
                pass
    for repo_path in (MONTHLY_RETURNS_REPO_PATH, MONTHLY_RETURNS_25Y_REPO_PATH, MONTHLY_RETURNS_FULL_REPO_PATH):
        remote = load_remote_csv(repo_path, timeout=15)
        if remote is not None and not remote.empty:
            sources.append(remote)

    actual_frame = pd.DataFrame()
    for candidate in sources:
        if candidate is None or candidate.empty or "Symbol" not in candidate.columns:
            continue
        if not _monthly_csv_actual(candidate):
            continue
        candidate = candidate.copy()
        candidate["Symbol"] = candidate["Symbol"].astype(str).str.upper().str.strip()
        candidate = candidate.drop_duplicates("Symbol", keep="last")
        if actual_frame.empty:
            actual_frame = candidate
        else:
            # Later sources fill/override the same symbols. A full-history row can therefore
            # coexist with legacy 10Y data without changing ranking compatibility.
            actual_frame = pd.concat([actual_frame, candidate], ignore_index=True).drop_duplicates("Symbol", keep="last")

    returns: dict[str, dict[str, float]] = {}
    missing_symbols: list[str] = []
    if not actual_frame.empty:
        actual_frame = actual_frame.set_index("Symbol", drop=False)

    for sym in clean_symbols:
        sym_returns: dict[str, float] = {}
        if not actual_frame.empty and sym in actual_frame.index:
            row = actual_frame.loc[sym]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[-1]
            valid = True
            for label in labels:
                value = pd.to_numeric(pd.Series([row.get(label)]), errors="coerce").iloc[0]
                if pd.isna(value) or not np.isfinite(value):
                    valid = False
                    break
                sym_returns[label] = float(value) / 100.0
            if valid:
                returns[sym] = sym_returns
                continue
        missing_symbols.append(sym)

    # Strong explicit-start fallback. v5.9.58 intentionally uses the exact same
    # configured anchor history boundary as the dynamic annual Table View calculation. Batch first,
    # then retry each missing symbol individually so one Yahoo omission (e.g. LLY)
    # cannot invalidate the entire portfolio schedule.
    if missing_symbols:
        try:
            histories = provider.download_daily_history_since(
                missing_symbols, start=ANNUAL_HISTORY_START, chunk_size=min(10, max(1, len(missing_symbols)))
            )
        except Exception:
            histories = {}
        still_batch_missing = [sym for sym in missing_symbols if sym not in histories or histories.get(sym) is None or histories.get(sym).empty]
        for sym in still_batch_missing:
            try:
                one = provider.download_daily_history_since([sym], start=ANNUAL_HISTORY_START, chunk_size=1)
                hist = one.get(sym)
                if hist is not None and not hist.empty:
                    histories[sym] = hist
            except Exception:
                continue

        start_year = min(int(y) for y in years)
        end_year = max(int(y) for y in years)
        for sym in missing_symbols:
            hist = histories.get(sym)
            if hist is None or hist.empty:
                continue
            calculated = calculate_monthly_returns(hist, start_year, end_year)
            sym_returns: dict[str, float] = {}
            valid = True
            for label in labels:
                value = calculated.get(label)
                if value is None or not np.isfinite(value):
                    valid = False
                    break
                sym_returns[label] = float(value)
            if valid:
                returns[sym] = sym_returns

    still_missing = [sym for sym in clean_symbols if sym not in returns]
    if still_missing:
        return {
            "unavailable": True,
            "reason": (
                "Actual monthly history could not be loaded after the durable full-history dataset "
                "and direct Yahoo retries for: " + ", ".join(still_missing)
            ),
            "returns": returns,
            "months": labels,
        }
    return {
        "unavailable": False,
        "returns": returns,
        "months": labels,
        "method": "Actual adjusted month-end return from the same Yahoo/yfinance history as Market Table",
        "annual_reconciliation": "Monthly compounds are checked against Market Table annual returns before withdrawal simulation.",
    }


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def cached_future_projection_monthly_returns(
    symbols: tuple[str, ...],
    calendar_years: tuple[str, ...],
) -> dict:
    """Load every observed monthly return available, including partial histories.

    The historical withdrawal simulator intentionally requires complete windows.
    Future Projection has a different limited-history contract: it preserves all
    observed post-IPO/post-inception months and explicitly imputes only the missing
    periods. This separate loader avoids changing any existing simulator result.
    """
    clean_symbols = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
    years = tuple(sorted({str(y) for y in calendar_years if str(y).isdigit()}, key=int))
    labels = _actual_month_labels(years)
    if not clean_symbols or not years:
        return {"unavailable": True, "reason": "No holdings or completed years were supplied.", "returns": {}}

    returns: dict[str, dict[str, float]] = {symbol: {} for symbol in clean_symbols}
    sources: list[pd.DataFrame] = []
    for local_path in (MONTHLY_RETURNS_FILE, MONTHLY_RETURNS_25Y_FILE, MONTHLY_RETURNS_FULL_FILE):
        if local_path.exists():
            try:
                sources.append(pd.read_csv(local_path))
            except Exception:
                pass
    for repo_path in (MONTHLY_RETURNS_REPO_PATH, MONTHLY_RETURNS_25Y_REPO_PATH, MONTHLY_RETURNS_FULL_REPO_PATH):
        remote = load_remote_csv(repo_path, timeout=15)
        if remote is not None and not remote.empty:
            sources.append(remote)

    for candidate in sources:
        if candidate is None or candidate.empty or "Symbol" not in candidate.columns or not _monthly_csv_actual(candidate):
            continue
        frame = candidate.copy()
        frame["Symbol"] = frame["Symbol"].astype(str).str.upper().str.strip()
        frame = frame.drop_duplicates("Symbol", keep="last").set_index("Symbol", drop=False)
        for symbol in clean_symbols:
            if symbol not in frame.index:
                continue
            row = frame.loc[symbol]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[-1]
            for label in labels:
                value = pd.to_numeric(pd.Series([row.get(label)]), errors="coerce").iloc[0]
                if pd.notna(value) and np.isfinite(value) and float(value) > -100.0:
                    returns[symbol][label] = float(value) / 100.0

    # Direct history fills all genuinely observed months while leaving pre-inception
    # dates absent for the projection engine to identify and blend explicitly.
    try:
        histories = provider.download_daily_history_since(
            list(clean_symbols),
            start=ANNUAL_HISTORY_START,
            chunk_size=min(10, max(1, len(clean_symbols))),
        )
    except Exception:
        histories = {}
    for symbol in clean_symbols:
        hist = histories.get(symbol)
        if hist is None or hist.empty:
            continue
        try:
            calculated = calculate_monthly_returns(hist, min(int(y) for y in years), max(int(y) for y in years))
        except Exception:
            continue
        for label, value in calculated.items():
            if label in labels and value is not None and np.isfinite(value) and float(value) > -1.0:
                returns[symbol][label] = float(value)

    observed = {symbol: len(values) for symbol, values in returns.items()}
    returns = {symbol: values for symbol, values in returns.items() if values}
    return {
        "unavailable": not bool(returns),
        "reason": "No actual monthly observations could be loaded." if not returns else "",
        "returns": returns,
        "months": labels,
        "observed_periods": observed,
        "method": "Observed adjusted month-end returns; missing pre-inception periods remain explicit for calibrated imputation",
    }


@st.cache_data(ttl=30 * 60, show_spinner=False)
def cached_future_projection_live_context(
    symbols: tuple[str, ...],
    current_market: pd.DataFrame,
) -> dict:
    """Load recent projection-only inputs without altering MarketScope snapshots."""

    try:
        return fetch_live_projection_context(provider, symbols, current_market)
    except Exception as exc:
        return {
            "retrieved_at": now_et().isoformat(),
            "histories": {},
            "prices": {},
            "fundamentals": {},
            "macro": {},
            "failures": [f"Live adaptive context unavailable ({type(exc).__name__})."],
        }


@st.cache_data(ttl=30 * 60, show_spinner=False)
def cached_card_two_year_histories(symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    """Batch-load two years of adjusted daily closes for visible market cards."""
    clean = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
    if not clean:
        return {}
    try:
        return provider.download_daily_history(clean, period="2y")
    except Exception:
        return {}


@st.cache_data(ttl=30 * 60, show_spinner=False)
def cached_price_targets(symbols: tuple[str, ...]) -> dict:
    """Lazy Yahoo price-target fallback for stock cards visible on the current page."""
    clean = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
    if not clean:
        return {}
    try:
        return provider.get_price_targets_many(clean, max_workers=2)
    except Exception:
        return {}


def _valid_price_target(value) -> bool:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return bool(pd.notna(parsed) and np.isfinite(parsed) and float(parsed) > 0)


_PRICE_TARGET_REGISTRY_FALLBACK: dict[str, dict] = {}


def _price_target_registry() -> dict:
    """Session registry for exact Low/Avg/High values already shown in Market Table."""
    try:
        registry = st.session_state.get("market_table_price_targets")
        if not isinstance(registry, dict):
            registry = {}
            st.session_state.market_table_price_targets = registry
        return registry
    except Exception:
        return _PRICE_TARGET_REGISTRY_FALLBACK


def _remember_price_targets(df: pd.DataFrame, symbols: tuple[str, ...] | list[str] | None = None, source_context: str = "") -> None:
    if df is None or df.empty or "Symbol" not in df.columns:
        return
    requested = None if symbols is None else {str(s).strip().upper() for s in symbols if str(s).strip()}
    registry = _price_target_registry()
    for _, row in df.iterrows():
        symbol = str(row.get("Symbol") or "").strip().upper()
        if not symbol or (requested is not None and symbol not in requested):
            continue
        values = {}
        for key, col in (("low", "Price Target Low"), ("mean", "Price Target Average"), ("high", "Price Target High")):
            value = pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").iloc[0]
            if pd.notna(value) and np.isfinite(value) and float(value) > 0:
                values[key] = float(value)
        if not values:
            continue
        existing = dict(registry.get(symbol) or {})
        existing.update(values)
        existing["source"] = str(row.get("Price Target Source") or source_context or existing.get("source") or "Market Table")
        existing["updated_et"] = str(row.get("Price Target Updated ET") or existing.get("updated_et") or "")
        registry[symbol] = existing


def _apply_remembered_price_targets(df: pd.DataFrame, symbols: tuple[str, ...] | list[str]) -> pd.DataFrame:
    if df is None or df.empty or "Symbol" not in df.columns:
        return df
    out = df.copy()
    registry = _price_target_registry()
    if not registry:
        return out
    requested = {str(s).strip().upper() for s in symbols if str(s).strip()}
    upper = out["Symbol"].astype(str).str.upper().str.strip()
    for symbol in requested:
        values = registry.get(symbol) or {}
        mask = upper.eq(symbol)
        if not mask.any():
            continue
        for key, col in (("low", "Price Target Low"), ("mean", "Price Target Average"), ("high", "Price Target High")):
            value = values.get(key)
            if not _valid_price_target(value):
                continue
            if col not in out.columns:
                out[col] = np.nan
            numeric = pd.to_numeric(out[col], errors="coerce")
            replace = mask & (numeric.isna() | ~np.isfinite(numeric) | (numeric <= 0))
            out.loc[replace, col] = float(value)
        if "Price Target Source" in out.columns and values.get("source"):
            source_text = out["Price Target Source"].astype(str).str.strip()
            out.loc[mask & source_text.isin(["", "—", "-"]), "Price Target Source"] = str(values.get("source"))
        if "Price Target Updated ET" in out.columns and values.get("updated_et"):
            updated_text = out["Price Target Updated ET"].astype(str).str.strip()
            out.loc[mask & updated_text.isin(["", "—", "-"]), "Price Target Updated ET"] = str(values.get("updated_et"))
    return out


def _hydrate_price_targets(df: pd.DataFrame, symbols: tuple[str, ...] | list[str]) -> pd.DataFrame:
    """Fill missing stock analyst Low / Average / High targets across every surface.

    Resolution order:
    1. durable snapshot value;
    2. shared cached Yahoo batch resolver;
    3. uncached per-symbol Yahoo resolver as a second chance.

    Existing valid values are never erased by a partial/failed response.
    """
    if df is None or df.empty or "Symbol" not in df.columns:
        return df

    out = df.copy()
    requested = tuple(
        dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip())
    )
    if not requested:
        return out

    for col in PRICE_TARGET_COLS:
        if col not in out.columns:
            out[col] = np.nan
    for col, default in (
        ("Price Target Updated ET", "—"),
        ("Price Target Source", ""),
    ):
        if col not in out.columns:
            out[col] = default

    # Reuse exact target values already shown in Market Table before making any
    # additional provider request.
    out = _apply_remembered_price_targets(out, requested)
    upper_symbols = out["Symbol"].astype(str).str.upper().str.strip()
    wanted = out.loc[upper_symbols.isin(requested)].copy()
    if wanted.empty:
        return out

    missing_symbols = []
    for _, row in wanted.iterrows():
        if str(row.get("Type") or "").strip().upper() != "STOCK":
            continue
        if any(not _valid_price_target(row.get(col)) for col in PRICE_TARGET_COLS):
            symbol = str(row.get("Symbol") or "").upper().strip()
            if symbol:
                missing_symbols.append(symbol)
    missing_symbols = list(dict.fromkeys(missing_symbols))
    if not missing_symbols:
        _remember_price_targets(out, requested)
        return out

    try:
        target_map = dict(cached_price_targets(tuple(missing_symbols)) or {})
    except Exception:
        target_map = {}

    # A cached empty/partial batch must not lock Table View or PDF into blanks.
    # Retry unresolved symbols directly, sequentially, bypassing the cache.
    for symbol in missing_symbols:
        values = target_map.get(symbol) or {}
        if not all(_valid_price_target(values.get(key)) for key in ("low", "mean", "high")):
            try:
                direct = provider.get_price_targets(symbol) or {}
            except Exception:
                direct = {}
            if direct:
                merged = dict(values)
                for key in ("low", "mean", "high", "median", "source"):
                    if direct.get(key) is not None:
                        merged[key] = direct.get(key)
                target_map[symbol] = merged

    stamp = format_et()
    for symbol in missing_symbols:
        values = target_map.get(symbol) or {}
        mask = upper_symbols.eq(symbol)
        wrote = False
        for source_key, col in (
            ("low", "Price Target Low"),
            ("mean", "Price Target Average"),
            ("high", "Price Target High"),
        ):
            value = pd.to_numeric(
                pd.Series([values.get(source_key)]), errors="coerce"
            ).iloc[0]
            if pd.notna(value) and np.isfinite(value) and float(value) > 0:
                # Only replace missing/invalid values; retain durable valid targets.
                current = pd.to_numeric(out.loc[mask, col], errors="coerce")
                replace_mask = mask & (
                    pd.to_numeric(out[col], errors="coerce").isna()
                    | ~np.isfinite(pd.to_numeric(out[col], errors="coerce"))
                    | (pd.to_numeric(out[col], errors="coerce") <= 0)
                )
                out.loc[replace_mask, col] = float(value)
                wrote = True
        if wrote:
            out.loc[mask, "Price Target Updated ET"] = stamp
            out.loc[mask, "Price Target Source"] = str(
                values.get("source") or "Yahoo Finance analyst consensus"
            )
    _remember_price_targets(out, requested)
    return out


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def cached_income_metrics(symbols: tuple[str, ...]) -> dict:
    """Fetch trailing dividend/distribution yield only for simulated portfolio instruments."""
    clean = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
    if not clean:
        return {}
    try:
        return provider.get_income_metrics_many(clean, max_workers=4)
    except Exception:
        return {}


@st.cache_data(ttl=30 * 60, show_spinner=False)
def cached_logo_urls(symbols: tuple[str, ...]) -> dict:
    """Fetch instrument logos for visible cards/comparisons with resilient fallback and short failure recovery."""
    clean = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
    if not clean:
        return {}
    try:
        return provider.get_logo_urls_many(clean, max_workers=3)
    except Exception:
        return {}


def _comparison_logo_html(symbol: str, logo_url: str) -> str:
    """Render Yahoo/issuer logo first, ticker-addressable logo second, initials last."""
    symbol = str(symbol or "").strip().upper()
    initials = escape((symbol[:2] or "?").upper())
    url = escape(str(logo_url or "").strip(), quote=True)
    fallback_url = escape(
        f"https://financialmodelingprep.com/image-stock/{symbol}.png",
        quote=True,
    )
    if not url.startswith(("https://", "http://")):
        url = fallback_url
    return (
        '<span class="comparison-logo">'
        f'<img src="{url}" data-logo-fallback="{fallback_url}" '
        f'alt="{escape(symbol)} logo" loading="lazy" '
        'onerror="if(this.src!==this.dataset.logoFallback){this.src=this.dataset.logoFallback;}'
        'else{this.style.display=\'none\';this.nextElementSibling.style.display=\'inline-flex\';}">'
        f'<span class="comparison-logo-inline-fallback">{initials}</span>'
        '</span>'
    )


def _card_logo_html(symbol: str, logo_url: str) -> str:
    """Shared compact logo treatment for Market Navigator and Comparison cards."""
    return _comparison_logo_html(symbol, logo_url)


def _enrich_pdf_record_with_current_market(record: dict, market_df: pd.DataFrame) -> dict:
    """Upgrade any saved simulation to the current PDF/positive-month contract."""
    upgraded = json.loads(json.dumps(record))
    required_layout = "MarketScope Portfolio Split Simulator v37 - v5.9.82 monthly reset + monthly start-year RB/NR depletion dashboard + continuous monthly start-year paths + start-year RB/NR depletion dashboard + split start-year strategies + persistent Build Simulation withdrawal tabs + annual and monthly reset views + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1"
    upgraded["_force_pdf_rebuild"] = str(record.get("pdf_layout") or "") != required_layout
    upgraded["app_version"] = MARKETSCOPE_VERSION

    # Repair old v5.9.48 records: the monthly schedules contained real return rows,
    # but the result dictionaries did not persist positive_months/months_modeled.
    for result_key, schedule_key in (
        ("monthly_withdrawal_rebalanced", "monthly_withdrawal_rebalanced_schedule"),
        ("monthly_withdrawal_not_rebalanced", "monthly_withdrawal_not_rebalanced_schedule"),
    ):
        result = dict(upgraded.get(result_key) or {})
        schedule = [dict(x) for x in (upgraded.get(schedule_key) or result.get("schedule") or []) if isinstance(x, dict)]
        if schedule:
            positive = sum(1 for row in schedule if float(row.get("portfolio_return_pct") or 0.0) > 0.0)
            result["positive_months"] = int(positive)
            result["months_modeled"] = int(len(schedule))
            result["schedule"] = schedule
            upgraded[result_key] = result
            upgraded[schedule_key] = schedule

    instruments = list(upgraded.get("instruments") or [])
    symbols = tuple(dict.fromkeys(str(item.get("symbol") or "").upper().strip() for item in instruments if str(item.get("symbol") or "").strip()))
    if symbols:
        # Prefer the exact years represented by a saved monthly schedule. Otherwise
        # derive the requested completed-year horizon from the saved period.
        schedule_years = []
        for key in ("monthly_withdrawal_rebalanced_schedule", "monthly_withdrawal_not_rebalanced_schedule"):
            for row in upgraded.get(key) or []:
                year = str(row.get("year") or "").strip()
                if year.isdigit() and year not in schedule_years:
                    schedule_years.append(year)
        if schedule_years:
            monthly_years = tuple(sorted(schedule_years))
        else:
            period_text = str(upgraded.get("period") or "10Y").upper()
            try:
                year_count = max(1, min(ANNUAL_HISTORY_YEARS, int(period_text.replace("Y", ""))))
            except Exception:
                year_count = 10
            monthly_years = tuple(YEAR_RETURN_COLS[:year_count])
        try:
            actual_payload = cached_actual_monthly_returns(symbols, monthly_years)
        except Exception:
            actual_payload = {"unavailable": True}
        if not actual_payload.get("unavailable"):
            for item in instruments:
                sym = str(item.get("symbol") or "").upper().strip()
                month_map = (actual_payload.get("returns") or {}).get(sym) or {}
                values = [float(v) for v in month_map.values() if v is not None and np.isfinite(v)]
                if values:
                    item["positive_months"] = int(sum(1 for v in values if v > 0.0))
                    item["available_months"] = int(len(values))

    if market_df is not None and not market_df.empty:
        lookup_source = _hydrate_price_targets(market_df, symbols) if symbols else market_df.copy()
        if symbols:
            lookup_source = _apply_remembered_price_targets(lookup_source, symbols)
        lookup_df = lookup_source.copy()
        lookup_df["Symbol"] = lookup_df["Symbol"].astype(str).str.upper().str.strip()
        lookup_df = lookup_df.drop_duplicates("Symbol", keep="last").set_index("Symbol", drop=False)
        for item in instruments:
            sym = str(item.get("symbol") or "").upper().strip()
            if sym not in lookup_df.index:
                continue
            row = lookup_df.loc[sym]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            item["name"] = str(row.get("Name") or item.get("name") or sym)
            item["sector"] = str(row.get("Sector") or item.get("sector") or "")
            item["analyst_rating"] = str(row.get("Analyst Rating") or item.get("analyst_rating") or "Not Rated")
            item["history_verification"] = str(row.get("History Verification") or item.get("history_verification") or "Pending")
            item["verification_coverage"] = str(row.get("Verification Coverage") or item.get("verification_coverage") or "")
            item["verification_exceptions"] = str(row.get("Verification Exceptions") or item.get("verification_exceptions") or "")
            item["verification_source"] = str(row.get("Verification Source") or item.get("verification_source") or "")
            _max_diff = pd.to_numeric(pd.Series([row.get("Max Verification Diff (pp)")]), errors="coerce").iloc[0]
            item["max_verification_diff_pp"] = float(_max_diff) if pd.notna(_max_diff) and np.isfinite(_max_diff) else None
            performance = dict(item.get("performance") or {})
            for metric in PERF_COLS:
                val = pd.to_numeric(pd.Series([row.get(metric)]), errors="coerce").iloc[0]
                performance[metric] = float(val) if pd.notna(val) and np.isfinite(val) else None
            item["performance"] = performance
            for key, col in (("current_price", "Price"), ("price_target_low", "Price Target Low"), ("price_target_average", "Price Target Average"), ("price_target_high", "Price Target High")):
                val = pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").iloc[0]
                if pd.notna(val):
                    item[key] = float(val)

    upgraded["instruments"] = instruments
    upgraded["pdf_layout"] = required_layout
    return upgraded


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def cached_etf_holdings(symbol: str) -> list[dict]:
    """Fetch ETF holdings only when the user taps the Holdings button."""
    try:
        return provider.get_top_holdings(symbol)
    except Exception:
        return []


@st.cache_data(ttl=10 * 60, show_spinner=False)
def cached_recent_news(symbol: str, company_name: str, instrument_type: str) -> list[dict]:
    # News is intentionally fetched only when the user opens the News panel.
    # This keeps the dashboard fast and avoids hundreds of background requests.
    items = provider.get_recent_news(symbol, company_name=company_name, max_items=12)
    return _directional_news_items(items, instrument_type=instrument_type, max_items=3)


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_single_metrics(symbol: str) -> dict:
    symbol = str(symbol).strip().upper()
    histories = provider.download_daily_history_since([symbol], start=ANNUAL_HISTORY_START, chunk_size=1)
    hist = histories.get(symbol)
    if hist is None or hist.empty:
        return {}
    perf = calculate_performance(hist)
    annual_returns = calculate_calendar_year_returns(hist, years=ANNUAL_HISTORY_YEARS)
    meta = default_meta.get(symbol, {})
    provider_meta = provider.get_metadata(symbol)
    quote_type = provider_meta.get("quote_type")
    instrument_type = meta.get("Type") or ("ETF" if quote_type in {"ETF", "MUTUALFUND"} else "Stock")
    rating = meta.get("Analyst Rating") or "Not Rated"
    rating_source = meta.get("Rating Source") or ""
    rating_updated = meta.get("Rating Updated ET") or "—"
    try:
        if instrument_type == "Stock":
            rating_map = nasdaq.get_stock_rating_map([symbol])
            rating = rating_map.get(symbol, "Not Rated")
            rating_source = (
                "Nasdaq Stock Screener analyst consensus"
                if rating != "Not Rated"
                else "Nasdaq Stock Screener — no consensus rating returned"
            )
            rating_updated = format_et()
        else:
            etf_rating = nasdaq.get_etf_rating_map([symbol]).get(symbol)
            if etf_rating:
                rating = etf_rating
                rating_source = "Nasdaq ETF Screener analyst field"
                rating_updated = format_et()
            else:
                rating = "Not Rated"
                rating_source = "Nasdaq ETF Screener — no stock-style analyst consensus"
    except Exception:
        pass

    latest_date = pd.to_datetime(hist.index[-1])
    try:
        latest_date = latest_date.tz_localize(None)
    except TypeError:
        try:
            latest_date = latest_date.tz_convert(None)
        except TypeError:
            pass

    signals = calculate_buy_signals(hist, analyst_rating=rating, instrument_type=instrument_type)
    stamp = format_et()
    return {
        "Symbol": symbol,
        "Name": meta.get("Name") or provider_meta.get("name") or symbol,
        "Sector": meta.get("Sector") or provider_meta.get("sector") or "Unknown",
        "Industry": meta.get("Industry") or provider_meta.get("industry") or "Unknown",
        "Type": instrument_type,
        "MarketCap": meta.get("MarketCap", np.nan),
        "Price": perf.current_price,
        "NAV": provider_meta.get("nav_price"),
        "Analyst Rating": rating,
        "Rating Source": rating_source,
        "Rating Updated ET": rating_updated,
        "Price Target Low": provider_meta.get("target_low_price") if instrument_type == "Stock" else np.nan,
        "Price Target Average": provider_meta.get("target_mean_price") if instrument_type == "Stock" else np.nan,
        "Price Target High": provider_meta.get("target_high_price") if instrument_type == "Stock" else np.nan,
        "Price Target Updated ET": stamp if instrument_type == "Stock" else "—",
        "Since Inception": as_percent(perf.since_inception),
        "1D": as_percent(perf.perf_1d),
        "1M": as_percent(perf.perf_1m),
        "3M": as_percent(perf.perf_3m),
        "6M": as_percent(perf.perf_6m),
        "YTD": as_percent(perf.ytd),
        **{year: as_percent(annual_returns.get(year)) for year in YEAR_RETURN_COLS},
        "Short Buy": signals.short_buy,
        "Long Buy": signals.long_buy,
        "Fundamental Buy": signals.fundamental_buy,
        "Short Signal New": signals.short_buy,
        "Long Signal New": signals.long_buy,
        "Signal Reasons": signals.reasons,
        "Signal Updated ET": stamp,
        "Return Basis": "Adjusted market total return" if instrument_type == "ETF" else "Adjusted total return",
        "Inception Date": perf.inception_date.date().isoformat() if perf.inception_date is not None else "—",
        "Exchange": provider_meta.get("exchange") or "",
        "Data As Of": latest_date.date().isoformat(),
        "Snapshot Updated ET": stamp,
        "Universe Source": meta.get("Source", "Yahoo search / manual persistent add"),
    }


def blank_row(symbol: str) -> dict:
    meta = default_meta.get(symbol, {})
    instrument_type = meta.get("Type", "Unknown")
    return {
        "Symbol": symbol,
        "Name": meta.get("Name", symbol),
        "Sector": meta.get("Sector", "Unknown"),
        "Industry": meta.get("Industry", "Unknown"),
        "Type": instrument_type,
        "MarketCap": pd.to_numeric(meta.get("MarketCap"), errors="coerce"),
        "Price": np.nan,
        "NAV": np.nan,
        "Analyst Rating": meta.get("Analyst Rating") or "Not Rated",
        "Rating Source": meta.get("Rating Source") or "",
        "Rating Updated ET": meta.get("Rating Updated ET") or "—",
        "Price Target Low": np.nan,
        "Price Target Average": np.nan,
        "Price Target High": np.nan,
        "Price Target Updated ET": "—",
        **{c: np.nan for c in ALL_RETURN_COLS},
        "Short Buy": False,
        "Long Buy": False,
        "Fundamental Buy": False,
        "Short Signal New": False,
        "Long Signal New": False,
        "Signal Reasons": "",
        "Signal Updated ET": "",
        "Return Basis": "Adjusted market total return" if instrument_type == "ETF" else "Adjusted total return",
        "Inception Date": "—",
        "Exchange": "",
        "Data As Of": "—",
        "Snapshot Updated ET": "—",
        "Universe Source": meta.get("Source", ""),
    }


def assemble_market(symbols: List[str], snapshot: pd.DataFrame) -> pd.DataFrame:
    snap = snapshot.set_index("Symbol", drop=False).to_dict(orient="index") if not snapshot.empty else {}
    rows = []
    for symbol in symbols:
        rows.append(dict(st.session_state.session_rows.get(symbol) or snap.get(symbol) or blank_row(symbol)))
    df = pd.DataFrame(rows)
    for col in ["MarketCap", "Price", "NAV", *PRICE_TARGET_COLS] + ALL_RETURN_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "Analyst Rating" not in df.columns:
        df["Analyst Rating"] = "Not Rated"
    for col in SIGNAL_COLS + ["Short Signal New", "Long Signal New"]:
        if col not in df.columns:
            df[col] = False
        df[col] = df[col].fillna(False).astype(bool)
    return df


def apply_live_overlay(df: pd.DataFrame, prices: Dict[str, float]) -> pd.DataFrame:
    if df.empty or not prices:
        return df
    out = df.copy()
    today_et = now_et().date().isoformat()
    for idx, row in out.iterrows():
        live = prices.get(row.get("Symbol"))
        if live is None or not np.isfinite(live) or live <= 0:
            continue

        old = row.get("Price")
        old_is_valid = old is not None and pd.notna(old) and np.isfinite(float(old)) and float(old) > 0
        if old_is_valid:
            ratio = float(live) / float(old)
            for col in ["Since Inception", "YTD", "6M", "3M", "1M"]:
                value = row.get(col)
                if value is not None and pd.notna(value):
                    out.at[idx, col] = ((1.0 + float(value) / 100.0) * ratio - 1.0) * 100.0
            if str(row.get("Data As Of", "")) != today_et:
                out.at[idx, "1D"] = (ratio - 1.0) * 100.0

        out.at[idx, "Price"] = float(live)
        out.at[idx, "Snapshot Updated ET"] = format_et()
    return out

def style_return(v):
    if v is None or pd.isna(v):
        return "color: #94a3b8;"
    if float(v) > 0:
        return "background-color: rgba(22,163,74,.28); color:#dcfce7; font-weight:700;"
    if float(v) < 0:
        return "background-color: rgba(220,38,38,.27); color:#fee2e2; font-weight:700;"
    return "background-color: rgba(100,116,139,.18); color:#e2e8f0; font-weight:700;"


def style_rating(v):
    text = str(v or "").strip().lower()
    if text in {"strong buy", "buy"}:
        return "background-color: rgba(22,163,74,.34); color:#dcfce7; font-weight:800;"
    if text == "hold":
        return "background-color: rgba(234,179,8,.32); color:#fef9c3; font-weight:800;"
    if text in {"sell", "strong sell"}:
        return "background-color: rgba(220,38,38,.34); color:#fee2e2; font-weight:800;"
    return "background-color: rgba(100,116,139,.18); color:#cbd5e1; font-weight:700;"


def style_signal(v):
    if bool(v):
        return "background-color: rgba(22,163,74,.34); color:#dcfce7; font-weight:800;"
    return "color:#94a3b8;"


def format_pct(v):
    return "—" if v is None or pd.isna(v) else f"{v:+.2f}%"


_POSITIVE_NEWS_RULES = [
    (("beat estimates", "beats estimates", "earnings beat", "revenue beat", "tops estimates", "better than expected"), "earnings/revenue beat"),
    (("raises guidance", "raised guidance", "boosts guidance", "raises outlook", "raised outlook", "boosts outlook"), "management raised guidance/outlook"),
    (("upgrade", "upgraded", "price target raised", "raises price target"), "analyst upgrade or higher price target"),
    (("fda approval", "approved by", "wins approval", "regulatory approval"), "regulatory approval"),
    (("record revenue", "record profit", "record earnings", "record sales"), "record financial performance"),
    (("wins contract", "awarded contract", "new contract", "strategic partnership", "major partnership"), "new commercial contract/partnership"),
    (("buyback", "share repurchase", "dividend increase", "raises dividend", "increases dividend"), "shareholder capital return"),
    (("margin expansion", "profit growth", "revenue growth", "free cash flow growth"), "improving fundamental growth/profitability"),
]
_NEGATIVE_NEWS_RULES = [
    (("misses estimates", "missed estimates", "earnings miss", "revenue miss", "below estimates", "worse than expected"), "earnings/revenue miss"),
    (("cuts guidance", "cut guidance", "lowers guidance", "lowered guidance", "cuts outlook", "lowers outlook"), "management reduced guidance/outlook"),
    (("downgrade", "downgraded", "price target cut", "cuts price target"), "analyst downgrade or lower price target"),
    (("investigation", "probe", "lawsuit", "sued", "antitrust", "sec charges"), "legal/regulatory risk"),
    (("recall", "data breach", "cyberattack", "hack", "production halt"), "operational/security risk"),
    (("bankruptcy", "default", "liquidity warning", "going concern"), "solvency/liquidity risk"),
    (("warning", "profit warning", "sales decline", "revenue decline", "profit decline", "demand weakens"), "deteriorating business trend"),
    (("share offering", "stock offering", "dilution", "dilutive"), "share dilution risk"),
]


def _news_timestamp(value) -> pd.Timestamp | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float, np.integer, np.floating)) and np.isfinite(value):
            ts = pd.to_datetime(float(value), unit="s", utc=True, errors="coerce")
        else:
            ts = pd.to_datetime(value, utc=True, errors="coerce")
        return None if pd.isna(ts) else pd.Timestamp(ts)
    except Exception:
        return None


def _classify_news_impact(title: str, summary: str = "") -> tuple[str, str, int]:
    title_text = str(title or "").lower()
    summary_text = str(summary or "").lower()
    pos_score = 0
    neg_score = 0
    pos_reason = ""
    neg_reason = ""
    for terms, reason in _POSITIVE_NEWS_RULES:
        hits_title = any(term in title_text for term in terms)
        hits_summary = any(term in summary_text for term in terms)
        if hits_title or hits_summary:
            pos_score += 2 if hits_title else 1
            pos_reason = pos_reason or reason
    for terms, reason in _NEGATIVE_NEWS_RULES:
        hits_title = any(term in title_text for term in terms)
        hits_summary = any(term in summary_text for term in terms)
        if hits_title or hits_summary:
            neg_score += 2 if hits_title else 1
            neg_reason = neg_reason or reason
    if pos_score > neg_score and pos_score > 0:
        return "UP", pos_reason or "positive fundamental catalyst", pos_score - neg_score
    if neg_score > pos_score and neg_score > 0:
        return "DOWN", neg_reason or "negative fundamental catalyst", neg_score - pos_score
    return "NEUTRAL", "no clear directional fundamental catalyst detected", 0


def _directional_news_items(items: list[dict], instrument_type: str, max_items: int = 3) -> list[dict]:
    now_utc = pd.Timestamp.now(tz="UTC")
    ranked: list[dict] = []
    for item in items or []:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        summary = str(item.get("summary") or "").strip()
        direction, reason, score = _classify_news_impact(title, summary)
        if direction == "NEUTRAL":
            continue
        ts = _news_timestamp(item.get("published"))
        if ts is not None:
            age_days = (now_utc - ts).total_seconds() / 86400.0
            if age_days < -1 or age_days > 7:
                continue
        enriched = dict(item)
        enriched.update({"direction": direction, "reason": reason, "impact_score": score, "published_ts": ts})
        ranked.append(enriched)
    ranked.sort(
        key=lambda item: (
            int(item.get("impact_score") or 0),
            item.get("published_ts") or pd.Timestamp("1970-01-01", tz="UTC"),
        ),
        reverse=True,
    )
    return ranked[:max_items]


def _news_time_display(ts: pd.Timestamp | None) -> str:
    if ts is None:
        return "Recent"
    try:
        local = ts.tz_convert("America/New_York") if ts.tzinfo else ts.tz_localize("UTC").tz_convert("America/New_York")
        return local.strftime("%b %d, %Y %I:%M %p %Z")
    except Exception:
        return "Recent"


def _news_panel_html(symbol: str, items: list[dict]) -> str:
    if not items:
        return (
            '<div class="news-panel"><div class="news-panel-title">NEWS IMPACT</div>'
            '<div class="news-empty">No clear UP/DOWN fundamental catalyst was detected in the latest 7-day Yahoo Finance news feed. Neutral or ambiguous headlines are intentionally not forced into a bullish/bearish label.</div></div>'
        )
    blocks = []
    for item in items:
        direction = str(item.get("direction") or "").upper()
        is_up = direction == "UP"
        arrow = "▲" if is_up else "▼"
        klass = "news-up" if is_up else "news-down"
        publisher = escape(str(item.get("publisher") or "Yahoo Finance feed"))
        title = escape(str(item.get("title") or "Untitled news"))
        reason = escape(str(item.get("reason") or "directional fundamental catalyst"))
        published = escape(_news_time_display(item.get("published_ts")))
        url = str(item.get("url") or "").strip()
        if url.startswith("https://") or url.startswith("http://"):
            headline = f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{title}</a>'
        else:
            headline = title
        blocks.append(
            f'<div class="news-item {klass}">'
            f'<div class="news-direction">{arrow} {direction} DRIVER</div>'
            f'<div class="news-headline">{headline}</div>'
            f'<div class="news-subline">{publisher} • {published}</div>'
            f'<div class="news-subline">Driver: {reason}</div>'
            f'<div class="news-subline">Directional read: {"positive" if is_up else "negative"} fundamental pressure; not a guaranteed price move.</div>'
            '</div>'
        )
    return '<div class="news-panel"><div class="news-panel-title">NEWS IMPACT • ' + escape(symbol) + '</div>' + ''.join(blocks) + '</div>'


def _holdings_panel_html(symbol: str, items: list[dict]) -> str:
    if not items:
        return (
            '<div class="holdings-panel"><div class="holdings-panel-title">TOP HOLDINGS • ' + escape(symbol) + '</div>'
            '<div class="holdings-empty">Yahoo Finance did not return fund holdings for this ETF right now.</div></div>'
        )
    count = len(items)
    label = 'TOP 10 HOLDINGS' if count >= 10 else ('TOP 5 HOLDINGS' if count >= 5 else f'TOP {count} HOLDINGS')
    rows = []
    for rank, item in enumerate(items, start=1):
        ticker = escape(str(item.get('symbol') or '—'))
        name = escape(str(item.get('name') or ticker))
        weight = item.get('weight_pct')
        try:
            weight_text = f'{float(weight):.2f}%' if weight is not None and np.isfinite(float(weight)) else '—'
        except Exception:
            weight_text = '—'
        rows.append(
            '<div class="holding-row">'
            f'<span class="holding-rank">{rank}</span>'
            f'<span class="holding-id"><b>{ticker}</b><small>{name}</small></span>'
            f'<span class="holding-weight">{escape(weight_text)}</span>'
            '</div>'
        )
    return (
        '<div class="holdings-panel">'
        f'<div class="holdings-panel-title">{label} • {escape(symbol)}</div>'
        '<div class="holdings-subtitle">Portfolio weight shown when Yahoo provides it.</div>'
        + ''.join(rows) +
        '</div>'
    )


def _filter_history_for_calendar_year(history: pd.DataFrame, year: int) -> pd.DataFrame:
    if history is None or history.empty:
        return pd.DataFrame()
    frame = history.copy()
    idx = pd.to_datetime(frame.index, errors="coerce")
    valid = ~pd.isna(idx)
    frame = frame.loc[valid].copy()
    idx = idx[valid]
    try:
        idx = idx.tz_localize(None)
    except TypeError:
        try:
            idx = idx.tz_convert(None)
        except TypeError:
            pass
    frame.index = idx
    return frame.loc[frame.index.year == int(year)].sort_index()


def _year_chart_stats(history: pd.DataFrame) -> dict | None:
    if history is None or history.empty or "Close" not in history.columns:
        return None
    close = pd.to_numeric(history["Close"], errors="coerce").dropna()
    if close.empty:
        return None
    start = float(close.iloc[0])
    end = float(close.iloc[-1])
    pct = ((end / start) - 1.0) * 100.0 if start > 0 else np.nan
    return {
        "start": start,
        "end": end,
        "return_pct": pct,
        "high": float(close.max()),
        "low": float(close.min()),
        "days": int(len(close)),
    }


def local_search(query: str, max_results: int = 12) -> List[dict]:
    q = str(query).strip().lower()
    if not q:
        return []
    df = default_universe.copy()
    mask = (
        df["Symbol"].astype(str).str.lower().str.contains(q, regex=False)
        | df["Name"].astype(str).str.lower().str.contains(q, regex=False)
    )
    matches = df.loc[mask].head(max_results)
    return [
        {
            "symbol": r.Symbol,
            "name": r.Name,
            "quote_type": "ETF" if r.Type == "ETF" else "EQUITY",
            "exchange": "",
            "local": True,
        }
        for r in matches.itertuples(index=False)
    ]


def merge_row_into_snapshot(snapshot: pd.DataFrame, row: dict) -> pd.DataFrame:
    base = snapshot.copy() if snapshot is not None else pd.DataFrame()
    symbol = str(row.get("Symbol", "")).upper()
    if not base.empty and "Symbol" in base.columns:
        base = base[base["Symbol"].astype(str).str.upper() != symbol]
    return _normalize_snapshot(pd.concat([base, pd.DataFrame([row])], ignore_index=True))


def merge_prefer_incoming_snapshot(base: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    """Merge a durable snapshot into the current table, incoming rows win.

    This is used before manual refresh so a populated GitHub snapshot is never
    replaced by an empty bootstrap/Render copy when Yahoo throttles the request.
    Manually added rows that exist only in the current table are preserved.
    """
    base = _normalize_snapshot(base)
    incoming = _normalize_snapshot(incoming)
    if incoming.empty:
        return base
    if base.empty:
        return incoming
    incoming_symbols = set(incoming["Symbol"].astype(str).str.upper())
    keep = base[~base["Symbol"].astype(str).str.upper().isin(incoming_symbols)]
    return _normalize_snapshot(pd.concat([keep, incoming], ignore_index=True, sort=False))


def _history_date(value) -> str:
    ts = pd.to_datetime(value)
    try:
        ts = ts.tz_localize(None)
    except TypeError:
        try:
            ts = ts.tz_convert(None)
        except TypeError:
            pass
    return ts.date().isoformat()


def apply_history_refresh(df: pd.DataFrame, histories: Dict[str, pd.DataFrame], symbols: List[str], stamp: str) -> tuple[pd.DataFrame, int]:
    """Populate performance metrics and buy-signal state from adjusted daily history."""
    out = df.copy()
    success = 0
    for symbol in symbols:
        hist = histories.get(symbol)
        if hist is None or hist.empty:
            continue
        mask = out["Symbol"].astype(str).str.upper().eq(symbol)
        if not mask.any():
            continue
        try:
            perf = calculate_performance(hist)
            annual_returns = calculate_calendar_year_returns(hist, years=ANNUAL_HISTORY_YEARS)
        except Exception:
            continue
        idx = out.index[mask][0]
        old_short = bool(out.at[idx, "Short Buy"]) if "Short Buy" in out.columns and pd.notna(out.at[idx, "Short Buy"]) else False
        old_long = bool(out.at[idx, "Long Buy"]) if "Long Buy" in out.columns and pd.notna(out.at[idx, "Long Buy"]) else False
        rating = out.at[idx, "Analyst Rating"] if "Analyst Rating" in out.columns else "Not Rated"
        instrument_type = out.at[idx, "Type"] if "Type" in out.columns else "Stock"
        signals = calculate_buy_signals(hist, analyst_rating=rating, instrument_type=instrument_type)

        out.at[idx, "Price"] = perf.current_price
        out.at[idx, "1D"] = as_percent(perf.perf_1d)
        out.at[idx, "1M"] = as_percent(perf.perf_1m)
        out.at[idx, "3M"] = as_percent(perf.perf_3m)
        out.at[idx, "6M"] = as_percent(perf.perf_6m)
        out.at[idx, "YTD"] = as_percent(perf.ytd)
        for year in YEAR_RETURN_COLS:
            fresh_value = as_percent(annual_returns.get(year))
            parsed_fresh = pd.to_numeric(pd.Series([fresh_value]), errors="coerce").iloc[0]
            if pd.notna(parsed_fresh) and np.isfinite(parsed_fresh):
                out.at[idx, year] = float(parsed_fresh)
            else:
                # Do not erase a previously verified annual return because one
                # refresh was temporarily truncated or rate-limited by Yahoo.
                prior_value = pd.to_numeric(pd.Series([out.at[idx, year]]), errors="coerce").iloc[0]
                if pd.isna(prior_value):
                    out.at[idx, year] = np.nan
        out.at[idx, "Short Buy"] = signals.short_buy
        out.at[idx, "Long Buy"] = signals.long_buy
        out.at[idx, "Fundamental Buy"] = signals.fundamental_buy
        out.at[idx, "Short Signal New"] = bool(signals.short_buy and not old_short)
        out.at[idx, "Long Signal New"] = bool(signals.long_buy and not old_long)
        out.at[idx, "Signal Reasons"] = signals.reasons
        out.at[idx, "Signal Updated ET"] = stamp
        out.at[idx, "Data As Of"] = _history_date(hist.index[-1])
        out.at[idx, "Snapshot Updated ET"] = stamp
        success += 1
    return out, success

def _safe_message(value, fallback: str) -> str:
    text = _valid_status_text(value)
    return text or fallback


def refresh_ratings(df: pd.DataFrame, symbols: List[str]) -> pd.DataFrame:
    out = df.copy()
    target = out[out["Symbol"].isin(symbols)]
    stock_symbols = target.loc[target["Type"].eq("Stock"), "Symbol"].tolist()
    etf_symbols = target.loc[target["Type"].eq("ETF"), "Symbol"].tolist()
    stamp = format_et()

    if stock_symbols:
        try:
            stock_map = nasdaq.get_stock_rating_map(stock_symbols)
            stock_mask = out["Symbol"].isin(stock_symbols)
            out.loc[stock_mask, "Analyst Rating"] = "Not Rated"
            out.loc[stock_mask, "Rating Source"] = "Nasdaq Stock Screener — no consensus rating returned"
            out.loc[stock_mask, "Rating Updated ET"] = stamp
            for symbol, rating in stock_map.items():
                mask = out["Symbol"].eq(symbol)
                out.loc[mask, "Analyst Rating"] = rating
                out.loc[mask, "Rating Source"] = "Nasdaq Stock Screener analyst consensus"
        except Exception:
            pass

    if etf_symbols:
        try:
            etf_map = nasdaq.get_etf_rating_map(etf_symbols)
            etf_mask = out["Symbol"].isin(etf_symbols)
            out.loc[etf_mask, "Analyst Rating"] = "Not Rated"
            out.loc[etf_mask, "Rating Source"] = "Nasdaq ETF Screener — no stock-style analyst consensus"
            out.loc[etf_mask, "Rating Updated ET"] = stamp
            for symbol, rating in etf_map.items():
                mask = out["Symbol"].eq(symbol)
                out.loc[mask, "Analyst Rating"] = rating
                out.loc[mask, "Rating Source"] = "Nasdaq ETF Screener analyst field"
        except Exception:
            pass
    return out


def refresh_price_targets(df: pd.DataFrame, symbols: List[str]) -> pd.DataFrame:
    """Refresh Yahoo analyst price-target low/average/high for stock rows only.

    Existing target values are preserved when Yahoo does not return a fresh value.
    ETFs intentionally remain blank because stock-style analyst price targets are
    not consistently available for funds.
    """
    out = df.copy()
    target = out[out["Symbol"].isin(symbols)]
    stock_symbols = target.loc[target["Type"].astype(str).str.upper().eq("STOCK"), "Symbol"].astype(str).tolist()
    if not stock_symbols:
        return out
    try:
        target_map = provider.get_price_targets_many(stock_symbols, max_workers=6)
    except Exception:
        target_map = {}
    if not target_map:
        return out
    stamp = format_et()
    for symbol, values in target_map.items():
        if not isinstance(values, dict):
            continue
        mask = out["Symbol"].astype(str).eq(symbol)
        if not mask.any():
            continue
        wrote = False
        for source_key, col in (("low", "Price Target Low"), ("mean", "Price Target Average"), ("high", "Price Target High")):
            value = pd.to_numeric(pd.Series([values.get(source_key)]), errors="coerce").iloc[0]
            if pd.notna(value) and np.isfinite(value) and float(value) > 0:
                out.loc[mask, col] = float(value)
                wrote = True
        if wrote:
            out.loc[mask, "Price Target Updated ET"] = stamp
    return out


def apply_dynamic_filters(df: pd.DataFrame, display_cols: List[str]) -> pd.DataFrame:
    out = df.copy()
    with st.expander("Advanced filters — every table column", expanded=False):
        st.caption(
            "Choose any displayed card fields. Numeric fields get min/max filters; "
            "text/categorical fields get value or contains filters. Card sort buttons remain available below."
        )
        chosen = st.pills("Columns to filter", display_cols, selection_mode="multi", key="advanced_filter_columns", format_func=timeframe_display_label) or []
        for col in chosen:
            if col not in out.columns:
                continue
            series = out[col]
            if pd.api.types.is_numeric_dtype(series):
                c1, c2 = st.columns(2)
                min_text = c1.text_input(f"{col} minimum", key=f"fmin_{col}", placeholder="No minimum")
                max_text = c2.text_input(f"{col} maximum", key=f"fmax_{col}", placeholder="No maximum")
                try:
                    if min_text.strip():
                        numeric = pd.to_numeric(out[col], errors="coerce")
                        out = out[numeric >= float(min_text.replace(",", ""))]
                    if max_text.strip():
                        numeric = pd.to_numeric(out[col], errors="coerce")
                        out = out[numeric <= float(max_text.replace(",", ""))]
                except ValueError:
                    st.warning(f"{col}: enter numeric min/max values only.")
            else:
                unique = sorted(x for x in series.dropna().astype(str).unique().tolist() if x and x != "nan")
                if len(unique) <= 30:
                    values = st.pills(
                        f"{col} values", unique, selection_mode="multi", key=f"fcat_{col}"
                    ) or []
                    if values:
                        out = out[out[col].astype(str).isin(values)]
                else:
                    text = st.text_input(f"{col} contains", key=f"ftext_{col}")
                    if text:
                        out = out[out[col].astype(str).str.contains(text, case=False, regex=False, na=False)]
    return out


st.markdown(
    f"""
<div class="hero">
  <div class="marketscope-brand-row">
    <div class="marketscope-logo" aria-label="MarketScope logo">
      <span class="marketscope-logo-bar bar-1"></span>
      <span class="marketscope-logo-bar bar-2"></span>
      <span class="marketscope-logo-bar bar-3"></span>
      <span class="marketscope-logo-line"></span>
    </div>
    <div class="marketscope-brand-copy">
      <h1>MarketScope</h1>
      <div class="marketscope-version">v{MARKETSCOPE_VERSION}</div>
    </div>
  </div>
  <p>Nasdaq stocks > $100B + ETFs • actual calendar-year returns • analyst consensus • persistent cloud snapshot</p>
  <span class="source-pill">● Nasdaq Stock Screener > $100B + Yahoo Finance • all displayed times: U.S. Eastern</span>
</div>
""",
    unsafe_allow_html=True,
)

snapshot = load_snapshot()
metadata = load_snapshot_metadata()
universe_metadata = load_universe_metadata()
universe_change_history = _merge_universe_change_history(
    load_universe_change_history(),
    _current_metadata_change_events(universe_metadata),
)
favorite_picks_history = load_favorite_picks_history()
favorite_picks_change_frame = favorite_change_history_frame(favorite_picks_history)
favorite_picks_run_frame = favorite_run_history_frame(favorite_picks_history)
base_symbols = default_universe["Symbol"].astype(str).str.upper().tolist()
snapshot_symbols = snapshot["Symbol"].tolist() if not snapshot.empty else []
extra_symbols = [s for s in st.session_state.extra_symbols if s not in set(base_symbols)]
symbols = list(dict.fromkeys(base_symbols + snapshot_symbols + extra_symbols))
market_base = assemble_market(symbols, snapshot)
market = apply_live_overlay(market_base, st.session_state.live_prices)

# v5.9.58: dynamic annual history is maintained by the same automatic snapshot
# refresh as every other market field. There is intentionally no separate repair
# task or user-facing backfill button. Missing pre-inception years remain blank.

# Nasdaq universe membership audit strip. The scheduled 6 PM ET workflow writes
# the refresh timestamp plus exact symbols crossing the >$100B screening boundary.
raw_universe_stamp = universe_metadata.get("refreshed_at_et")
universe_refreshed = "Pending first successful universe refresh"
try:
    parsed_universe_stamp = pd.to_datetime(raw_universe_stamp, errors="coerce")
    if pd.notna(parsed_universe_stamp):
        if getattr(parsed_universe_stamp, "tzinfo", None) is not None:
            parsed_universe_stamp = parsed_universe_stamp.tz_convert("America/New_York")
        date_label = parsed_universe_stamp.strftime("%b %d, %Y")
        hour_label = int(parsed_universe_stamp.strftime("%I"))
        universe_refreshed = f"{date_label} {hour_label}:{parsed_universe_stamp.strftime('%M')} {parsed_universe_stamp.strftime('%p')} ET"
except Exception:
    universe_refreshed = _valid_status_text(universe_metadata.get("refreshed_at_display_et")) or universe_refreshed
added_symbols = [str(x).upper() for x in (universe_metadata.get("added_symbols") or [])]
removed_symbols = [str(x).upper() for x in (universe_metadata.get("removed_symbols") or [])]
added_count = int(universe_metadata.get("added_count") or 0)
removed_count = int(universe_metadata.get("removed_count") or 0)
added_preview = ", ".join(added_symbols[:8]) or "None"
removed_preview = ", ".join(removed_symbols[:8]) or "None"
if len(added_symbols) > 8:
    added_preview += f" +{len(added_symbols)-8} more"
if len(removed_symbols) > 8:
    removed_preview += f" +{len(removed_symbols)-8} more"
rating_changes = universe_metadata.get("analyst_rating_changes") or []
rating_change_count = int(universe_metadata.get("analyst_rating_change_count") or len(rating_changes))
rating_change_preview_parts = []
for change in rating_changes[:8]:
    if not isinstance(change, dict):
        continue
    sym = str(change.get("symbol") or "").upper()
    old_rating = str(change.get("from") or "Not Rated")
    new_rating = str(change.get("to") or "Not Rated")
    rating_change_preview_parts.append(f"{sym}: {old_rating} → {new_rating}")
rating_change_preview = " • ".join(rating_change_preview_parts) or "None"
if len(rating_changes) > 8:
    rating_change_preview += f" • +{len(rating_changes)-8} more"
# New buy-signal alerts are generated only when a signal transitions from off to on.
new_signal_mask = (
    market.get("Short Signal New", pd.Series(False, index=market.index)).fillna(False).astype(bool)
    | market.get("Long Signal New", pd.Series(False, index=market.index)).fillna(False).astype(bool)
)
new_signal_alerts = market.loc[new_signal_mask].copy()
active_signal_mask = (
    market.get("Short Buy", pd.Series(False, index=market.index)).fillna(False).astype(bool)
    | market.get("Long Buy", pd.Series(False, index=market.index)).fillna(False).astype(bool)
)
active_signal_count = int(active_signal_mask.sum())

# v5.9.37: PDF Setup button removed from the app UI; server-side PDF persistence remains automatic.

# v5.11.2 adds permanent first-detected Favorite Picks and risk change trails.
# v5.11.1 adds the evidence-backed Favorite Picks sector ranking workspace.
# v5.11.0 keeps Future Projection safe while its unlimited holding selector is empty.
# v5.10.0 adds Future Projection without renaming or removing existing top-level workspaces.
# v5.9.24 compatibility contract previously used: market_tab, portfolio_tab, compare_tab, alerts_tab = st.tabs
_top_tab_labels = [
    "◈ Market Navigator",
    "Favorite Picks",
    "◫ Portfolio Simulator",
    "Future Projection",
    "⚖ Stock & ETF Comparison",
    "◈ Sector Performance",
    "🔔 Alerts & Help",
]
from runtime_performance import preserve_navigation_state
preserve_navigation_state()
if bool(st.session_state.pop("future_projection_focus", False)):
    st.session_state["workspace_navigation"] = "Future Projection"
    market_tab, favorite_tab, portfolio_tab, future_tab, compare_tab, sector_tab, alerts_tab = st.tabs(
        _top_tab_labels,
        default="Future Projection",
        key="workspace_navigation", on_change="rerun",
    )
else:
    market_tab, favorite_tab, portfolio_tab, future_tab, compare_tab, sector_tab, alerts_tab = st.tabs(_top_tab_labels, key="workspace_navigation", on_change="rerun")


with alerts_tab:
    if st.button(
        f"🔔 Buy Signal Alerts ({len(new_signal_alerts)} new)" if not st.session_state.buy_signal_alerts_open else "🔔 Hide Buy Signal Alerts",
        key="toggle_buy_signal_alerts",
        use_container_width=True,
        type="primary" if st.session_state.buy_signal_alerts_open else "secondary",
    ):
        st.session_state.buy_signal_alerts_open = not st.session_state.buy_signal_alerts_open
        st.rerun()

    if st.session_state.buy_signal_alerts_open:
        st.markdown("### Buy signal alerts")
        a1, a2, a3 = st.columns(3)
        a1.metric("New alerts", f"{len(new_signal_alerts):,}")
        a2.metric("Active buy signals", f"{active_signal_count:,}")
        a3.metric("Signal basis", "Technical + Nasdaq consensus")
        if len(new_signal_alerts):
            st.success(
                f"{len(new_signal_alerts):,} new informational buy signal(s) detected in the latest refresh. "
                "Short signals are technical; long signals use long-trend technical rules and Nasdaq analyst consensus for stocks."
            )
            alert_view = new_signal_alerts[[
                "Symbol", "Name", "Type", "Analyst Rating", "Short Buy", "Long Buy", "Signal Reasons"
            ]].copy()
            alert_view["Short Buy"] = alert_view["Short Buy"].map(lambda x: "BUY" if bool(x) else "")
            alert_view["Long Buy"] = alert_view["Long Buy"].map(lambda x: "BUY" if bool(x) else "")
            st.dataframe(alert_view, width="stretch", hide_index=True, height=min(320, 48 + 42 * len(alert_view)))
        else:
            st.info("No new buy-signal transition is recorded in the current snapshot. Existing active signals remain available in the table filters.")

with market_tab:
    st.markdown(
        '<div class="universe-status-strip">'
        f'<div><span>Nasdaq Universe Last Refreshed</span><b>{escape(universe_refreshed)}</b></div>'
        f'<div><span>Stocks Added / Removed Today</span><b>+{added_count} / -{removed_count}</b>'
        f'<small>Added: {escape(added_preview)} • Removed: {escape(removed_preview)}</small></div>'
        f'<div><span>Analyst Rating Changes</span><b>{rating_change_count}</b>'
        f'<small>{escape(rating_change_preview)}</small></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    six_month_history = _six_month_universe_history_frame(universe_change_history)
    all_time_universe_history = _six_month_universe_history_frame(universe_change_history, months=None)
    universe_refresh_col, universe_history_col, favorite_history_col, universe_help_col = st.columns([1.45, 1.45, 1.45, 2.65])
    with universe_refresh_col:
        refresh_universe_now = st.button(
            "↻ Refresh Nasdaq Universe Now",
            key="refresh_nasdaq_universe_now",
            use_container_width=True,
            help=(
                "Refresh Nasdaq >$100B stock membership and Nasdaq analyst ratings immediately. "
                "This uses the same universe generator as the scheduled workflow."
            ),
        )
    with universe_history_col:
        if st.button(
            (
                f"🕘 6-Month Change History ({len(six_month_history)})"
                if not st.session_state.universe_change_history_open
                else "🕘 Hide Change History"
            ),
            key="toggle_universe_change_history",
            use_container_width=True,
            help=(
                "Show stock additions/removals and analyst-rating changes recorded during the last six months. "
                "Older events remain permanently stored for historical purposes."
            ),
        ):
            st.session_state.universe_change_history_open = not st.session_state.universe_change_history_open
            st.rerun()
    with favorite_history_col:
        if st.button(
            (
                f"★ Pick Fav Change Trail ({len(favorite_picks_change_frame)})"
                if not st.session_state.favorite_picks_history_open
                else "★ Hide Pick Fav Trail"
            ),
            key="toggle_favorite_picks_history",
            use_container_width=True,
            help=(
                "Show the permanent, all-time Pick Fav replacement and risk-rating history. "
                "Each row keeps the date the change was first detected."
            ),
        ):
            st.session_state.favorite_picks_history_open = not st.session_state.favorite_picks_history_open
            st.rerun()
    with universe_help_col:
        st.caption(
            "Both ledgers are append-only. Stock additions/removals, analyst changes, Pick Fav replacements, "
            "and Favorite risk-rating changes keep their original first-detected date permanently."
        )

    if st.session_state.universe_change_history_open:
        st.markdown("### 🕘 Nasdaq Universe & Analyst Change History · Last 6 Months")
        st.caption(
            "Every recorded stock addition, stock removal, and analyst-rating change is listed below. "
            "Only the view is limited to six months; the underlying historical log is never pruned."
        )
        if six_month_history.empty:
            st.info(
                "No recorded Nasdaq universe or analyst-rating changes fall within the last six months yet. "
                "v5.9.78 begins durable history collection and migrates the latest change still present in universe metadata."
            )
        else:
            history_counts = six_month_history["Change Type"].value_counts()
            hc1, hc2, hc3, hc4 = st.columns(4)
            hc1.metric("Total changes", f"{len(six_month_history):,}")
            hc2.metric("Stocks added", f"{int(history_counts.get('Stock Added', 0)):,}")
            hc3.metric("Stocks removed", f"{int(history_counts.get('Stock Removed', 0)):,}")
            hc4.metric("Rating changes", f"{int(history_counts.get('Analyst Rating', 0)):,}")
            st.dataframe(
                six_month_history,
                use_container_width=True,
                hide_index=True,
                height=min(600, 72 + max(1, len(six_month_history)) * 35),
                column_config={"Date / Time (ET)": "First Detected (ET)"},
                key="nasdaq_six_month_change_history",
            )
        with st.expander(f"All-time stock and analyst archive ({len(all_time_universe_history):,} events retained)"):
            st.caption(
                "This permanent archive keeps every recorded stock addition, stock removal, and analyst-rating "
                "transition with its original First Detected date. Later refreshes do not replace that date."
            )
            if all_time_universe_history.empty:
                st.info("No permanent stock or analyst changes have been recorded yet.")
            else:
                st.dataframe(
                    all_time_universe_history,
                    use_container_width=True,
                    hide_index=True,
                    height=min(650, 72 + max(1, len(all_time_universe_history)) * 35),
                    column_config={"Date / Time (ET)": "First Detected (ET)"},
                    key="nasdaq_all_time_change_history",
                )

    if st.session_state.favorite_picks_history_open:
        st.markdown("### ★ Favorite Picks Permanent Change Trail · All Time")
        st.caption(
            "A replacement row identifies the stock that dropped and the new sector favorite. Risk changes are "
            "logged separately. Existing rows and their First Detected dates are never overwritten by later runs."
        )
        if favorite_picks_change_frame.empty:
            st.info(
                "No Favorite Picks history has been recorded yet. Select Pick Fav in the Favorite Picks tab, "
                "or allow the daily GitHub workflow to complete its first v5.11.2 run."
            )
        else:
            favorite_history_counts = favorite_picks_change_frame["Change Type"].value_counts()
            fh1, fh2, fh3, fh4 = st.columns(4)
            fh1.metric("Total retained events", f"{len(favorite_picks_change_frame):,}")
            fh2.metric("Replacements", f"{int(favorite_history_counts.get('Favorite Pick Replaced', 0)):,}")
            fh3.metric(
                "Adds / removals",
                f"{int(favorite_history_counts.get('Favorite Pick Added', 0) + favorite_history_counts.get('Initial Favorite Pick', 0)):,} / "
                f"{int(favorite_history_counts.get('Favorite Pick Removed', 0)):,}",
            )
            fh4.metric("Risk changes", f"{int(favorite_history_counts.get('Favorite Risk Rating Changed', 0)):,}")
            st.dataframe(
                favorite_picks_change_frame,
                use_container_width=True,
                hide_index=True,
                height=min(720, 72 + max(1, len(favorite_picks_change_frame)) * 35),
                key="favorite_picks_permanent_change_history",
            )
            with st.expander(f"Favorite Picks run audit ({len(favorite_picks_run_frame):,} runs retained)"):
                st.dataframe(
                    favorite_picks_run_frame,
                    use_container_width=True,
                    hide_index=True,
                    height=min(520, 72 + max(1, len(favorite_picks_run_frame)) * 35),
                    key="favorite_picks_run_history_main",
                )

    if refresh_universe_now:
        with st.spinner("Refreshing Nasdaq >$100B universe and analyst ratings..."):
            local_ok, durable_ok, refresh_message, _ = _run_manual_universe_refresh()
        st.session_state.universe_refresh_message = (local_ok, durable_ok, refresh_message)
        if local_ok:
            load_universe_metadata.clear()
            load_universe_change_history.clear()
            load_snapshot_metadata.clear()
        st.rerun()

    if st.session_state.universe_refresh_message:
        local_ok, durable_ok, message = st.session_state.universe_refresh_message
        if local_ok and durable_ok:
            st.success(message)
        elif local_ok:
            st.warning(message)
        else:
            st.error(message)
        st.session_state.universe_refresh_message = None

    # v5.9.13: Sidebar market controls/search removed for a cleaner full-width workspace.

    if st.session_state.persistence_message:
        ok, msg = st.session_state.persistence_message
        msg = _safe_message(
            msg,
            "Refresh completed on this server. Durable GitHub save status was not returned; check Render's MARKETSCOPE_GITHUB_TOKEN setting.",
        )
        (st.success if ok else st.warning)(msg)
        st.session_state.persistence_message = None

    if st.session_state.last_refresh_summary:
        summary_text = _safe_message(st.session_state.last_refresh_summary, "Refresh finished.")
        if "no usable historical or price data" in summary_text.lower():
            st.warning(summary_text)
        else:
            st.success(summary_text)
        st.session_state.last_refresh_summary = None

    st.info(
        "Analyst Rating: stocks use Nasdaq Stock Screener consensus buckets (Strong Buy / Buy / Hold / Sell / Strong Sell). "
        "Nasdaq's public ETF screener does not expose the same stock-style analyst consensus; ETFs remain Not Rated unless "
        "Nasdaq itself returns a genuine analyst/recommendation field."
    )

    # Quick filters — clickable controls instead of dropdowns.
    st.markdown("#### Quick filters")
    q1, q2 = st.columns([1.05, 1.6])
    with q1:
        instrument_filter = st.segmented_control(
            "Instrument", ["All", "Stocks", "ETFs"],
            default=(_query_scalar_early("instrument", "All") if _query_scalar_early("instrument", "All") in {"All", "Stocks", "ETFs"} else "All"),
            key="instrument_filter"
        )
    # Streamlit can return None if the active Instrument option is deselected.
    instrument_filter = instrument_filter or "All"

    with q2:
        cap_filter = st.segmented_control(
            "Stock market cap",
            ["> $100B", "> $200B", "> $500B", "> $1T"],
            default=(_query_scalar_early("cap", "> $100B") if _query_scalar_early("cap", "> $100B") in {"> $100B", "> $200B", "> $500B", "> $1T"} else "> $100B"),
            key="cap_filter",
            help="The Nasdaq stock universe already starts strictly above $100B. Higher buttons narrow it further. ETFs are not filtered by stock market cap.",
        )

    _rating_default = [x for x in _query_csv_early("ratings") if x in RATINGS]
    rating_filter = st.pills(
        "Analyst Rating", RATINGS, selection_mode="multi", default=_rating_default, key="rating_filter"
    ) or []
    _signal_options = ["Short-term Buy", "Long-term Buy", "New Signal"]
    _signal_default = [x for x in _query_csv_early("signals") if x in _signal_options]
    signal_filter = st.pills(
        "Buy signals", _signal_options, selection_mode="multi", default=_signal_default, key="signal_filter"
    ) or []
    stock_sector_rows = market.loc[market["Type"].astype(str).str.upper().eq("STOCK")]
    sectors = sorted(
        x for x in stock_sector_rows["Sector"].dropna().astype(str).unique().tolist()
        if x and x.lower() not in {"nan", "unknown", "etf / fund", "fund", "etf"}
    )
    _sector_default = [x for x in _query_csv_early("sectors") if x in sectors]
    selected_sectors = st.pills(
        "Sector", sectors, selection_mode="multi", default=_sector_default, key="sector_filter"
    ) or []

    filtered = market.copy()
    if selected_sectors:
        filtered = filtered[filtered["Sector"].isin(selected_sectors)]
    if instrument_filter == "ETFs":
        filtered = filtered[filtered["Type"].eq("ETF")]
    elif instrument_filter == "Stocks":
        filtered = filtered[filtered["Type"].eq("Stock")]
    if rating_filter:
        filtered = filtered[filtered["Analyst Rating"].isin(rating_filter)]
    if "Short-term Buy" in signal_filter:
        filtered = filtered[filtered["Short Buy"].fillna(False).astype(bool)]
    if "Long-term Buy" in signal_filter:
        filtered = filtered[filtered["Long Buy"].fillna(False).astype(bool)]
    if "New Signal" in signal_filter:
        filtered = filtered[
            filtered["Short Signal New"].fillna(False).astype(bool)
            | filtered["Long Signal New"].fillna(False).astype(bool)
        ]

    cap_thresholds = {
        "> $100B": 100_000_000_000,
        "> $200B": 200_000_000_000,
        "> $500B": 500_000_000_000,
        "> $1T": 1_000_000_000_000,
    }
    threshold = cap_thresholds[cap_filter]
    cap_values = pd.to_numeric(filtered["MarketCap"], errors="coerce")
    if cap_filter == "> $100B" and "Universe Source" in filtered.columns:
        manual_mask = filtered["Universe Source"].astype(str).str.contains("manual", case=False, regex=False, na=False)
    else:
        manual_mask = pd.Series(False, index=filtered.index)
    filtered = filtered[(filtered["Type"].eq("ETF")) | (cap_values > threshold) | manual_mask]
    filtered["Market Cap ($B)"] = pd.to_numeric(filtered["MarketCap"], errors="coerce") / 1_000_000_000
    DISPLAY_COLS = [
        "Symbol", "Name", "Type", "Sector", "Industry", "Analyst Rating", "Short Buy", "Long Buy",
        "Market Cap ($B)", "Price",
        *PERF_COLS,
    ]
    filtered = apply_dynamic_filters(filtered, DISPLAY_COLS)

    valid_prices = pd.to_numeric(market["Price"], errors="coerce").notna()
    stock_count = int((default_universe["Type"] == "Stock").sum())
    etf_count = int((default_universe["Type"] == "ETF").sum())
    rated_count = int(market["Analyst Rating"].isin(["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"]).sum())
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Universe", f"{len(market):,}")
    k2.metric("Stocks > $100B", f"{stock_count:,}")
    k3.metric("ETFs", f"{etf_count:,}")
    k4.metric("Rated", f"{rated_count:,}")
    k5.metric("Snapshot populated", f"{int(valid_prices.sum()):,}")
    k6.metric("Showing", f"{len(filtered):,}")

    # Manual refresh with visible instrument count and percentage.
    rc1, rc2, rc3 = st.columns([1.8, 1.7, 3.5])
    with rc1:
        refresh_scope = st.segmented_control(
            "Manual refresh scope",
            ["Filtered / shown results", "Entire tracked universe"],
            default="Filtered / shown results",
            help=(
                "The >$100B stock universe is substantially smaller than prior versions. The scheduled 6 PM ET job always refreshes the complete Nasdaq >$100B stock universe plus the 213 ETFs."
            ),
        )
    with rc2:
        target_count = len(filtered) if refresh_scope == "Filtered / shown results" else len(market)
        refresh_now = st.button(
            f"⚡ Refresh {target_count:,}",
            type="primary",
            use_container_width=True,
            disabled=target_count == 0,
        )
    with rc3:
        st.caption(
            f"Manual scope: {target_count:,} instrument(s). Prices refresh in batches, Nasdaq analyst ratings are rechecked, "
            "then the complete snapshot is saved locally and durably to GitHub when MARKETSCOPE_GITHUB_TOKEN is configured."
        )

    if refresh_now:
        targets = (filtered if refresh_scope == "Filtered / shown results" else market)["Symbol"].astype(str).tolist()
        total = len(targets)
        target_rows = market[market["Symbol"].isin(targets)]
        target_stocks = int(target_rows["Type"].eq("Stock").sum())
        target_etfs = int(target_rows["Type"].eq("ETF").sum())
        progress = st.progress(0.0, text=f"Starting refresh: 0 / {total:,} (0.0%)")
        counter = st.empty()

        # Stage 0: seed from the durable GitHub snapshot before contacting Yahoo.
        # This is the v5.4 safeguard that keeps returns visible even if Render's IP
        # is temporarily throttled by the free market-data source.
        refreshed = market_base.copy()
        try:
            remote_seed = _normalize_snapshot(load_remote_snapshot())
        except Exception:
            remote_seed = pd.DataFrame()
        if _populated_price_count(remote_seed) > 0:
            refreshed = merge_prefer_incoming_snapshot(refreshed, remote_seed)

        # Stage 1: refresh Nasdaq analyst ratings first so stock signal classification
        # uses the newest available consensus during this same manual refresh.
        progress.progress(0.04, text=f"Refreshing Nasdaq analyst ratings for {total:,} instruments...")
        refreshed = refresh_ratings(refreshed, targets)

        # Stage 1B: Yahoo analyst price-target ranges for stocks only.
        progress.progress(0.08, text=f"Refreshing analyst price targets for stock cards...")
        refreshed = refresh_price_targets(refreshed, targets)

        # Stage 2: historical adjusted data supplies returns and technical buy signals.
        history_success = 0
        processed = 0
        history_batch_size = 40
        stamp = format_et()
        for start in range(0, total, history_batch_size):
            batch = targets[start:start + history_batch_size]
            try:
                histories = provider.download_daily_history_since(batch, start=ANNUAL_HISTORY_START, chunk_size=20)
            except Exception:
                histories = {}
            refreshed, added = apply_history_refresh(refreshed, histories, batch, stamp)
            history_success += added
            processed += len(batch)
            pct = processed / total if total else 1.0
            progress.progress(
                min(0.74, 0.08 + pct * 0.66),
                text=f"Historical returns: {processed:,} / {total:,} processed ({pct*100:.1f}%) • {history_success:,} populated",
            )
            counter.caption(
                f"Stocks: {target_stocks:,} • ETFs: {target_etfs:,} • historical rows populated: {history_success:,} / {processed:,}"
            )

        # Stage 3: intraday/latest prices.  If historical retrieval is throttled,
        # apply_live_overlay still writes a returned live Price even with no old price.
        prices: Dict[str, float] = {}
        live_processed = 0
        live_batch_size = 50
        for start in range(0, total, live_batch_size):
            batch = targets[start:start + live_batch_size]
            try:
                got = provider.download_live_prices(batch)
            except Exception:
                got = {}
            prices.update(got)
            live_processed += len(batch)
            pct = live_processed / total if total else 1.0
            progress.progress(
                min(0.94, 0.74 + pct * 0.20),
                text=f"Latest prices: {live_processed:,} / {total:,} processed ({pct*100:.1f}%) • {len(prices):,} returned",
            )
            counter.caption(
                f"Historical rows: {history_success:,} • latest prices returned: {len(prices):,} • total target: {total:,}"
            )

        refreshed = apply_live_overlay(refreshed, prices)
        progress.progress(0.97, text="Returns, signals, prices, ratings and price targets refreshed • saving the complete persistent snapshot...")

        fresh_symbols = set(prices)
        fresh_symbols.update(
            symbol for symbol in targets
            if symbol in set(
                refreshed.loc[
                    refreshed["Symbol"].isin(targets)
                    & refreshed["Snapshot Updated ET"].astype(str).eq(stamp),
                    "Symbol",
                ].astype(str).tolist()
            )
        )
        freshly_updated = len(fresh_symbols)
        target_available = refreshed[
            refreshed["Symbol"].isin(targets)
            & pd.to_numeric(refreshed["Price"], errors="coerce").notna()
        ]
        rows_available = int(len(target_available))

        # Only label/persist a manual refresh as fresh when Yahoo actually returned
        # historical rows or latest prices. If it did not, keep the durable snapshot
        # visible without pretending it was newly refreshed.
        if history_success or prices:
            refreshed.loc[
                refreshed["Symbol"].isin(targets)
                & pd.to_numeric(refreshed["Price"], errors="coerce").notna(),
                "Snapshot Updated ET",
            ] = stamp
            ok, msg = persist_snapshot(
                refreshed, SNAPSHOT_FILE, "Manual app refresh", max(history_success, freshly_updated)
            )
            st.session_state.persistence_message = (
                ok,
                _safe_message(msg, "Server snapshot saved; durable GitHub save status unavailable."),
            )
            st.session_state.last_refresh_summary = (
                f"Manual refresh completed at {format_et(now_et())} • {total:,}/{total:,} instruments processed (100%) • "
                f"{history_success:,} historical return rows refreshed • {len(prices):,} latest prices returned • "
                f"{rows_available:,}/{total:,} requested rows now have saved return data."
            )
        elif rows_available:
            # Yahoo returned nothing, but the durable snapshot already contains data.
            # Do not overwrite its true refresh timestamp.
            st.session_state.last_refresh_summary = (
                f"The live source returned no new rows at {format_et(now_et())}, so MarketScope preserved the last durable snapshot. "
                f"{rows_available:,}/{total:,} requested instruments still have saved price/return data available."
            )
        else:
            st.session_state.last_refresh_summary = (
                f"Refresh request completed at {format_et(now_et())}, but no usable historical or price data was returned for "
                f"these {total:,} instruments. The daily GitHub refresh remains the authoritative recovery path."
            )

        st.session_state.live_prices = {}
        st.session_state.manual_refreshed_at = now_et()
        load_snapshot.clear()
        load_snapshot_metadata.clear()
        progress.progress(
            1.0,
            text=(
                f"Refresh complete: {total:,} / {total:,} processed (100.0%) • "
                f"{history_success:,} return rows refreshed • {rows_available:,} rows available"
            ),
        )
        counter.caption(
            f"Completed at {format_et(st.session_state.manual_refreshed_at)} • historical rows refreshed {history_success:,} • "
            f"latest prices {len(prices):,} • saved rows available {rows_available:,}"
        )
        st.rerun()

    # One-time update timestamps above both display views (not repeated as columns).
    snapshot_updated_display = _valid_status_text(metadata.get("updated_at_display_et"))
    if not snapshot_updated_display and "Snapshot Updated ET" in market.columns:
        snapshot_updated_display = _latest_display_timestamp(market["Snapshot Updated ET"].tolist())
    rating_updated_display = (
        _latest_display_timestamp(market["Rating Updated ET"].tolist())
        if "Rating Updated ET" in market.columns
        else ""
    )
    if not snapshot_updated_display:
        snapshot_updated_display = "Pending first successful refresh"
    if not rating_updated_display:
        rating_updated_display = "Pending first successful rating refresh"
    st.markdown(
        f"""<div class="update-strip">
            <span><strong>Rating update:</strong> {rating_updated_display}</span>
            <span><strong>Snapshot update:</strong> {snapshot_updated_display}</span>
            <span><strong>Timezone:</strong> U.S. Eastern</span>
        </div>""",
        unsafe_allow_html=True,
    )

def _portfolio_common_calendar_years(market_df: pd.DataFrame, symbols: list[str], max_years: int | None = None) -> list[str]:
    """Return completed calendar years for which every selected instrument has a valid saved return.

    Years are returned newest-to-oldest and are capped to MarketScope's dynamically growing annual-history window. This lets a
    requested 1Y-{ANNUAL_HISTORY_YEARS}Y horizon remain selectable even when one instrument listed later: the effective
    simulation begins with the earliest year in the common-data window instead of failing.
    """
    if max_years is None:
        max_years = ANNUAL_HISTORY_YEARS
    max_years = max(1, min(ANNUAL_HISTORY_YEARS, int(max_years)))
    if not symbols:
        return list(YEAR_RETURN_COLS[:max_years])
    lookup = market_df.copy()
    lookup["Symbol"] = lookup["Symbol"].astype(str).str.upper()
    lookup = lookup.drop_duplicates("Symbol", keep="first").set_index("Symbol", drop=False)
    clean = [str(sym).upper() for sym in symbols if str(sym).strip()]
    if not clean or any(sym not in lookup.index for sym in clean):
        return []
    common: list[str] = []
    for year in list(YEAR_RETURN_COLS[:max_years]):
        valid = True
        for sym in clean:
            row = lookup.loc[sym]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            raw = pd.to_numeric(pd.Series([row.get(year)]), errors="coerce").iloc[0]
            if pd.isna(raw) or not np.isfinite(raw):
                valid = False
                break
        if valid:
            common.append(str(year))
    return common


def _effective_portfolio_years(market_df: pd.DataFrame, symbols: list[str], period_choice: str) -> list[str]:
    """Newest-to-oldest common years used for the requested portfolio horizon."""
    try:
        requested = max(1, min(ANNUAL_HISTORY_YEARS, int(str(period_choice).replace("Y", ""))))
    except Exception:
        return []
    return _portfolio_common_calendar_years(market_df, symbols, ANNUAL_HISTORY_YEARS)[:requested]


def _portfolio_annual_reset_dataframe(
    market_df: pd.DataFrame,
    symbols: list[str],
    weights: dict[str, float],
    total_investment: float,
    annual_withdrawal: float = 0.0,
    calendar_years: list[str] | None = None,
) -> pd.DataFrame:
    """Independent one-year reset test with the current annual withdrawal applied.

    Every displayed calendar year begins with the exact same initial investment
    and target allocation. The year's saved annual returns are applied, then the
    requested annual withdrawal is taken. Nothing carries into the next row.

    A year is included only when every selected instrument has a finite annual
    return. If ``calendar_years`` is supplied, the table is restricted to that
    current Portfolio Simulator completed-year window.
    """
    base_columns = [
        "Year",
        "Starting Balance ($)",
        "Annual Return (%)",
        "Gain / Loss ($)",
        "Before Withdrawal ($)",
        "Withdrawal ($)",
        "Remaining After Withdrawal ($)",
        "Withdrawal Status",
    ]
    clean = list(dict.fromkeys(str(sym).upper().strip() for sym in symbols if str(sym).strip()))
    try:
        principal = float(total_investment)
        requested_withdrawal = max(0.0, float(annual_withdrawal))
    except Exception:
        return pd.DataFrame(columns=base_columns)

    if not clean or principal <= 0 or not np.isfinite(principal):
        return pd.DataFrame(columns=base_columns)

    lookup = market_df.copy()
    lookup["Symbol"] = lookup["Symbol"].astype(str).str.upper().str.strip()
    lookup = lookup.drop_duplicates("Symbol", keep="last").set_index("Symbol", drop=False)
    if any(sym not in lookup.index for sym in clean):
        return pd.DataFrame(columns=base_columns)

    common_years = _portfolio_common_calendar_years(
        market_df,
        clean,
        ANNUAL_HISTORY_YEARS,
    )
    if calendar_years is not None:
        requested_years = [str(year) for year in calendar_years]
        common_set = set(common_years)
        common_years = [year for year in requested_years if year in common_set]
    if not common_years:
        return pd.DataFrame(columns=base_columns)

    weight_values = {sym: float(weights.get(sym, 0.0) or 0.0) for sym in clean}
    weight_total = sum(weight_values.values())
    if weight_total <= 0 or abs(weight_total - 100.0) > 0.05:
        return pd.DataFrame(columns=base_columns)

    rows: list[dict] = []
    for year in sorted(common_years, key=lambda value: int(value)):
        row_out: dict = {
            "Year": int(year),
            "Starting Balance ($)": principal,
        }
        weighted_return = 0.0
        year_valid = True

        for sym in clean:
            source_row = lookup.loc[sym]
            if isinstance(source_row, pd.DataFrame):
                source_row = source_row.iloc[0]
            raw = pd.to_numeric(
                pd.Series([source_row.get(str(year))]),
                errors="coerce",
            ).iloc[0]
            if pd.isna(raw) or not np.isfinite(raw):
                year_valid = False
                break
            pct = float(raw)
            row_out[f"{sym} Return (%)"] = pct
            weighted_return += (weight_values[sym] / 100.0) * pct

        if not year_valid:
            continue

        gain_loss = principal * weighted_return / 100.0
        before_withdrawal = principal + gain_loss
        available = max(0.0, before_withdrawal)
        actual_withdrawal = min(requested_withdrawal, available)
        remaining = max(0.0, before_withdrawal - actual_withdrawal)

        if requested_withdrawal <= 0:
            withdrawal_status = "No withdrawal"
        elif actual_withdrawal >= requested_withdrawal - 0.005:
            withdrawal_status = "Funded"
        elif actual_withdrawal > 0:
            withdrawal_status = "Partial"
        else:
            withdrawal_status = "Not funded"

        row_out.update({
            "Annual Return (%)": weighted_return,
            "Gain / Loss ($)": gain_loss,
            "Before Withdrawal ($)": before_withdrawal,
            "Withdrawal ($)": actual_withdrawal,
            "Remaining After Withdrawal ($)": remaining,
            "Withdrawal Status": withdrawal_status,
        })
        rows.append(row_out)

    if not rows:
        return pd.DataFrame(columns=base_columns)

    ordered = ["Year", "Starting Balance ($)"]
    ordered.extend(f"{sym} Return (%)" for sym in clean)
    ordered.extend([
        "Annual Return (%)",
        "Gain / Loss ($)",
        "Before Withdrawal ($)",
        "Withdrawal ($)",
        "Remaining After Withdrawal ($)",
        "Withdrawal Status",
    ])
    return pd.DataFrame(rows)[ordered]


def _portfolio_horizon_projection(row: pd.Series, principal: float, period_choice: str, include_ytd: bool, calendar_years: list[str] | None = None) -> dict | None:
    """Calculate one instrument's simulated result for a shared portfolio horizon."""
    try:
        principal = float(principal)
    except Exception:
        return None
    if not np.isfinite(principal) or principal < 0:
        return None
    period_choice = str(period_choice or "YTD")
    if period_choice == "YTD":
        pct = pd.to_numeric(pd.Series([row.get("YTD")]), errors="coerce").iloc[0]
        if pd.isna(pct) or not np.isfinite(pct):
            return {"unavailable": True, "period": "YTD"}
        factor = 1.0 + float(pct) / 100.0
        if factor < 0:
            return {"unavailable": True, "period": "YTD"}
        ending = principal * factor
        return {"ending_value": ending, "profit": ending - principal, "return_pct": float(pct), "period": "YTD"}

    try:
        years_requested = int(period_choice.replace("Y", ""))
    except Exception:
        return None
    years_requested = max(1, min(ANNUAL_HISTORY_YEARS, years_requested))
    requested_year_labels = (list(calendar_years) if calendar_years is not None else list(YEAR_RETURN_COLS[:years_requested]))[:years_requested]
    selected: list[tuple[str, float]] = []
    for year in requested_year_labels:
        pct = pd.to_numeric(pd.Series([row.get(year)]), errors="coerce").iloc[0]
        if pd.isna(pct) or not np.isfinite(pct):
            continue
        selected.append((str(year), float(pct)))
    if not selected:
        return {"unavailable": True, "period": period_choice, "available_years": 0}
    value = principal
    for _, annual_pct in reversed(selected):
        factor = 1.0 + annual_pct / 100.0
        if factor < 0:
            return {"unavailable": True, "period": period_choice}
        value *= factor
    ytd_applied = False
    if include_ytd:
        ytd = pd.to_numeric(pd.Series([row.get("YTD")]), errors="coerce").iloc[0]
        if pd.notna(ytd) and np.isfinite(ytd):
            factor = 1.0 + float(ytd) / 100.0
            if factor >= 0:
                value *= factor
                ytd_applied = True
    total_pct = ((value / principal) - 1.0) * 100.0 if principal > 0 else 0.0
    return {
        "ending_value": value,
        "profit": value - principal,
        "return_pct": total_pct,
        "period": period_choice,
        "effective_years": len(selected),
        "start_year": selected[-1][0] if selected else None,
        "end_year": selected[0][0] if selected else None,
        "ytd_applied": ytd_applied,
    }


def _market_table_annual_withdrawal_projection(
    row: pd.Series,
    principal: float,
    period_choice: str,
    annual_withdrawal: float,
    include_ytd: bool = False,
) -> dict:
    """Single-instrument withdrawal simulation sourced directly from Market Table annual columns.

    For the maximum-history selection, every completed annual return from the configured baseline through the latest completed year is
    processed oldest-to-newest when present. The withdrawal occurs after each
    completed year's listed return. Current YTD, when enabled, is applied last
    without another annual withdrawal.
    """
    try:
        principal = float(principal)
        withdrawal = max(0.0, float(annual_withdrawal))
    except Exception:
        return {"unavailable": True}
    if principal <= 0 or str(period_choice or "YTD") == "YTD":
        return {"unavailable": True}
    try:
        requested = max(1, min(ANNUAL_HISTORY_YEARS, int(str(period_choice).replace("Y", ""))))
    except Exception:
        return {"unavailable": True}

    annual: list[tuple[str, float]] = []
    for year in YEAR_RETURN_COLS[:requested]:
        value = pd.to_numeric(pd.Series([row.get(year)]), errors="coerce").iloc[0]
        if pd.isna(value) or not np.isfinite(value):
            return {
                "unavailable": True,
                "reason": f"Missing Market Table annual return for {year}.",
                "years_used": len(annual),
            }
        annual.append((str(year), float(value)))

    balance = principal
    total_withdrawn = 0.0
    funded = 0
    schedule: list[dict] = []
    for year, pct in reversed(annual):
        start = balance
        factor = 1.0 + pct / 100.0
        if factor < 0:
            return {"unavailable": True, "reason": f"Invalid Market Table annual return for {year}."}
        before = start * factor
        actual = min(withdrawal, before)
        balance = max(0.0, before - actual)
        total_withdrawn += actual
        funded += 1 if actual >= withdrawal - 0.005 else 0
        schedule.append({
            "year": year,
            "starting_balance": start,
            "annual_return_pct": pct,
            "balance_before_withdrawal": before,
            "withdrawal": actual,
            "ending_balance": balance,
            "return_method": "Market Table completed calendar-year return",
        })
        if balance <= 0:
            break

    if include_ytd and balance > 0:
        ytd = pd.to_numeric(pd.Series([row.get("YTD")]), errors="coerce").iloc[0]
        if pd.notna(ytd) and np.isfinite(ytd):
            factor = 1.0 + float(ytd) / 100.0
            if factor >= 0:
                balance *= factor

    return {
        "unavailable": False,
        "ending_balance": balance,
        "total_withdrawn": total_withdrawn,
        "net_value_including_withdrawals": balance + total_withdrawn,
        "net_profit_including_withdrawals": balance + total_withdrawn - principal,
        "years_used": len(annual),
        "withdrawals_funded": funded,
        "schedule": schedule,
        "return_method": "Market Table annual returns (Yahoo/yfinance adjusted history)",
    }


def _portfolio_annual_withdrawal_schedule(
    market_df: pd.DataFrame,
    symbols: list[str],
    weights: dict[str, float],
    total_invested: float,
    period_choice: str,
    include_ytd: bool,
    annual_withdrawal: float,
    calendar_years: list[str] | None = None,
    rebalance_after_withdrawal: bool = False,
) -> dict:
    """Run a portfolio-level annual withdrawal path using actual saved instrument returns.

    Completed calendar years are processed oldest to newest. Each holding first receives its own
    annual return and the requested withdrawal is then taken proportionally from the post-return
    portfolio. When ``rebalance_after_withdrawal`` is true, the remaining balance is redistributed
    back to the user's target weights after each completed-year withdrawal. When false, holdings are
    left at their naturally drifted weights. Current YTD, when requested, is a final partial-period
    row and never triggers a withdrawal or rebalance.
    """
    try:
        principal = float(total_invested)
        withdrawal_requested = max(0.0, float(annual_withdrawal))
    except Exception:
        return {"unavailable": True, "reason": "Invalid portfolio amount or withdrawal amount."}
    if principal <= 0 or not symbols:
        return {"unavailable": True, "reason": "A positive portfolio amount and at least one instrument are required."}
    period_choice = str(period_choice or "YTD")
    if period_choice == "YTD":
        return {"unavailable": True, "reason": f"Annual withdrawals require a completed-year horizon from 1Y through {ANNUAL_HISTORY_YEARS}Y."}
    try:
        years_requested = max(1, min(ANNUAL_HISTORY_YEARS, int(period_choice.replace("Y", ""))))
    except Exception:
        return {"unavailable": True, "reason": "Invalid portfolio period."}

    lookup = market_df.copy()
    lookup["Symbol"] = lookup["Symbol"].astype(str).str.upper()
    lookup = lookup.drop_duplicates("Symbol", keep="first").set_index("Symbol", drop=False)
    selected_years = (list(calendar_years) if calendar_years is not None else list(YEAR_RETURN_COLS[:years_requested]))[:years_requested]
    if not selected_years:
        return {"unavailable": True, "reason": "No completed calendar year is shared by every selected instrument."}

    balances: dict[str, float] = {}
    for sym in symbols:
        sym = str(sym).upper()
        if sym not in lookup.index:
            return {"unavailable": True, "reason": f"{sym} is not available in the current market snapshot."}
        weight = float(weights.get(sym, 0.0) or 0.0)
        balances[sym] = principal * weight / 100.0

    schedule: list[dict] = []
    total_withdrawn = 0.0
    depleted_year = None
    for year in reversed(selected_years):
        starting_balance = sum(balances.values())
        if starting_balance <= 0:
            depleted_year = depleted_year or str(year)
            break
        for sym in list(balances):
            raw = pd.to_numeric(pd.Series([lookup.loc[sym].get(str(year))]), errors="coerce").iloc[0]
            if pd.isna(raw) or not np.isfinite(raw):
                return {"unavailable": True, "reason": f"{sym} does not have a saved return for {year}."}
            factor = 1.0 + float(raw) / 100.0
            if factor < 0:
                return {"unavailable": True, "reason": f"{sym} has an invalid return below -100% for {year}."}
            balances[sym] *= factor
        before_withdrawal = sum(balances.values())
        gain_loss = before_withdrawal - starting_balance
        portfolio_return = (gain_loss / starting_balance * 100.0) if starting_balance > 0 else 0.0
        actual_withdrawal = min(withdrawal_requested, before_withdrawal)
        ending_balance = max(0.0, before_withdrawal - actual_withdrawal)
        if before_withdrawal > 0 and actual_withdrawal > 0:
            # First fund the withdrawal proportionally from the post-return holdings.
            scale = ending_balance / before_withdrawal
            for sym in balances:
                balances[sym] *= scale
        if rebalance_after_withdrawal and ending_balance > 0:
            # Reset the remaining portfolio to the original target allocation for the next year.
            weight_total = sum(max(0.0, float(weights.get(str(sym).upper(), 0.0) or 0.0)) for sym in balances)
            if weight_total <= 0:
                return {"unavailable": True, "reason": "Target portfolio weights are invalid for annual rebalancing."}
            for sym in balances:
                target_weight = max(0.0, float(weights.get(str(sym).upper(), 0.0) or 0.0)) / weight_total
                balances[sym] = ending_balance * target_weight
        total_withdrawn += actual_withdrawal
        schedule.append({
            "year": str(year),
            "starting_balance": starting_balance,
            "portfolio_return_pct": portfolio_return,
            "gain_loss": gain_loss,
            "balance_before_withdrawal": before_withdrawal,
            "withdrawal": actual_withdrawal,
            "ending_balance": ending_balance,
            "return_method": "Market Table completed calendar-year return (Yahoo/yfinance adjusted history)",
        })
        if ending_balance <= 0:
            depleted_year = str(year)
            break

    if include_ytd and sum(balances.values()) > 0:
        starting_balance = sum(balances.values())
        for sym in list(balances):
            raw = pd.to_numeric(pd.Series([lookup.loc[sym].get("YTD")]), errors="coerce").iloc[0]
            if pd.isna(raw) or not np.isfinite(raw):
                return {"unavailable": True, "reason": f"{sym} does not have a saved YTD return."}
            factor = 1.0 + float(raw) / 100.0
            if factor < 0:
                return {"unavailable": True, "reason": f"{sym} has an invalid YTD return below -100%."}
            balances[sym] *= factor
        ending_balance = sum(balances.values())
        gain_loss = ending_balance - starting_balance
        schedule.append({
            "year": "YTD (partial)",
            "starting_balance": starting_balance,
            "portfolio_return_pct": (gain_loss / starting_balance * 100.0) if starting_balance > 0 else 0.0,
            "gain_loss": gain_loss,
            "balance_before_withdrawal": ending_balance,
            "withdrawal": 0.0,
            "ending_balance": ending_balance,
        })

    remaining = sum(balances.values())
    completed_withdrawal_rows = [
        row for row in schedule
        if str(row.get("year") or "").strip().lower() != "ytd (partial)"
    ]
    withdrawals_funded = sum(
        1
        for row in completed_withdrawal_rows
        if float(row.get("withdrawal") or 0.0) >= withdrawal_requested - 0.005
    )
    positive_years = sum(
        1
        for row in completed_withdrawal_rows
        if float(row.get("portfolio_return_pct") or 0.0) > 0.0
    )
    return {
        "unavailable": False,
        "annual_withdrawal_requested": withdrawal_requested,
        "withdrawals_targeted": len(selected_years),
        "withdrawals_funded": withdrawals_funded,
        "positive_years": int(positive_years),
        "years_modeled": int(len(completed_withdrawal_rows)),
        "total_withdrawn": total_withdrawn,
        "ending_balance": remaining,
        "depleted_year": depleted_year,
        "schedule": schedule,
        "net_value_including_withdrawals": remaining + total_withdrawn,
        "net_profit_including_withdrawals": remaining + total_withdrawn - principal,
        "strategy": "Rebalanced annually" if rebalance_after_withdrawal else "Not rebalanced",
        "rebalanced_annually": bool(rebalance_after_withdrawal),
    }


def _portfolio_start_year_paths_dataframe(
    market_df: pd.DataFrame,
    symbols: list[str],
    weights: dict[str, float],
    total_invested: float,
    annual_withdrawal: float,
    calendar_years: list[str],
    rebalance_after_withdrawal: bool,
) -> pd.DataFrame:
    """Build rolling withdrawal paths for every eligible investment start year.

    Each cohort begins with the same original investment in its own Start Year.
    From that point forward, the remaining balance is carried into every later
    completed year. The portfolio is never reset between subsequent years.

    One strategy is calculated per call so the Rebalanced and Not-Rebalanced
    Start-Year tabs remain completely separated in the UI.

    Profit ($) and Profit (%) are cumulative economic profit versus the original
    starting investment and include cash already withdrawn:
        Remaining Balance + Cumulative Withdrawn - Initial Investment
    """
    columns = [
        "Start Year",
        "Year",
        "Year #",
        "Starting Balance ($)",
        "Annual Return (%)",
        "Year Gain / Loss ($)",
        "Before Withdrawal ($)",
        "Withdrawal ($)",
        "Remaining After Withdrawal ($)",
        "Cumulative Withdrawn ($)",
        "Profit ($)",
        "Profit (%)",
        "Withdrawal Status",
    ]

    clean = list(dict.fromkeys(str(sym).upper().strip() for sym in symbols if str(sym).strip()))
    try:
        principal = float(total_invested)
        withdrawal = max(0.0, float(annual_withdrawal))
    except Exception:
        return pd.DataFrame(columns=columns)

    if principal <= 0 or not clean:
        return pd.DataFrame(columns=columns)

    common_years = _portfolio_common_calendar_years(
        market_df,
        clean,
        ANNUAL_HISTORY_YEARS,
    )
    requested = [str(year) for year in (calendar_years or [])]
    common_set = set(common_years)
    requested = [year for year in requested if year in common_set]
    if not requested:
        return pd.DataFrame(columns=columns)

    rows: list[dict] = []

    # requested is newest -> oldest. Each Start Year cohort uses that year and
    # every later year through the newest completed year.
    for start_year in sorted(requested, key=lambda value: int(value)):
        start_index = requested.index(str(start_year))
        cohort_years = requested[: start_index + 1]
        period_choice = f"{len(cohort_years)}Y"

        result = _portfolio_annual_withdrawal_schedule(
            market_df=market_df,
            symbols=clean,
            weights=weights,
            total_invested=principal,
            period_choice=period_choice,
            include_ytd=False,
            annual_withdrawal=withdrawal,
            calendar_years=cohort_years,
            rebalance_after_withdrawal=bool(rebalance_after_withdrawal),
        )
        if result.get("unavailable"):
            continue

        cumulative_withdrawn = 0.0
        for sequence, schedule_row in enumerate(result.get("schedule") or [], start=1):
            year = str(schedule_row.get("year") or "")
            if not year or year.strip().lower() == "ytd (partial)":
                continue

            actual_withdrawal = float(schedule_row.get("withdrawal") or 0.0)
            cumulative_withdrawn += actual_withdrawal
            remaining = float(schedule_row.get("ending_balance") or 0.0)
            economic_value = remaining + cumulative_withdrawn
            cumulative_profit = economic_value - principal
            cumulative_profit_pct = (
                cumulative_profit / principal * 100.0 if principal > 0 else 0.0
            )

            if withdrawal <= 0:
                status = "No withdrawal"
            elif actual_withdrawal >= withdrawal - 0.005:
                status = "Funded"
            elif actual_withdrawal > 0:
                status = "Partial"
            else:
                status = "Not funded"

            rows.append({
                "Start Year": int(start_year),
                "Year": int(year),
                "Year #": int(sequence),
                "Starting Balance ($)": float(schedule_row.get("starting_balance") or 0.0),
                "Annual Return (%)": float(schedule_row.get("portfolio_return_pct") or 0.0),
                "Year Gain / Loss ($)": float(schedule_row.get("gain_loss") or 0.0),
                "Before Withdrawal ($)": float(schedule_row.get("balance_before_withdrawal") or 0.0),
                "Withdrawal ($)": actual_withdrawal,
                "Remaining After Withdrawal ($)": remaining,
                "Cumulative Withdrawn ($)": cumulative_withdrawn,
                "Profit ($)": cumulative_profit,
                "Profit (%)": cumulative_profit_pct,
                "Withdrawal Status": status,
            })

    if not rows:
        return pd.DataFrame(columns=columns)

    return pd.DataFrame(rows)[columns]


def _start_year_depletion_summary(paths_df: pd.DataFrame) -> dict:
    """Summarize every annual cohort plus the earliest depletion event.

    A cohort is depleted when Remaining After Withdrawal reaches effectively $0.
    Each cohort retains its actual first modeled year, first depletion year, and
    last modeled year so the full result can be displayed inside the dashboard card.
    """
    empty = {
        "total_cohorts": 0,
        "depleted_cohorts": 0,
        "first_depletion_year": None,
        "first_depletion_start_year": None,
        "cohort_outcomes": [],
    }
    if paths_df is None or paths_df.empty:
        return empty
    required = {"Start Year", "Year", "Remaining After Withdrawal ($)"}
    if not required.issubset(paths_df.columns):
        return empty

    work = paths_df.copy()
    work["Start Year"] = pd.to_numeric(work["Start Year"], errors="coerce")
    work["Year"] = pd.to_numeric(work["Year"], errors="coerce")
    work["Remaining After Withdrawal ($)"] = pd.to_numeric(
        work["Remaining After Withdrawal ($)"], errors="coerce"
    )
    work = work.dropna(subset=["Start Year", "Year", "Remaining After Withdrawal ($)"])
    if work.empty:
        return empty

    cohort_outcomes: list[dict] = []
    first_events: list[dict] = []
    for start_year, cohort in work.groupby("Start Year", sort=True):
        cohort = cohort.sort_values("Year")
        start_period = int(cohort.iloc[0]["Year"])
        last_year = int(cohort.iloc[-1]["Year"])
        depleted_rows = cohort.loc[cohort["Remaining After Withdrawal ($)"] <= 0.005]
        depletion_year = None
        if not depleted_rows.empty:
            depletion_year = int(depleted_rows.iloc[0]["Year"])
            first_events.append({
                "start_year": int(start_year),
                "depletion_year": depletion_year,
            })
        cohort_outcomes.append({
            "start_year": int(start_year),
            "start_period": start_period,
            "depletion_year": depletion_year,
            "last_year": last_year,
        })

    total_cohorts = len(cohort_outcomes)
    if not first_events:
        return {
            "total_cohorts": total_cohorts,
            "depleted_cohorts": 0,
            "first_depletion_year": None,
            "first_depletion_start_year": None,
            "cohort_outcomes": cohort_outcomes,
        }

    first_event = sorted(
        first_events,
        key=lambda event: (event["depletion_year"], event["start_year"]),
    )[0]
    return {
        "total_cohorts": total_cohorts,
        "depleted_cohorts": len(first_events),
        "first_depletion_year": int(first_event["depletion_year"]),
        "first_depletion_start_year": int(first_event["start_year"]),
        "cohort_outcomes": cohort_outcomes,
    }


def _annual_depletion_card_html(label: str, summary: dict) -> str:
    """Render all annual cohort initiation/depletion outcomes inside one card."""
    year = summary.get("first_depletion_year")
    start_year = summary.get("first_depletion_start_year")
    depleted = int(summary.get("depleted_cohorts") or 0)
    total = int(summary.get("total_cohorts") or 0)
    outcomes = list(summary.get("cohort_outcomes") or [])

    primary = str(year) if year is not None else "Not depleted"
    if year is not None:
        context = f"Earliest affected start cohort: {start_year} • Depleted cohorts: {depleted}/{total}"
    else:
        context = f"All modeled cohorts survived • Depleted cohorts: 0/{total}"

    rows = []
    for outcome in outcomes:
        start_period = escape(str(outcome.get("start_period") or outcome.get("start_year") or "—"))
        depletion_year = outcome.get("depletion_year")
        if depletion_year is not None:
            outcome_class = "depleted"
            outcome_text = f"Depleted <b>{escape(str(depletion_year))}</b>"
        else:
            outcome_class = "survived"
            last_year = escape(str(outcome.get("last_year") or "—"))
            outcome_text = f"Not depleted through <b>{last_year}</b>"
        rows.append(
            f'<div class="monthly-depletion-cohort-row {outcome_class}">'
            f'<span>Initiated <b>{start_period}</b></span>'
            f'<span>{outcome_text}</span>'
            "</div>"
        )

    cohort_html = "".join(rows) or (
        '<div class="monthly-depletion-cohort-empty">No annual start-year cohorts available.</div>'
    )
    return (
        '<div class="monthly-depletion-detail-card annual-depletion-detail-card">'
        f'<span class="monthly-depletion-card-label">{escape(str(label))}</span>'
        f'<b class="monthly-depletion-card-value">{escape(primary)}</b>'
        f'<small class="monthly-depletion-card-context">{escape(context)}</small>'
        '<div class="monthly-depletion-cohort-title">ALL COHORT START AND DEPLETION YEARS</div>'
        f'<div class="monthly-depletion-cohort-grid">{cohort_html}</div>'
        "</div>"
    )


def _portfolio_monthly_withdrawal_schedule(
    market_df: pd.DataFrame,
    symbols: list[str],
    weights: dict[str, float],
    total_invested: float,
    period_choice: str,
    monthly_withdrawal: float,
    calendar_years: list[str] | None = None,
    rebalance_after_withdrawal: bool = False,
    actual_monthly_returns: dict[str, dict[str, float]] | None = None,
) -> dict:
    """Run monthly cash withdrawals using actual adjusted month-to-month returns.

    Each modeled month uses the instrument's genuine adjusted month-end return:
    final adjusted close of the month / final adjusted close of the prior month - 1.
    The engine never derives a monthly rate by dividing or rooting an annual return.
    Rebalanced mode restores the saved target allocation after every month-end
    withdrawal; Not rebalanced leaves the post-market weights to drift naturally.
    """
    try:
        principal = float(total_invested)
        withdrawal_requested = max(0.0, float(monthly_withdrawal))
    except Exception:
        return {"unavailable": True, "reason": "Invalid portfolio amount or monthly withdrawal amount."}
    if principal <= 0 or not symbols:
        return {"unavailable": True, "reason": "A positive portfolio amount and at least one instrument are required."}
    period_choice = str(period_choice or "YTD")
    if period_choice == "YTD":
        return {"unavailable": True, "reason": f"Monthly withdrawals require a completed-year horizon from 1Y through {ANNUAL_HISTORY_YEARS}Y."}
    try:
        years_requested = max(1, min(ANNUAL_HISTORY_YEARS, int(period_choice.replace("Y", ""))))
    except Exception:
        return {"unavailable": True, "reason": "Invalid portfolio period."}

    selected_years = (list(calendar_years) if calendar_years is not None else list(YEAR_RETURN_COLS[:years_requested]))[:years_requested]
    if not selected_years:
        return {"unavailable": True, "reason": "No completed calendar year is shared by every selected instrument."}

    month_labels = _actual_month_labels(tuple(selected_years))
    monthly_data = actual_monthly_returns or {}
    clean_symbols = [str(sym).upper() for sym in symbols]
    for sym in clean_symbols:
        if sym not in monthly_data:
            return {"unavailable": True, "reason": f"Actual monthly returns are unavailable for {sym}."}
        for label in month_labels:
            value = monthly_data[sym].get(label)
            if value is None or not np.isfinite(value):
                return {"unavailable": True, "reason": f"{sym} does not have an actual monthly return for {label}."}
            if float(value) <= -1.0:
                return {"unavailable": True, "reason": f"{sym} has an invalid monthly return at or below -100% for {label}."}

    # Reconcile every modeled year to the annual return currently displayed in
    # Market Table. If a stale monthly file disagrees, fail clearly instead of
    # silently using inconsistent data.
    reconciliation_issues: list[str] = []
    for sym in clean_symbols:
        ok, issues = _monthly_matches_market_table(
            market_df, sym, selected_years, monthly_data.get(sym) or {}, tolerance_pp=0.05
        )
        if not ok:
            reconciliation_issues.extend([f"{sym} {issue}" for issue in issues])
    if reconciliation_issues:
        return {
            "unavailable": True,
            "reason": "Monthly history does not reconcile to Market Table annual returns: " + " | ".join(reconciliation_issues[:6]),
        }

    balances: dict[str, float] = {}
    for sym in clean_symbols:
        weight = float(weights.get(sym, 0.0) or 0.0)
        balances[sym] = principal * weight / 100.0

    schedule: list[dict] = []
    total_withdrawn = 0.0
    depleted_period = None
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    for label in month_labels:
        year, month_text = label.split("-")
        month_number = int(month_text)
        starting_balance = sum(balances.values())
        if starting_balance <= 0:
            depleted_period = depleted_period or label
            break

        for sym in list(balances):
            balances[sym] *= 1.0 + float(monthly_data[sym][label])

        before_withdrawal = sum(balances.values())
        gain_loss = before_withdrawal - starting_balance
        portfolio_return = (gain_loss / starting_balance * 100.0) if starting_balance > 0 else 0.0
        actual_withdrawal = min(withdrawal_requested, before_withdrawal)
        ending_balance = max(0.0, before_withdrawal - actual_withdrawal)

        # Proportional withdrawal preserves each holding's post-return weight.
        if before_withdrawal > 0 and actual_withdrawal > 0:
            scale = ending_balance / before_withdrawal
            for sym in balances:
                balances[sym] *= scale

        if rebalance_after_withdrawal and ending_balance > 0:
            weight_total = sum(max(0.0, float(weights.get(sym, 0.0) or 0.0)) for sym in balances)
            if weight_total <= 0:
                return {"unavailable": True, "reason": "Target portfolio weights are invalid for monthly rebalancing."}
            for sym in balances:
                target_weight = max(0.0, float(weights.get(sym, 0.0) or 0.0)) / weight_total
                balances[sym] = ending_balance * target_weight

        total_withdrawn += actual_withdrawal
        schedule.append({
            "period": label,
            "year": year,
            "month": month_number,
            "month_name": month_names[month_number - 1],
            "starting_balance": starting_balance,
            "portfolio_return_pct": portfolio_return,
            "gain_loss": gain_loss,
            "balance_before_withdrawal": before_withdrawal,
            "withdrawal": actual_withdrawal,
            "ending_balance": ending_balance,
            "return_method": "Actual adjusted month-end return",
        })
        if ending_balance <= 0:
            depleted_period = label
            break

    remaining = sum(balances.values())
    positive_months = sum(
        1 for row in schedule
        if float(row.get("portfolio_return_pct") or 0.0) > 0.0
    )
    return {
        "unavailable": False,
        "monthly_withdrawal_requested": withdrawal_requested,
        "total_withdrawn": total_withdrawn,
        "ending_balance": remaining,
        "depleted_period": depleted_period,
        "schedule": schedule,
        "positive_months": int(positive_months),
        "months_modeled": int(len(schedule)),
        "net_value_including_withdrawals": remaining + total_withdrawn,
        "net_profit_including_withdrawals": remaining + total_withdrawn - principal,
        "strategy": "Rebalanced monthly" if rebalance_after_withdrawal else "Not rebalanced monthly",
        "rebalanced_monthly": bool(rebalance_after_withdrawal),
        "monthly_return_method": "Actual adjusted month-end return from Yahoo/yfinance daily history",
    }


def _portfolio_monthly_reset_dataframe(
    symbols: list[str],
    weights: dict[str, float],
    total_investment: float,
    monthly_withdrawal: float,
    calendar_years: list[str],
    actual_monthly_returns: dict[str, dict[str, float]],
) -> pd.DataFrame:
    """Independent monthly reset test using genuine month-end returns.

    Every row restarts from the same original investment and target weights,
    applies only that historical month's actual instrument returns, and then
    takes one monthly withdrawal. No balance, profit, or holding drift carries
    from one reset row into the next.
    """
    base_columns = [
        "Month",
        "Starting Balance ($)",
        "Monthly Return (%)",
        "Month Gain / Loss ($)",
        "Before Withdrawal ($)",
        "Withdrawal ($)",
        "Remaining After Withdrawal ($)",
        "Withdrawal Status",
    ]
    clean = list(dict.fromkeys(str(sym).upper().strip() for sym in symbols if str(sym).strip()))
    try:
        principal = float(total_investment)
        requested_withdrawal = max(0.0, float(monthly_withdrawal))
    except Exception:
        return pd.DataFrame(columns=base_columns)
    if principal <= 0 or not np.isfinite(principal) or not clean:
        return pd.DataFrame(columns=base_columns)

    weight_values = {sym: max(0.0, float(weights.get(sym, 0.0) or 0.0)) for sym in clean}
    weight_total = sum(weight_values.values())
    if weight_total <= 0 or abs(weight_total - 100.0) > 0.05:
        return pd.DataFrame(columns=base_columns)

    month_labels = _actual_month_labels(tuple(str(year) for year in calendar_years))
    monthly_data = actual_monthly_returns or {}
    rows: list[dict] = []
    for label in month_labels:
        row_out: dict = {"Month": label, "Starting Balance ($)": principal}
        before_withdrawal = 0.0
        valid = True
        for sym in clean:
            value = (monthly_data.get(sym) or {}).get(label)
            if value is None or not np.isfinite(value) or float(value) <= -1.0:
                valid = False
                break
            pct = float(value) * 100.0
            row_out[f"{sym} Return (%)"] = pct
            allocated = principal * weight_values[sym] / weight_total
            before_withdrawal += allocated * (1.0 + float(value))
        if not valid:
            continue

        gain_loss = before_withdrawal - principal
        portfolio_return = gain_loss / principal * 100.0
        actual_withdrawal = min(requested_withdrawal, max(0.0, before_withdrawal))
        remaining = max(0.0, before_withdrawal - actual_withdrawal)
        if requested_withdrawal <= 0:
            status = "No withdrawal"
        elif actual_withdrawal >= requested_withdrawal - 0.005:
            status = "Funded"
        elif actual_withdrawal > 0:
            status = "Partial"
        else:
            status = "Not funded"
        row_out.update({
            "Monthly Return (%)": portfolio_return,
            "Month Gain / Loss ($)": gain_loss,
            "Before Withdrawal ($)": before_withdrawal,
            "Withdrawal ($)": actual_withdrawal,
            "Remaining After Withdrawal ($)": remaining,
            "Withdrawal Status": status,
        })
        rows.append(row_out)

    if not rows:
        return pd.DataFrame(columns=base_columns)
    ordered = ["Month", "Starting Balance ($)"]
    ordered.extend(f"{sym} Return (%)" for sym in clean)
    ordered.extend(base_columns[2:])
    return pd.DataFrame(rows)[ordered]


def _portfolio_monthly_start_year_paths_dataframe(
    market_df: pd.DataFrame,
    symbols: list[str],
    weights: dict[str, float],
    total_invested: float,
    monthly_withdrawal: float,
    calendar_years: list[str],
    rebalance_after_withdrawal: bool,
    actual_monthly_returns: dict[str, dict[str, float]],
) -> pd.DataFrame:
    """Build continuous monthly paths for every eligible investment start year.

    Each cohort begins with the same original investment in January of its Start
    Year. Actual monthly returns and one cash withdrawal are applied every month.
    Remaining After Withdrawal carries into the next month and across calendar
    year boundaries; no annual reset occurs.
    """
    columns = [
        "Start Year",
        "Month",
        "Month #",
        "Year",
        "Starting Balance ($)",
        "Monthly Return (%)",
        "Month Gain / Loss ($)",
        "Before Withdrawal ($)",
        "Withdrawal ($)",
        "Remaining After Withdrawal ($)",
        "Cumulative Withdrawn ($)",
        "Profit ($)",
        "Profit (%)",
        "Withdrawal Status",
    ]
    clean = list(dict.fromkeys(str(sym).upper().strip() for sym in symbols if str(sym).strip()))
    try:
        principal = float(total_invested)
        withdrawal = max(0.0, float(monthly_withdrawal))
    except Exception:
        return pd.DataFrame(columns=columns)
    if principal <= 0 or not clean:
        return pd.DataFrame(columns=columns)

    common_years = _portfolio_common_calendar_years(market_df, clean, ANNUAL_HISTORY_YEARS)
    common_set = set(common_years)
    requested = [str(year) for year in (calendar_years or []) if str(year) in common_set]
    if not requested:
        return pd.DataFrame(columns=columns)

    rows: list[dict] = []
    for start_year in sorted(requested, key=lambda value: int(value)):
        start_index = requested.index(str(start_year))
        cohort_years = requested[: start_index + 1]
        result = _portfolio_monthly_withdrawal_schedule(
            market_df=market_df,
            symbols=clean,
            weights=weights,
            total_invested=principal,
            period_choice=f"{len(cohort_years)}Y",
            monthly_withdrawal=withdrawal,
            calendar_years=cohort_years,
            rebalance_after_withdrawal=bool(rebalance_after_withdrawal),
            actual_monthly_returns=actual_monthly_returns,
        )
        if result.get("unavailable"):
            continue

        cumulative_withdrawn = 0.0
        for sequence, schedule_row in enumerate(result.get("schedule") or [], start=1):
            period = str(schedule_row.get("period") or "")
            if not period:
                continue
            actual_withdrawal = float(schedule_row.get("withdrawal") or 0.0)
            cumulative_withdrawn += actual_withdrawal
            remaining = float(schedule_row.get("ending_balance") or 0.0)
            cumulative_profit = remaining + cumulative_withdrawn - principal
            cumulative_profit_pct = cumulative_profit / principal * 100.0 if principal > 0 else 0.0
            if withdrawal <= 0:
                status = "No withdrawal"
            elif actual_withdrawal >= withdrawal - 0.005:
                status = "Funded"
            elif actual_withdrawal > 0:
                status = "Partial"
            else:
                status = "Not funded"
            rows.append({
                "Start Year": int(start_year),
                "Month": period,
                "Month #": int(sequence),
                "Year": int(schedule_row.get("year") or str(period)[:4]),
                "Starting Balance ($)": float(schedule_row.get("starting_balance") or 0.0),
                "Monthly Return (%)": float(schedule_row.get("portfolio_return_pct") or 0.0),
                "Month Gain / Loss ($)": float(schedule_row.get("gain_loss") or 0.0),
                "Before Withdrawal ($)": float(schedule_row.get("balance_before_withdrawal") or 0.0),
                "Withdrawal ($)": actual_withdrawal,
                "Remaining After Withdrawal ($)": remaining,
                "Cumulative Withdrawn ($)": cumulative_withdrawn,
                "Profit ($)": cumulative_profit,
                "Profit (%)": cumulative_profit_pct,
                "Withdrawal Status": status,
            })

    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)[columns]


def _monthly_start_year_depletion_summary(paths_df: pd.DataFrame) -> dict:
    """Return every cohort's initiation/depletion month plus the earliest event."""
    empty = {
        "total_cohorts": 0,
        "depleted_cohorts": 0,
        "first_depletion_period": None,
        "first_depletion_start_year": None,
        "cohort_outcomes": [],
    }
    if paths_df is None or paths_df.empty:
        return empty
    required = {"Start Year", "Month", "Remaining After Withdrawal ($)"}
    if not required.issubset(paths_df.columns):
        return empty

    work = paths_df.copy()
    work["Start Year"] = pd.to_numeric(work["Start Year"], errors="coerce")
    work["_month_order"] = pd.to_datetime(work["Month"], format="%Y-%m", errors="coerce")
    work["Remaining After Withdrawal ($)"] = pd.to_numeric(
        work["Remaining After Withdrawal ($)"], errors="coerce"
    )
    work = work.dropna(subset=["Start Year", "_month_order", "Remaining After Withdrawal ($)"])
    if work.empty:
        return empty

    cohort_outcomes: list[dict] = []
    first_events: list[dict] = []
    for start_year, cohort in work.groupby("Start Year", sort=True):
        cohort = cohort.sort_values("_month_order")
        start_period = str(cohort.iloc[0]["Month"])
        last_period = str(cohort.iloc[-1]["Month"])
        depleted_rows = cohort.loc[cohort["Remaining After Withdrawal ($)"] <= 0.005]
        depletion_period = None
        if not depleted_rows.empty:
            depletion_period = str(depleted_rows.iloc[0]["Month"])
            first_events.append({
                "start_year": int(start_year),
                "depletion_period": depletion_period,
                "_month_order": depleted_rows.iloc[0]["_month_order"],
            })
        cohort_outcomes.append({
            "start_year": int(start_year),
            "start_period": start_period,
            "depletion_period": depletion_period,
            "last_period": last_period,
        })

    total_cohorts = len(cohort_outcomes)
    if not first_events:
        return {
            "total_cohorts": total_cohorts,
            "depleted_cohorts": 0,
            "first_depletion_period": None,
            "first_depletion_start_year": None,
            "cohort_outcomes": cohort_outcomes,
        }
    first_event = sorted(
        first_events,
        key=lambda event: (event["_month_order"], event["start_year"]),
    )[0]
    return {
        "total_cohorts": total_cohorts,
        "depleted_cohorts": len(first_events),
        "first_depletion_period": str(first_event["depletion_period"]),
        "first_depletion_start_year": int(first_event["start_year"]),
        "cohort_outcomes": cohort_outcomes,
    }


def _monthly_depletion_card_html(label: str, summary: dict) -> str:
    """Render all monthly cohort initiation/depletion outcomes inside one card."""
    period = summary.get("first_depletion_period")
    start_year = summary.get("first_depletion_start_year")
    depleted = int(summary.get("depleted_cohorts") or 0)
    total = int(summary.get("total_cohorts") or 0)
    outcomes = list(summary.get("cohort_outcomes") or [])

    primary = str(period) if period is not None else "Not depleted"
    if period is not None:
        context = f"Earliest affected start cohort: {start_year} • Depleted cohorts: {depleted}/{total}"
    else:
        context = f"All modeled cohorts survived • Depleted cohorts: 0/{total}"

    rows = []
    for outcome in outcomes:
        start_period = escape(str(outcome.get("start_period") or outcome.get("start_year") or "—"))
        depletion_period = outcome.get("depletion_period")
        if depletion_period:
            outcome_class = "depleted"
            outcome_text = f"Depleted <b>{escape(str(depletion_period))}</b>"
        else:
            outcome_class = "survived"
            last_period = escape(str(outcome.get("last_period") or "—"))
            outcome_text = f"Not depleted through <b>{last_period}</b>"
        rows.append(
            f'<div class="monthly-depletion-cohort-row {outcome_class}">'
            f'<span>Initiated <b>{start_period}</b></span>'
            f'<span>{outcome_text}</span>'
            "</div>"
        )

    cohort_html = "".join(rows) or (
        '<div class="monthly-depletion-cohort-empty">No monthly start-year cohorts available.</div>'
    )
    return (
        '<div class="monthly-depletion-detail-card">'
        f'<span class="monthly-depletion-card-label">{escape(str(label))}</span>'
        f'<b class="monthly-depletion-card-value">{escape(primary)}</b>'
        f'<small class="monthly-depletion-card-context">{escape(context)}</small>'
        '<div class="monthly-depletion-cohort-title">ALL COHORT START AND DEPLETION MONTHS</div>'
        f'<div class="monthly-depletion-cohort-grid">{cohort_html}</div>'
        "</div>"
    )


def _finite_number(value):
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(parsed) if pd.notna(parsed) and np.isfinite(parsed) else None


def _ten_year_stats(row: pd.Series) -> dict:
    """Summarize the ten completed calendar-year return columns stored by MarketScope."""
    annual: list[tuple[str, float]] = []
    for year in YEAR_RETURN_COLS:
        value = _finite_number(row.get(year))
        if value is not None:
            annual.append((str(year), value))
    positive = sum(1 for _, value in annual if value > 0)
    cagr = None
    if len(annual) >= 10:
        selected = annual[:10]
        compound = 1.0
        valid = True
        for _, pct in selected:
            factor = 1.0 + pct / 100.0
            if factor <= 0:
                valid = False
                break
            compound *= factor
        if valid and compound > 0:
            cagr = (compound ** (1.0 / 10.0) - 1.0) * 100.0
    worst = min(annual, key=lambda item: item[1]) if annual else None
    best = max(annual, key=lambda item: item[1]) if annual else None
    return {
        "cagr_10y_pct": cagr,
        "positive_years": positive,
        "available_years": len(annual),
        "worst_year": worst[0] if worst else None,
        "worst_year_pct": worst[1] if worst else None,
        "best_year": best[0] if best else None,
        "best_year_pct": best[1] if best else None,
    }


def _portfolio_analytics_payload(meta_row: pd.Series, result: dict, income_metrics: dict, monthly_stats: dict | None = None) -> dict:
    stats = _ten_year_stats(meta_row)
    allocated = float(result.get("allocated") or 0.0)
    yield_pct = _finite_number((income_metrics or {}).get("regular_yield_pct"))
    est_dividend = allocated * yield_pct / 100.0 if yield_pct is not None else None
    industry = str(meta_row.get("Industry") or "").strip()
    if industry.lower() in {"", "unknown", "nan", "none", "etf / fund", "fund", "etf"}:
        industry = str(meta_row.get("Sector") or "Unknown").strip() or "Unknown"
    performance = {metric: _finite_number(meta_row.get(metric)) for metric in PERF_COLS}
    return {
        "industry": industry,
        "stock": str(meta_row.get("Symbol") or result.get("symbol") or "").upper(),
        "allocation_pct": float(result.get("weight") or 0.0),
        "allocation_dollars": allocated,
        "cagr_10y_pct": stats.get("cagr_10y_pct"),
        "positive_years": int(stats.get("positive_years") or 0),
        "available_years": int(stats.get("available_years") or 0),
        "positive_months": (monthly_stats or {}).get("positive_months"),
        "available_months": (monthly_stats or {}).get("available_months"),
        "worst_year": stats.get("worst_year"),
        "worst_year_pct": stats.get("worst_year_pct"),
        "best_year": stats.get("best_year"),
        "best_year_pct": stats.get("best_year_pct"),
        "regular_yield_pct": yield_pct,
        "est_annual_dividend": est_dividend,
        "yield_source": str((income_metrics or {}).get("source") or ""),
        "performance": performance,
    }


def _monthly_withdrawal_kpi_grid(
    monthly_withdrawal: float,
    rb_end: float,
    nr_end: float,
    rb_positive: int,
    rb_months: int,
    nr_positive: int,
    nr_months: int,
) -> str:
    """Responsive KPI grid that never truncates the displayed metric values."""
    diff = float(rb_end) - float(nr_end)
    cards = [
        ("Monthly withdrawal", f"${float(monthly_withdrawal):,.2f}", ""),
        ("Rebalanced remaining", f"${float(rb_end):,.2f}", "accent"),
        ("Not rebalanced remaining", f"${float(nr_end):,.2f}", "accent"),
        ("Rebalance difference", f"${diff:+,.2f}", "positive" if diff >= 0 else "negative"),
    ]
    html = []
    for label, value, css_class in cards:
        html.append(
            '<div class="monthly-withdrawal-kpi-card">'
            f'<span>{escape(label)}</span>'
            f'<b class="{css_class}">{escape(value)}</b>'
            '</div>'
        )
    html.append(
        '<div class="monthly-withdrawal-kpi-card monthly-positive-months-card">'
        '<span>Positive months</span>'
        '<div class="positive-month-lines">'
        f'<b><em>RB</em> {int(rb_positive)}/{int(rb_months)}</b>'
        f'<b><em>NR</em> {int(nr_positive)}/{int(nr_months)}</b>'
        '</div>'
        '</div>'
    )
    return '<div class="monthly-withdrawal-kpi-grid">' + "".join(html) + "</div>"


def _portfolio_summary_kpi_grid(
    invested: float,
    ending_value: float,
    profit_loss: float,
    return_pct: float,
) -> str:
    """Compact responsive simulator totals using the same cards as Monthly Withdrawal."""
    cards = [
        ("Portfolio invested", f"${float(invested):,.2f}", ""),
        ("Calculated ending value", f"${float(ending_value):,.2f}", "accent"),
        (
            "Calculated profit / loss",
            f"${float(profit_loss):+,.2f}",
            "positive" if float(profit_loss) >= 0 else "negative",
        ),
        (
            "Calculated return",
            f"{float(return_pct):+.2f}%",
            "positive" if float(return_pct) >= 0 else "negative",
        ),
    ]
    html = []
    for label, value, css_class in cards:
        html.append(
            '<div class="monthly-withdrawal-kpi-card portfolio-summary-kpi-card">'
            f'<span>{escape(label)}</span>'
            f'<b class="{css_class}">{escape(value)}</b>'
            '</div>'
        )
    return (
        '<div class="monthly-withdrawal-kpi-grid portfolio-summary-kpi-grid">'
        + "".join(html)
        + "</div>"
    )


def _annual_withdrawal_funding_counts(result: dict, requested: float) -> tuple[int, int]:
    """Return full yearly withdrawals funded / completed-year withdrawals targeted."""
    rows = [
        row for row in (result.get("schedule") or [])
        if str(row.get("year") or "").strip().lower() != "ytd (partial)"
    ]
    target = int(result.get("withdrawals_targeted") or len(rows))
    stored_funded = result.get("withdrawals_funded")
    if stored_funded is not None:
        funded = int(stored_funded)
    else:
        funded = sum(
            1
            for row in rows
            if float(row.get("withdrawal") or 0.0) >= max(0.0, float(requested)) - 0.005
        )
    return funded, target


def _annual_withdrawal_positive_year_counts(result: dict) -> tuple[int, int]:
    """Return positive completed calendar years / annual years actually modeled."""
    rows = [
        row for row in (result.get("schedule") or [])
        if str(row.get("year") or "").strip().lower() != "ytd (partial)"
    ]
    stored_positive = result.get("positive_years")
    stored_years = result.get("years_modeled")
    positive = (
        int(stored_positive)
        if stored_positive is not None
        else sum(1 for row in rows if float(row.get("portfolio_return_pct") or 0.0) > 0.0)
    )
    modeled = int(stored_years) if stored_years is not None else len(rows)
    return positive, modeled


def _annual_withdrawal_kpi_grid(
    annual_withdrawal: float,
    rb_end: float,
    nr_end: float,
    rb_positive: int,
    rb_years: int,
    nr_positive: int,
    nr_years: int,
) -> str:
    """Yearly Withdrawal summary using Positive Years just like monthly uses Positive Months."""
    diff = float(rb_end) - float(nr_end)
    cards = [
        ("Annual withdrawal", f"${float(annual_withdrawal):,.2f}", ""),
        ("Rebalanced remaining", f"${float(rb_end):,.2f}", "accent"),
        ("Not rebalanced remaining", f"${float(nr_end):,.2f}", "accent"),
        ("Rebalance difference", f"${diff:+,.2f}", "positive" if diff >= 0 else "negative"),
    ]
    html = []
    for label, value, css_class in cards:
        html.append(
            '<div class="monthly-withdrawal-kpi-card">'
            f'<span>{escape(label)}</span>'
            f'<b class="{css_class}">{escape(value)}</b>'
            '</div>'
        )
    html.append(
        '<div class="monthly-withdrawal-kpi-card monthly-positive-months-card annual-positive-years-card">'
        '<span>Positive years</span>'
        '<div class="positive-month-lines">'
        f'<b><em>RB</em> {int(rb_positive)}/{int(rb_years)}</b>'
        f'<b><em>NR</em> {int(nr_positive)}/{int(nr_years)}</b>'
        '</div>'
        '</div>'
    )
    return '<div class="monthly-withdrawal-kpi-grid">' + "".join(html) + "</div>"


def _saved_simulation_withdrawal_values(record: dict) -> dict | None:
    """Normalize saved annual/monthly withdrawal metrics for compact library rendering."""
    if not isinstance(record, dict):
        return None

    if bool(record.get("monthly_withdrawals_enabled")):
        rb = dict(record.get("monthly_withdrawal_rebalanced") or {})
        nr = dict(record.get("monthly_withdrawal_not_rebalanced") or {})
        amount = float(record.get("monthly_withdrawal_amount") or 0.0)
        rb_end = float(rb.get("ending_balance") or 0.0)
        nr_end = float(
            nr.get("ending_balance")
            if nr.get("ending_balance") is not None
            else (record.get("monthly_withdrawal_ending_balance") or 0.0)
        )
        rb_positive = int(
            rb.get("positive_months")
            if rb.get("positive_months") is not None
            else (record.get("monthly_positive_months_rebalanced") or 0)
        )
        nr_positive = int(
            nr.get("positive_months")
            if nr.get("positive_months") is not None
            else (record.get("monthly_positive_months_not_rebalanced") or 0)
        )
        rb_months = int(
            rb.get("months_modeled")
            if rb.get("months_modeled") is not None
            else (record.get("monthly_months_modeled_rebalanced") or 0)
        )
        nr_months = int(
            nr.get("months_modeled")
            if nr.get("months_modeled") is not None
            else (record.get("monthly_months_modeled_not_rebalanced") or 0)
        )
        return {
            "mode": "monthly",
            "amount_label": "MONTHLY WITHDRAWAL",
            "amount": amount,
            "rb_end": rb_end,
            "nr_end": nr_end,
            "difference": rb_end - nr_end,
            "final_label": "POSITIVE MONTHS",
            "rb_count": rb_positive,
            "rb_total": rb_months,
            "nr_count": nr_positive,
            "nr_total": nr_months,
        }

    if bool(record.get("annual_withdrawals_enabled")):
        rb = dict(record.get("withdrawal_rebalanced") or {})
        nr = dict(record.get("withdrawal_not_rebalanced") or {})
        amount = float(record.get("annual_withdrawal_amount") or 0.0)
        rb_end = float(rb.get("ending_balance") or 0.0)
        nr_end = float(
            nr.get("ending_balance")
            if nr.get("ending_balance") is not None
            else (record.get("withdrawal_ending_balance") or 0.0)
        )
        rb_positive, rb_years = _annual_withdrawal_positive_year_counts(rb)
        nr_positive, nr_years = _annual_withdrawal_positive_year_counts(nr)
        rb_positive = int(
            record.get("annual_positive_years_rebalanced")
            if record.get("annual_positive_years_rebalanced") is not None
            else rb_positive
        )
        nr_positive = int(
            record.get("annual_positive_years_not_rebalanced")
            if record.get("annual_positive_years_not_rebalanced") is not None
            else nr_positive
        )
        rb_years = int(
            record.get("annual_years_modeled_rebalanced")
            if record.get("annual_years_modeled_rebalanced") is not None
            else rb_years
        )
        nr_years = int(
            record.get("annual_years_modeled_not_rebalanced")
            if record.get("annual_years_modeled_not_rebalanced") is not None
            else nr_years
        )
        return {
            "mode": "annual",
            "amount_label": "ANNUAL WITHDRAWAL",
            "amount": amount,
            "rb_end": rb_end,
            "nr_end": nr_end,
            "difference": rb_end - nr_end,
            "final_label": "POSITIVE YEARS",
            "rb_count": rb_positive,
            "rb_total": rb_years,
            "nr_count": nr_positive,
            "nr_total": nr_years,
        }

    return None


def _saved_simulation_withdrawal_inline_html(record: dict) -> str:
    """Render saved withdrawal metrics inside the existing Saved Simulation card."""
    values = _saved_simulation_withdrawal_values(record)
    if not values:
        return ""

    diff = float(values["difference"])
    diff_class = "pos" if diff > 0 else ("neg" if diff < 0 else "flat")
    return (
        "<div class='simulation-library-withdrawal-strip'>"
        f"<div class='simulation-library-withdrawal-metric'><small>{escape(str(values['amount_label']))}</small><b>${float(values['amount']):,.2f}</b></div>"
        f"<div class='simulation-library-withdrawal-metric'><small>REBALANCED REMAINING</small><b>${float(values['rb_end']):,.2f}</b></div>"
        f"<div class='simulation-library-withdrawal-metric'><small>NOT-REBALANCED REMAINING</small><b>${float(values['nr_end']):,.2f}</b></div>"
        f"<div class='simulation-library-withdrawal-metric'><small>REBALANCE DIFFERENCE</small><b class='{diff_class}'>${diff:+,.2f}</b></div>"
        f"<div class='simulation-library-withdrawal-metric simulation-library-withdrawal-counts'><small>{escape(str(values['final_label']))}</small>"
        f"<b><em>RB</em> {int(values['rb_count'])}/{int(values['rb_total'])}</b>"
        f"<b><em>NR</em> {int(values['nr_count'])}/{int(values['nr_total'])}</b></div>"
        "</div>"
    )


def _saved_simulation_withdrawal_kpi(record: dict) -> tuple[str, str] | None:
    """Return the saved simulation's annual/monthly five-card withdrawal summary."""
    values = _saved_simulation_withdrawal_values(record)
    if not values:
        return None

    if values["mode"] == "monthly":
        return (
            "MONTHLY WITHDRAWAL SUMMARY",
            _monthly_withdrawal_kpi_grid(
                float(values["amount"]),
                float(values["rb_end"]),
                float(values["nr_end"]),
                int(values["rb_count"]),
                int(values["rb_total"]),
                int(values["nr_count"]),
                int(values["nr_total"]),
            ),
        )

    return (
        "ANNUAL WITHDRAWAL SUMMARY",
        _annual_withdrawal_kpi_grid(
            float(values["amount"]),
            float(values["rb_end"]),
            float(values["nr_end"]),
            int(values["rb_count"]),
            int(values["rb_total"]),
            int(values["nr_count"]),
            int(values["nr_total"]),
        ),
    )


def _portfolio_analytics_dataframe(payloads: list[dict]) -> pd.DataFrame:
    rows = []
    for item in payloads:
        perf = item.get("performance") or {}
        worst = (
            f"{item.get('worst_year')} ({float(item.get('worst_year_pct')):+.2f}%)"
            if item.get("worst_year") and item.get("worst_year_pct") is not None else "—"
        )
        best = (
            f"{item.get('best_year')} ({float(item.get('best_year_pct')):+.2f}%)"
            if item.get("best_year") and item.get("best_year_pct") is not None else "—"
        )
        cagr = item.get("cagr_10y_pct")
        yld = item.get("regular_yield_pct")
        div = item.get("est_annual_dividend")
        row = {
            "Industry": item.get("industry") or "Unknown",
            "Stock": item.get("stock") or "—",
            "Allocation": f"{float(item.get('allocation_pct') or 0):.2f}% / ${float(item.get('allocation_dollars') or 0):,.2f}",
            "10-year CAGR": f"{float(cagr):+.2f}%" if cagr is not None else "—",
            "Positive years": f"{int(item.get('positive_years') or 0)}/{int(item.get('available_years') or 0)}",
            "Positive months": (
                f"{int(item.get('positive_months'))}/{int(item.get('available_months'))}"
                if item.get("positive_months") is not None and item.get("available_months") is not None else "—"
            ),
            "Worst year and %": worst,
            "Best year and %": best,
            "Regular yield": f"{float(yld):.2f}%" if yld is not None else "—",
            "Est. annual dividend": f"${float(div):,.2f}" if div is not None else "—",
        }
        for metric in PERF_COLS:
            value = perf.get(metric)
            row[metric] = f"{float(value):+.2f}%" if value is not None else "—"
        rows.append(row)
    return pd.DataFrame(rows)


with portfolio_tab:
    # Multi-instrument portfolio split simulator — collapsible in v5.9.9.
    portfolio_total = 0.0
    selected_portfolio_symbols: list[str] = []
    portfolio_period = "YTD"
    portfolio_allocation_mode = "Equal split"
    portfolio_include_ytd = False
    portfolio_withdrawals_enabled = False
    portfolio_annual_withdrawal = 0.0
    portfolio_monthly_withdrawals_enabled = False
    portfolio_monthly_withdrawal = 0.0
    portfolio_withdrawal_result: dict = {}
    portfolio_withdrawal_rebalanced_result: dict = {}
    portfolio_withdrawal_not_rebalanced_result: dict = {}
    portfolio_monthly_withdrawal_result: dict = {}
    portfolio_monthly_withdrawal_rebalanced_result: dict = {}
    portfolio_monthly_withdrawal_not_rebalanced_result: dict = {}
    portfolio_weights: dict[str, float] = {}
    portfolio_results: list[dict] = []
    portfolio_analytics: list[dict] = []
    portfolio_income_metrics: dict[str, dict] = {}
    calculated: list[dict] = []
    unresolved_amount = 0.0
    total_ending = 0.0
    total_start_calculated = 0.0
    total_profit = 0.0
    total_return = 0.0
    allocation_valid = False

    portfolio_build_tab, portfolio_manage_tab = st.tabs([
        "◆ Build Simulation",
        "💾 Saved / Manage",
    ])

    with portfolio_build_tab:
        st.markdown("<div class='investment-title'>PORTFOLIO SPLIT SIMULATOR</div>", unsafe_allow_html=True)

        all_portfolio_symbols = market["Symbol"].astype(str).str.upper().drop_duplicates().tolist()
        valid_saved_portfolio = [s for s in st.session_state.portfolio_symbols if s in set(all_portfolio_symbols)]
        if valid_saved_portfolio != st.session_state.portfolio_symbols:
            st.session_state.portfolio_symbols = valid_saved_portfolio

        # v5.9.53: ranking families stay hidden until their respective button is opened.
        st.caption("Portfolio preset rankings are grouped below. Open only the ranking family you want to use.")
        preset_row1 = st.columns(3)
        preset_row2 = st.columns(4)

        def _render_profit_worst_rankings(period_label: str, profit_file: Path, worst_file: Path) -> None:
            st.caption(
                f"{period_label} • four stocks • four different sectors • equal 25% starting allocation • "
                "$100,000 normalized starting portfolio."
            )
            profit_rank = _load_ranked_combo_file(str(profit_file))
            worst_rank = _load_ranked_combo_file(str(worst_file))
            st.markdown(f"#### 💰 Top 200 — Best Profit ({period_label})")
            if profit_rank.empty:
                st.warning(f"{period_label} profit-generator ranking data is unavailable.")
            else:
                lookup_key = f"combo_{period_label.lower()}_profit_lookup"
                picker_key = f"combo_{period_label.lower()}_profit_picker"
                profit_lookup = {}
                profit_options = [f"— Select a Top 200 {period_label} profit combo —"]
                for _, combo_row in profit_rank.sort_values("Rank").iterrows():
                    label = _ranked_combo_label(combo_row, "profit")
                    profit_options.append(label)
                    profit_lookup[label] = _ranked_combo_symbols(combo_row)
                st.session_state[lookup_key] = profit_lookup
                st.selectbox(
                    f"{period_label} profit generator combination",
                    options=profit_options, index=0, key=picker_key,
                    on_change=_apply_ranked_combo_selection,
                    args=(picker_key, lookup_key, f"{period_label} Top Profit Generator combo", period_label),
                )
            st.markdown(f"#### 🛡️ Top 200 — Best Worst Year ({period_label})")
            if worst_rank.empty:
                st.warning(f"{period_label} best-worst-year ranking data is unavailable.")
            else:
                lookup_key = f"combo_{period_label.lower()}_worst_lookup"
                picker_key = f"combo_{period_label.lower()}_worst_picker"
                worst_lookup = {}
                worst_options = [f"— Select a Top 200 {period_label} best-worst-year combo —"]
                for _, combo_row in worst_rank.sort_values("Rank").iterrows():
                    label = _ranked_combo_label(combo_row, "worst")
                    worst_options.append(label)
                    worst_lookup[label] = _ranked_combo_symbols(combo_row)
                st.session_state[lookup_key] = worst_lookup
                st.selectbox(
                    f"{period_label} best worst-year combination",
                    options=worst_options, index=0, key=picker_key,
                    on_change=_apply_ranked_combo_selection,
                    args=(picker_key, lookup_key, f"{period_label} Best Worst-Year combo", period_label),
                )
            table_profit_tab, table_worst_tab = st.tabs([
                f"💰 {period_label} Profit table", f"🛡️ {period_label} Best Worst-Year table",
            ])
            with table_profit_tab:
                st.dataframe(_combo_rank_table(profit_rank, period_label), use_container_width=True, hide_index=True, height=500)
            with table_worst_tab:
                st.dataframe(_combo_rank_table(worst_rank, period_label), use_container_width=True, hide_index=True, height=500)

        with preset_row1[0]:
            with st.popover("📈 5Y Combo Rankings", use_container_width=True):
                _render_profit_worst_rankings("5Y", COMBO_5Y_PROFIT_FILE, COMBO_5Y_WORST_FILE)

        with preset_row1[1]:
            with st.popover("📊 10Y Combo Rankings", use_container_width=True):
                _render_profit_worst_rankings("10Y", COMBO_10Y_PROFIT_FILE, COMBO_10Y_WORST_FILE)

        with preset_row1[2]:
            with st.popover("💵 10Y Yearly Withdrawal", use_container_width=True):
                st.markdown("### $300K Start / $85K per Year")
                st.caption(
                    f"Top 100 surviving four-stock portfolios, four different sectors, {COMBO_RANK_YEARS_BY_PERIOD['10Y'][-1]}–{COMBO_RANK_YEARS_BY_PERIOD['10Y'][0]}. "
                    "Every table now exposes the full stock/sector/name, annual-return, worst/best-year, cash-flow, ending-balance, and yearly-balance fields."
                )
                rebalance_rank = _load_ranked_combo_file(str(COMBO_10Y_REBALANCED_WITHDRAWAL_FILE))
                not_rebalanced_rank = _load_ranked_combo_file(str(COMBO_10Y_NOT_REBALANCED_WITHDRAWAL_FILE))
                st.markdown("#### 🔄 Rebalanced Annually")
                if rebalance_rank.empty:
                    st.warning("10Y rebalanced withdrawal ranking data is unavailable.")
                else:
                    lookup_key = "combo_10y_withdrawal_rebalanced_lookup"
                    picker_key = "combo_10y_withdrawal_rebalanced_picker"
                    lookup = {}
                    options = ["— Select a Top 100 rebalanced withdrawal combo —"]
                    for _, combo_row in rebalance_rank.sort_values("Rank").iterrows():
                        label = _ranked_withdrawal_combo_label(combo_row, "Rebalanced")
                        options.append(label); lookup[label] = _ranked_combo_symbols(combo_row)
                    st.session_state[lookup_key] = lookup
                    st.selectbox("10Y rebalanced withdrawal combination", options=options, index=0, key=picker_key,
                                 on_change=_apply_withdrawal_ranked_combo_selection,
                                 args=(picker_key, lookup_key, "10Y Rebalanced Withdrawal combo"))
                st.markdown("#### ↗ Not Rebalanced")
                if not_rebalanced_rank.empty:
                    st.warning("10Y not-rebalanced withdrawal ranking data is unavailable.")
                else:
                    lookup_key = "combo_10y_withdrawal_not_rebalanced_lookup"
                    picker_key = "combo_10y_withdrawal_not_rebalanced_picker"
                    lookup = {}; options = ["— Select a Top 100 not-rebalanced withdrawal combo —"]
                    for _, combo_row in not_rebalanced_rank.sort_values("Rank").iterrows():
                        label = _ranked_withdrawal_combo_label(combo_row, "Not Rebalanced")
                        options.append(label); lookup[label] = _ranked_combo_symbols(combo_row)
                    st.session_state[lookup_key] = lookup
                    st.selectbox("10Y not-rebalanced withdrawal combination", options=options, index=0, key=picker_key,
                                 on_change=_apply_withdrawal_ranked_combo_selection,
                                 args=(picker_key, lookup_key, "10Y Not-Rebalanced Withdrawal combo"))
                trb, tnr = st.tabs(["🔄 Rebalanced Top 100", "↗ Not Rebalanced Top 100"])
                with trb:
                    st.dataframe(_withdrawal_combo_rank_table(rebalance_rank), use_container_width=True, hide_index=True, height=520)
                with tnr:
                    st.dataframe(_withdrawal_combo_rank_table(not_rebalanced_rank), use_container_width=True, hide_index=True, height=520)

        with preset_row2[0]:
            with st.popover("🗓️ 10Y Actual-Monthly Withdrawal", use_container_width=True):
                st.markdown("### $300K Start / $5K per Month · HWM Excluded")
                st.caption(
                    "Actual adjusted month-end returns from Yahoo/yfinance daily history. All 120 withdrawals must be funded. "
                    "Tables use the same detailed structure as the yearly withdrawal rankings, adapted for monthly cash flow and Positive Months."
                )
                monthly_rebalance_rank = _load_actual_monthly_ranked_combo_file(str(COMBO_10Y_REBALANCED_MONTHLY_WITHDRAWAL_FILE))
                monthly_not_rebalanced_rank = _load_actual_monthly_ranked_combo_file(str(COMBO_10Y_NOT_REBALANCED_MONTHLY_WITHDRAWAL_FILE))
                st.markdown("#### 🔄 Rebalanced Monthly")
                if monthly_rebalance_rank.empty:
                    st.warning("Actual-monthly 10Y rebalanced ranking data is not available yet. Run the MarketScope refresh workflow.")
                else:
                    lookup_key = "combo_10y_monthly_withdrawal_rebalanced_lookup"
                    picker_key = "combo_10y_monthly_withdrawal_rebalanced_picker"
                    lookup = {}; options = ["— Select a Top 100 monthly rebalanced combo —"]
                    for _, combo_row in monthly_rebalance_rank.sort_values("Rank").iterrows():
                        label = _ranked_withdrawal_combo_label(combo_row, "Rebalanced")
                        options.append(label); lookup[label] = _ranked_combo_symbols(combo_row)
                    st.session_state[lookup_key] = lookup
                    st.selectbox("10Y monthly rebalanced combination — actual returns", options=options, index=0, key=picker_key,
                                 on_change=_apply_monthly_withdrawal_ranked_combo_selection,
                                 args=(picker_key, lookup_key, "10Y Monthly Rebalanced Withdrawal combo"))
                st.markdown("#### ↗ Not Rebalanced Monthly")
                if monthly_not_rebalanced_rank.empty:
                    st.warning("Actual-monthly 10Y not-rebalanced ranking data is not available yet. Run the MarketScope refresh workflow.")
                else:
                    lookup_key = "combo_10y_monthly_withdrawal_not_rebalanced_lookup"
                    picker_key = "combo_10y_monthly_withdrawal_not_rebalanced_picker"
                    lookup = {}; options = ["— Select a Top 100 monthly not-rebalanced combo —"]
                    for _, combo_row in monthly_not_rebalanced_rank.sort_values("Rank").iterrows():
                        label = _ranked_withdrawal_combo_label(combo_row, "Not Rebalanced")
                        options.append(label); lookup[label] = _ranked_combo_symbols(combo_row)
                    st.session_state[lookup_key] = lookup
                    st.selectbox("10Y monthly not-rebalanced combination — actual returns", options=options, index=0, key=picker_key,
                                 on_change=_apply_monthly_withdrawal_ranked_combo_selection,
                                 args=(picker_key, lookup_key, "10Y Monthly Not-Rebalanced Withdrawal combo"))
                mrb_tab, mnr_tab = st.tabs(["🔄 Monthly Rebalanced Top 100", "↗ Monthly Not Rebalanced Top 100"])
                with mrb_tab:
                    st.dataframe(_monthly_withdrawal_combo_rank_table(monthly_rebalance_rank), use_container_width=True, hide_index=True, height=520)
                with mnr_tab:
                    st.dataframe(_monthly_withdrawal_combo_rank_table(monthly_not_rebalanced_rank), use_container_width=True, hide_index=True, height=520)

        with preset_row2[1]:
            with st.popover("🛡️ Recession-Balanced Top 100", use_container_width=True):
                st.markdown("### 2 Profit Engines + 2 Recession-Defense Stocks")
                st.caption(
                    "Exactly four stocks from four different sectors: 2 Profit Engines + 2 Recession Defense stocks. "
                    "Each ticker may appear in no more than 5 of the Top 100 combinations, so the list is intentionally diversified instead of repeatedly recycling the same winners. "
                    "NBER periods: Mar–Nov 2001, Dec 2007–Jun 2009, and Feb–Apr 2020. Rankings use a $300,000 equal-weight start and no withdrawals to isolate growth and recession behavior."
                )
                recession_rb = _load_ranked_combo_file(str(COMBO_RECESSION_REBALANCED_FILE))
                recession_nr = _load_ranked_combo_file(str(COMBO_RECESSION_NOT_REBALANCED_FILE))
                st.markdown("#### 🔄 Top 100 — Rebalanced Annually")
                if recession_rb.empty:
                    st.warning("Recession-balanced rebalanced ranking data is unavailable until the refresh/ranking job completes.")
                else:
                    lookup_key = "combo_recession_rebalanced_lookup"; picker_key = "combo_recession_rebalanced_picker"
                    lookup = {}; options = ["— Select a Top 100 recession-balanced rebalanced combo —"]
                    for _, combo_row in recession_rb.sort_values("Rank").iterrows():
                        label = _ranked_withdrawal_combo_label(combo_row, "Rebalanced")
                        options.append(label); lookup[label] = _ranked_combo_symbols(combo_row)
                    st.session_state[lookup_key] = lookup
                    st.selectbox("Recession-balanced rebalanced combination", options=options, index=0, key=picker_key,
                                 on_change=_apply_recession_ranked_combo_selection,
                                 args=(picker_key, lookup_key, "Recession-Balanced Rebalanced combo"))
                st.markdown("#### ↗ Top 100 — Not Rebalanced")
                if recession_nr.empty:
                    st.warning("Recession-balanced not-rebalanced ranking data is unavailable until the refresh/ranking job completes.")
                else:
                    lookup_key = "combo_recession_not_rebalanced_lookup"; picker_key = "combo_recession_not_rebalanced_picker"
                    lookup = {}; options = ["— Select a Top 100 recession-balanced not-rebalanced combo —"]
                    for _, combo_row in recession_nr.sort_values("Rank").iterrows():
                        label = _ranked_withdrawal_combo_label(combo_row, "Not Rebalanced")
                        options.append(label); lookup[label] = _ranked_combo_symbols(combo_row)
                    st.session_state[lookup_key] = lookup
                    st.selectbox("Recession-balanced not-rebalanced combination", options=options, index=0, key=picker_key,
                                 on_change=_apply_recession_ranked_combo_selection,
                                 args=(picker_key, lookup_key, "Recession-Balanced Not-Rebalanced combo"))
                rbt, nrt = st.tabs(["🔄 Rebalanced Top 100", "↗ Not Rebalanced Top 100"])
                with rbt:
                    st.dataframe(_recession_combo_rank_table(recession_rb), use_container_width=True, hide_index=True, height=520)
                with nrt:
                    st.dataframe(_recession_combo_rank_table(recession_nr), use_container_width=True, hide_index=True, height=520)
                st.caption(
                    "Recession Defense is a historical resilience screen, not a guarantee. A hard maximum of five Top-100 appearances per ticker is enforced in each strategy ranking. The next successful MarketScope refresh regenerates these rankings from the current annual-return snapshot."
                )

        with preset_row2[2]:
            with st.popover("💰 10Y $160K Withdrawal Top 100", use_container_width=True):
                st.markdown("### $300K Start / $160K per Year · Max 5 Uses per Ticker")
                st.caption(
                    "Four stocks from four different sectors, equal 25% starting allocation, using the completed "
                    "2016–2025 annual returns in the saved CSV ranking source. Each ticker may appear in no more "
                    "than five of the Top 100 combinations in each strategy. Rankings prioritize the number of "
                    "full $160,000 withdrawals funded, then total cash delivered, then ending balance."
                )
                high_rb = _load_ranked_combo_file(str(COMBO_10Y_REBALANCED_WITHDRAWAL_160K_FILE))
                high_nr = _load_ranked_combo_file(str(COMBO_10Y_NOT_REBALANCED_WITHDRAWAL_160K_FILE))

                st.markdown("#### 🔄 Top 100 — Rebalanced Annually")
                if high_rb.empty:
                    st.warning("$160K rebalanced ranking data is unavailable.")
                else:
                    lookup_key = "combo_10y_160k_rebalanced_lookup"
                    picker_key = "combo_10y_160k_rebalanced_picker"
                    lookup = {}
                    options = ["— Select a Top 100 $160K rebalanced combo —"]
                    for _, combo_row in high_rb.sort_values("Rank").iterrows():
                        label = _ranked_withdrawal_combo_label(combo_row, "Rebalanced")
                        options.append(label)
                        lookup[label] = _ranked_combo_symbols(combo_row)
                    st.session_state[lookup_key] = lookup
                    st.selectbox(
                        "10Y $160K rebalanced withdrawal combination",
                        options=options,
                        index=0,
                        key=picker_key,
                        on_change=_apply_withdrawal_ranked_combo_selection,
                        args=(
                            picker_key,
                            lookup_key,
                            "10Y $160K Rebalanced Withdrawal combo",
                            COMBO_WITHDRAWAL_ANNUAL_160K,
                        ),
                    )

                st.markdown("#### ↗ Top 100 — Not Rebalanced")
                if high_nr.empty:
                    st.warning("$160K not-rebalanced ranking data is unavailable.")
                else:
                    lookup_key = "combo_10y_160k_not_rebalanced_lookup"
                    picker_key = "combo_10y_160k_not_rebalanced_picker"
                    lookup = {}
                    options = ["— Select a Top 100 $160K not-rebalanced combo —"]
                    for _, combo_row in high_nr.sort_values("Rank").iterrows():
                        label = _ranked_withdrawal_combo_label(combo_row, "Not Rebalanced")
                        options.append(label)
                        lookup[label] = _ranked_combo_symbols(combo_row)
                    st.session_state[lookup_key] = lookup
                    st.selectbox(
                        "10Y $160K not-rebalanced withdrawal combination",
                        options=options,
                        index=0,
                        key=picker_key,
                        on_change=_apply_withdrawal_ranked_combo_selection,
                        args=(
                            picker_key,
                            lookup_key,
                            "10Y $160K Not-Rebalanced Withdrawal combo",
                            COMBO_WITHDRAWAL_ANNUAL_160K,
                        ),
                    )

                high_rb_tab, high_nr_tab = st.tabs([
                    "🔄 Rebalanced Top 100",
                    "↗ Not Rebalanced Top 100",
                ])
                with high_rb_tab:
                    st.dataframe(
                        _withdrawal_combo_rank_table(high_rb),
                        use_container_width=True,
                        hide_index=True,
                        height=540,
                    )
                with high_nr_tab:
                    st.dataframe(
                        _withdrawal_combo_rank_table(high_nr),
                        use_container_width=True,
                        hide_index=True,
                        height=540,
                    )

                st.caption(
                    "Because $160,000 per year is a very high withdrawal relative to a $300,000 starting portfolio, "
                    "the table explicitly shows Withdrawals Fully Funded and Depleted Year. The max-five rule is "
                    "enforced across the full Top 100 list, not just within an individual combination."
                )

        with preset_row2[3]:
            with st.popover("🏆 20Y $160K Withdrawal Top 250", use_container_width=True):
                st.markdown("### $300K Start / $160K per Year · 20Y · Max 10 Uses per Ticker")
                st.caption(
                    "Exactly four stocks from four different sectors, equal 25% starting allocation, using "
                    "20 completed annual returns (2006–2025) from the saved annual-performance source. "
                    "Each ticker may appear in no more than 10 of the Top 250 combinations in each strategy. "
                    "Ranking priority is withdrawals fully funded, then total cash delivered, then ending balance."
                )
                long_rb = _load_ranked_combo_file(str(COMBO_20Y_REBALANCED_WITHDRAWAL_160K_FILE))
                long_nr = _load_ranked_combo_file(str(COMBO_20Y_NOT_REBALANCED_WITHDRAWAL_160K_FILE))

                st.markdown("#### 🔄 Top 250 — Rebalanced Annually")
                if long_rb.empty:
                    st.warning("20Y $160K rebalanced Top 250 ranking data is unavailable.")
                else:
                    lookup_key = "combo_20y_160k_rebalanced_lookup"
                    picker_key = "combo_20y_160k_rebalanced_picker"
                    lookup = {}
                    options = ["— Select a Top 250 20Y $160K rebalanced combo —"]
                    for _, combo_row in long_rb.sort_values("Rank").iterrows():
                        label = _ranked_withdrawal_combo_label(combo_row, "Rebalanced")
                        options.append(label)
                        lookup[label] = _ranked_combo_symbols(combo_row)
                    st.session_state[lookup_key] = lookup
                    st.selectbox(
                        "20Y $160K rebalanced withdrawal combination",
                        options=options,
                        index=0,
                        key=picker_key,
                        on_change=_apply_withdrawal_ranked_combo_selection,
                        args=(
                            picker_key,
                            lookup_key,
                            "20Y $160K Rebalanced Withdrawal combo",
                            COMBO_WITHDRAWAL_ANNUAL_160K,
                            "20Y",
                        ),
                    )

                st.markdown("#### ↗ Top 250 — Not Rebalanced")
                if long_nr.empty:
                    st.warning("20Y $160K not-rebalanced Top 250 ranking data is unavailable.")
                else:
                    lookup_key = "combo_20y_160k_not_rebalanced_lookup"
                    picker_key = "combo_20y_160k_not_rebalanced_picker"
                    lookup = {}
                    options = ["— Select a Top 250 20Y $160K not-rebalanced combo —"]
                    for _, combo_row in long_nr.sort_values("Rank").iterrows():
                        label = _ranked_withdrawal_combo_label(combo_row, "Not Rebalanced")
                        options.append(label)
                        lookup[label] = _ranked_combo_symbols(combo_row)
                    st.session_state[lookup_key] = lookup
                    st.selectbox(
                        "20Y $160K not-rebalanced withdrawal combination",
                        options=options,
                        index=0,
                        key=picker_key,
                        on_change=_apply_withdrawal_ranked_combo_selection,
                        args=(
                            picker_key,
                            lookup_key,
                            "20Y $160K Not-Rebalanced Withdrawal combo",
                            COMBO_WITHDRAWAL_ANNUAL_160K,
                            "20Y",
                        ),
                    )

                long_rb_tab, long_nr_tab = st.tabs([
                    "🔄 Rebalanced Top 250",
                    "↗ Not Rebalanced Top 250",
                ])
                with long_rb_tab:
                    st.dataframe(
                        _withdrawal_combo_rank_table(long_rb),
                        use_container_width=True,
                        hide_index=True,
                        height=560,
                    )
                with long_nr_tab:
                    st.dataframe(
                        _withdrawal_combo_rank_table(long_nr),
                        use_container_width=True,
                        hide_index=True,
                        height=560,
                    )

                st.caption(
                    "A $160,000 annual withdrawal is extremely aggressive relative to a $300,000 starting "
                    "portfolio. The ranking therefore displays Withdrawals Fully Funded and Depleted Year. "
                    "In this 20-year historical window, no four-stock portfolio in the eligible universe funds "
                    "all 20 full withdrawals; the best combinations fund six before depletion. The max-10 rule "
                    "is enforced across the entire Top 250 list."
                )

        st.button(
            "Project Future - Ranked Portfolio",
            key="project_future_ranked_portfolio",
            on_click=_queue_current_portfolio_for_future_projection,
            disabled=len(st.session_state.get("portfolio_symbols") or []) != 4,
            help="Open Future Projection with the four-stock/ETF ranked portfolio currently loaded above.",
        )

        portfolio_total = st.number_input(
            "Total portfolio amount ($)",
            min_value=0.0,
            max_value=10_000_000_000.0,
            value=100_000.0,
            step=10_000.0,
            format="%.2f",
            key="portfolio_total_amount",
            help="Enter the total amount you want to split across multiple tracked stocks and ETFs.",
        )
        portfolio_name_map = {}
        for _, _prow in market.iterrows():
            _sym = str(_prow.get("Symbol") or "").upper()
            _label = _card_display_name(_prow) if "_card_display_name" in globals() else str(_prow.get("Name") or _sym)
            portfolio_name_map[_sym] = f"{_sym} — {_label}"
        selected_portfolio_symbols = st.multiselect(
            "Portfolio instruments",
            options=all_portfolio_symbols,
            default=valid_saved_portfolio,
            format_func=lambda sym: portfolio_name_map.get(sym, sym),
            key="portfolio_symbol_picker",
            placeholder="Search and select stocks / ETFs...",
        )
        st.session_state.portfolio_symbols = list(selected_portfolio_symbols)
        st.button(
            "Project Future",
            key="project_future_selected_portfolio",
            on_click=_queue_current_portfolio_for_future_projection,
            disabled=len(selected_portfolio_symbols) != 4,
            help="Open Future Projection with these four holdings and the current amount, withdrawals, and allocation.",
        )

        # v5.9.32 - keep every 1Y-{ANNUAL_HISTORY_YEARS}Y choice available. If a selected instrument did not exist
        # for the full requested span, begin at the first completed year shared by all selections.
        portfolio_period_options = ["YTD", *ANNUAL_HORIZON_OPTIONS]
        _saved_period = str(st.session_state.get("portfolio_period") or "YTD")
        if _saved_period not in portfolio_period_options:
            st.session_state["portfolio_period"] = "YTD"
        common_calendar_years = _portfolio_common_calendar_years(market, list(selected_portfolio_symbols), ANNUAL_HISTORY_YEARS)

        port_controls = st.columns([1.7, 1.35, 1.35, 2.4])
        with port_controls[0]:
            portfolio_period = st.segmented_control(
                "Portfolio period",
                portfolio_period_options,
                default="YTD",
                key="portfolio_period",
                format_func=timeframe_display_label,
                help="Historical choices are limited to the newest contiguous completed years available for every selected instrument. Pre-IPO/pre-inception years are not simulated.",
            )
            if selected_portfolio_symbols and str(portfolio_period or "YTD") != "YTD":
                _effective = _effective_portfolio_years(market, list(selected_portfolio_symbols), str(portfolio_period))
                _requested = int(str(portfolio_period).replace("Y", ""))
                if _effective:
                    _oldest, _newest = _effective[-1], _effective[0]
                    if len(_effective) < _requested:
                        st.caption(
                            f"Requested {_requested}Y • effective common history {len(_effective)}Y ({_oldest}–{_newest}). "
                            "Simulation starts only once every selected instrument has a valid completed-year return."
                        )
                    else:
                        st.caption(f"Common simulation window: {_oldest}–{_newest} ({len(_effective)} completed years).")
                else:
                    st.caption("No completed calendar year is shared by every selected instrument yet. Use YTD or change the portfolio.")
        with port_controls[1]:
            portfolio_allocation_mode = st.segmented_control(
                "Allocation", ["Equal split", "Custom %"], default="Equal split", key="portfolio_allocation_mode"
            )
        with port_controls[2]:
            portfolio_include_ytd = st.toggle(
                "Add current YTD",
                value=False,
                key="portfolio_include_ytd",
                disabled=str(portfolio_period or "YTD") == "YTD",
                help=f"For 1Y–{ANNUAL_HISTORY_YEARS}Y only, optionally apply the current YTD return after the completed-year history.",
            )
        with port_controls[3]:
            st.caption(
                "Example: enter $200,000, choose several instruments, then use an equal split or custom percentages. "
                "MarketScope calculates each allocation separately and totals the simulated ending value and profit."
            )

        withdrawal_controls = st.columns([1.05, 1.35, 1.05, 1.35, 2.7])
        with withdrawal_controls[0]:
            portfolio_withdrawals_enabled = st.toggle(
                "Yearly withdrawal",
                value=False,
                key="portfolio_withdrawals_enabled",
                disabled=str(portfolio_period or "YTD") == "YTD",
                on_change=_on_yearly_withdrawal_toggle,
                help=f"Apply the same withdrawal after each completed calendar year return shown in Market Table. Supports the full 1Y–{ANNUAL_HISTORY_YEARS}Y history where every selected instrument has data. Yearly and Monthly withdrawal modes are mutually exclusive.",
            )
        with withdrawal_controls[1]:
            portfolio_annual_withdrawal = st.number_input(
                "Withdrawal / year ($)",
                min_value=0.0, max_value=10_000_000_000.0, value=10_000.0, step=5_000.0, format="%.2f",
                key="portfolio_annual_withdrawal", disabled=not bool(portfolio_withdrawals_enabled),
                help="Taken at the end of each completed calendar year after that year's return is applied.",
            )
        with withdrawal_controls[2]:
            portfolio_monthly_withdrawals_enabled = st.toggle(
                "Monthly withdrawal",
                value=False,
                key="portfolio_monthly_withdrawals_enabled",
                disabled=str(portfolio_period or "YTD") == "YTD",
                on_change=_on_monthly_withdrawal_toggle,
                help="Apply the same cash withdrawal every month using the durable actual month-end history generated from the same adjusted daily prices as Market Table. Monthly returns are reconciled to each listed annual return.",
            )
        with withdrawal_controls[3]:
            portfolio_monthly_withdrawal = st.number_input(
                "Withdrawal / month ($)",
                min_value=0.0, max_value=10_000_000_000.0, value=5_000.0, step=1_000.0, format="%.2f",
                key="portfolio_monthly_withdrawal", disabled=not bool(portfolio_monthly_withdrawals_enabled),
                help="Taken at the end of every modeled month. For the 10Y preset this means 120 withdrawals.",
            )
        with withdrawal_controls[4]:
            if portfolio_monthly_withdrawals_enabled:
                st.caption(
                    "Monthly mode: each stock uses actual adjusted month-to-month returns generated from the same historical prices as Market Table. "
                    "Each completed year's 12 monthly returns are reconciled to the annual return shown in Table View before withdrawals are modeled. "
                    "Return is applied first, then the monthly cash withdrawal. Add current YTD is not applied to monthly withdrawal schedules."
                )
            elif portfolio_withdrawals_enabled:
                st.caption(
                    "Yearly mode: each stock receives the exact completed calendar-year return shown in Market Table, then the requested yearly cash withdrawal is removed proportionally. "
                    "If current YTD is added, it appears as a final partial row with no additional yearly withdrawal."
                )
            else:
                st.caption("Choose Yearly withdrawal or Monthly withdrawal to model recurring portfolio income. Only one frequency can be active at a time.")

        portfolio_weights: dict[str, float] = {}
        portfolio_results: list[dict] = []
        portfolio_analytics: list[dict] = []
        portfolio_income_metrics: dict[str, dict] = {}
        portfolio_withdrawal_result: dict = {}
        portfolio_withdrawal_rebalanced_result: dict = {}
        portfolio_withdrawal_not_rebalanced_result: dict = {}
        portfolio_monthly_withdrawal_result: dict = {}
        portfolio_monthly_withdrawal_rebalanced_result: dict = {}
        portfolio_monthly_withdrawal_not_rebalanced_result: dict = {}
        calculated: list[dict] = []
        unresolved_amount = 0.0
        total_ending = 0.0
        total_start_calculated = 0.0
        total_profit = 0.0
        total_return = 0.0
        allocation_valid = False
        if selected_portfolio_symbols:
            if portfolio_allocation_mode == "Equal split":
                equal_weight = 100.0 / len(selected_portfolio_symbols)
                portfolio_weights = {sym: equal_weight for sym in selected_portfolio_symbols}
                st.caption(f"Equal allocation: {equal_weight:.2f}% per instrument across {len(selected_portfolio_symbols)} selection(s).")
            else:
                st.markdown("**Custom allocation percentages**")
                alloc_cols = st.columns(min(4, max(1, len(selected_portfolio_symbols))))
                default_pct = 100.0 / len(selected_portfolio_symbols)
                for idx, sym in enumerate(selected_portfolio_symbols):
                    with alloc_cols[idx % len(alloc_cols)]:
                        portfolio_weights[sym] = st.number_input(
                            f"{sym} %",
                            min_value=0.0,
                            max_value=100.0,
                            value=float(default_pct),
                            step=1.0,
                            format="%.2f",
                            key=f"portfolio_weight_{sym}",
                        )
                weight_sum = sum(portfolio_weights.values())
                st.caption(f"Allocated: {weight_sum:.2f}%")

            allocation_valid = portfolio_allocation_mode == "Equal split" or abs(sum(portfolio_weights.values()) - 100.0) <= 0.05
            if not allocation_valid:
                st.warning("Custom allocation must total 100% before the portfolio result can be calculated.")
            elif portfolio_total > 0:
                portfolio_rows = market.set_index(market["Symbol"].astype(str).str.upper(), drop=False)
                effective_portfolio_years = (
                    _effective_portfolio_years(market, list(selected_portfolio_symbols), str(portfolio_period or "YTD"))
                    if str(portfolio_period or "YTD") != "YTD" else []
                )
                portfolio_results = []
                unresolved_amount = 0.0
                for sym in selected_portfolio_symbols:
                    weight = float(portfolio_weights.get(sym, 0.0))
                    allocated = float(portfolio_total) * weight / 100.0
                    if sym not in portfolio_rows.index:
                        unresolved_amount += allocated
                        continue
                    row = portfolio_rows.loc[sym]
                    if isinstance(row, pd.DataFrame):
                        row = row.iloc[0]
                    result = _portfolio_horizon_projection(
                        row, allocated, str(portfolio_period or "YTD"), bool(portfolio_include_ytd), effective_portfolio_years
                    )
                    if result is None or result.get("unavailable"):
                        unresolved_amount += allocated
                        portfolio_results.append({"symbol": sym, "weight": weight, "allocated": allocated, "unavailable": True})
                        continue
                    portfolio_results.append({"symbol": sym, "weight": weight, "allocated": allocated, **result})

                calculated = [r for r in portfolio_results if not r.get("unavailable")]
                total_ending = sum(float(r["ending_value"]) for r in calculated)
                total_start_calculated = sum(float(r["allocated"]) for r in calculated)
                total_profit = total_ending - total_start_calculated
                total_return = ((total_ending / total_start_calculated) - 1.0) * 100.0 if total_start_calculated > 0 else 0.0
                st.markdown(
                    _portfolio_summary_kpi_grid(
                        float(portfolio_total),
                        total_ending,
                        total_profit,
                        total_return,
                    ),
                    unsafe_allow_html=True,
                )
                if unresolved_amount > 0:
                    st.warning(
                        f"${unresolved_amount:,.2f} of the starting allocation could not be simulated because no common return data was available. "
                        f"MarketScope otherwise shortens the requested 1Y–{ANNUAL_HISTORY_YEARS}Y horizon automatically to the years shared by every selected instrument."
                    )

                if portfolio_results:
                    st.markdown("<div class='portfolio-results-grid'>", unsafe_allow_html=True)
                    result_cols = st.columns(min(3, max(1, len(portfolio_results))))
                    for idx, result in enumerate(portfolio_results):
                        sym = result["symbol"]
                        with result_cols[idx % len(result_cols)]:
                            if result.get("unavailable"):
                                st.markdown(
                                    f"<div class='portfolio-result-card'><span>{escape(sym)} • {result['weight']:.1f}%</span>"
                                    f"<b>${result['allocated']:,.2f} allocated</b><small>Selected-period return unavailable</small></div>",
                                    unsafe_allow_html=True,
                                )
                            else:
                                profit = float(result["profit"])
                                klass = "pos" if profit > 0 else ("neg" if profit < 0 else "flat")
                                st.markdown(
                                    f"<div class='portfolio-result-card'><span>{escape(sym)} • {result['weight']:.1f}% • {escape(str(portfolio_period or 'YTD'))}" + (f" request • {int(result.get('effective_years') or 0)}Y effective" if str(portfolio_period or 'YTD') != 'YTD' else '') + "</span>"
                                    f"<b>${result['ending_value']:,.2f}</b>"
                                    f"<small>${result['allocated']:,.2f} start • <span class='{klass}'>Profit {profit:+,.2f} ({result['return_pct']:+.2f}%)</span></small></div>",
                                    unsafe_allow_html=True,
                                )
                    st.markdown("</div>", unsafe_allow_html=True)

                # v5.9.78 - keep the annual strategy tab row visible inside Build Simulation
                # even when Yearly Withdrawal is disabled or its calculation is not yet available.
                annual_withdrawal_tabs_rendered = False

                # v5.9.38 - annual withdrawals are now modeled under both portfolio-maintenance
                # strategies so the user can compare annual rebalancing against natural weight drift.
                if portfolio_withdrawals_enabled and portfolio_annual_withdrawal > 0 and unresolved_amount <= 0.005:
                    withdrawal_args = (
                        market,
                        list(selected_portfolio_symbols),
                        dict(portfolio_weights),
                        float(portfolio_total),
                        str(portfolio_period or "YTD"),
                        bool(portfolio_include_ytd),
                        float(portfolio_annual_withdrawal),
                        effective_portfolio_years,
                    )
                    portfolio_withdrawal_not_rebalanced_result = _portfolio_annual_withdrawal_schedule(
                        *withdrawal_args,
                        rebalance_after_withdrawal=False,
                    )
                    portfolio_withdrawal_rebalanced_result = _portfolio_annual_withdrawal_schedule(
                        *withdrawal_args,
                        rebalance_after_withdrawal=True,
                    )
                    # Preserve the legacy field as the not-rebalanced path for saved-record backward compatibility.
                    portfolio_withdrawal_result = portfolio_withdrawal_not_rebalanced_result
                    unavailable = [
                        r for r in (portfolio_withdrawal_rebalanced_result, portfolio_withdrawal_not_rebalanced_result)
                        if r.get("unavailable")
                    ]
                    if unavailable:
                        st.warning(f"Annual withdrawal schedule unavailable: {unavailable[0].get('reason', 'required actual monthly return data is unavailable')} ")
                    else:
                        st.markdown("<div class='portfolio-analytics-title'>ANNUAL WITHDRAWAL — REBALANCED VS NOT REBALANCED</div>", unsafe_allow_html=True)
                        st.caption(
                            "Both paths apply each holding's actual saved return first and then take the requested annual withdrawal proportionally. "
                            "Rebalanced resets the remaining portfolio to the original target allocation after each completed-year withdrawal; Not rebalanced lets weights drift."
                        )
                        rb_end = float(portfolio_withdrawal_rebalanced_result.get("ending_balance") or 0)
                        nr_end = float(portfolio_withdrawal_not_rebalanced_result.get("ending_balance") or 0)
                        rb_positive, rb_years = _annual_withdrawal_positive_year_counts(
                            portfolio_withdrawal_rebalanced_result
                        )
                        nr_positive, nr_years = _annual_withdrawal_positive_year_counts(
                            portfolio_withdrawal_not_rebalanced_result
                        )
                        st.markdown(
                            _annual_withdrawal_kpi_grid(
                                float(portfolio_annual_withdrawal),
                                rb_end,
                                nr_end,
                                rb_positive,
                                rb_years,
                                nr_positive,
                                nr_years,
                            ),
                            unsafe_allow_html=True,
                        )

                        def _withdrawal_table_rows(result: dict) -> list[dict]:
                            rows = []
                            for row in result.get("schedule") or []:
                                rows.append({
                                    "Year": row.get("year"),
                                    "Starting Balance": f"${float(row.get('starting_balance') or 0):,.2f}",
                                    "Annual Return": f"{float(row.get('portfolio_return_pct') or 0):+.2f}%",
                                    "Gain / Loss": f"${float(row.get('gain_loss') or 0):+,.2f}",
                                    "Before Withdrawal": f"${float(row.get('balance_before_withdrawal') or 0):,.2f}",
                                    "Withdrawal": f"${float(row.get('withdrawal') or 0):,.2f}",
                                    "Remaining After Withdrawal": f"${float(row.get('ending_balance') or 0):,.2f}",
                                })
                            return rows

                        rb_tab, nr_tab, compare_tab, reset_tab, start_year_rb_tab, start_year_nr_tab = st.tabs([
                            "↻ Rebalanced annually",
                            "↝ Not rebalanced",
                            "⚖ Side-by-side",
                            "📅 Annual Reset",
                            "📈 Start-Year Rebalanced",
                            "📉 Start-Year Not Rebalanced",
                        ])
                        annual_withdrawal_tabs_rendered = True
                        with rb_tab:
                            st.caption("After each completed-year withdrawal, the remaining balance is restored to the original target weights.")
                            rb_rows = _withdrawal_table_rows(portfolio_withdrawal_rebalanced_result)
                            if rb_rows:
                                st.dataframe(pd.DataFrame(rb_rows), use_container_width=True, hide_index=True, height=min(560, 56 + 36 * len(rb_rows)))
                        with nr_tab:
                            st.caption("After each withdrawal, holdings keep their post-return weights; no annual rebalance is performed.")
                            nr_rows = _withdrawal_table_rows(portfolio_withdrawal_not_rebalanced_result)
                            if nr_rows:
                                st.dataframe(pd.DataFrame(nr_rows), use_container_width=True, hide_index=True, height=min(560, 56 + 36 * len(nr_rows)))
                        with compare_tab:
                            rb_schedule = list(portfolio_withdrawal_rebalanced_result.get("schedule") or [])
                            nr_schedule = list(portfolio_withdrawal_not_rebalanced_result.get("schedule") or [])
                            compare_rows = []
                            for i in range(max(len(rb_schedule), len(nr_schedule))):
                                rb = rb_schedule[i] if i < len(rb_schedule) else {}
                                nr = nr_schedule[i] if i < len(nr_schedule) else {}
                                rb_remaining = float(rb.get("ending_balance") or 0)
                                nr_remaining = float(nr.get("ending_balance") or 0)
                                compare_rows.append({
                                    "Year": rb.get("year") or nr.get("year"),
                                    "Rebalanced Return": f"{float(rb.get('portfolio_return_pct') or 0):+.2f}%",
                                    "Rebalanced Remaining": f"${rb_remaining:,.2f}",
                                    "Not Rebalanced Return": f"{float(nr.get('portfolio_return_pct') or 0):+.2f}%",
                                    "Not Rebalanced Remaining": f"${nr_remaining:,.2f}",
                                    "Difference": f"${(rb_remaining - nr_remaining):+,.2f}",
                                })
                            if compare_rows:
                                st.dataframe(pd.DataFrame(compare_rows), use_container_width=True, hide_index=True, height=min(560, 56 + 36 * len(compare_rows)))

                        with reset_tab:
                            st.caption(
                                "Independent annual reset test using the same current starting investment, target allocation, "
                                "and annual withdrawal. Every row starts fresh; no ending balance or profit/loss rolls into the next year."
                            )
                            annual_reset_df = _portfolio_annual_reset_dataframe(
                                market,
                                list(selected_portfolio_symbols),
                                dict(portfolio_weights),
                                float(portfolio_total),
                                float(portfolio_annual_withdrawal),
                                list(effective_portfolio_years),
                            )

                            if annual_reset_df.empty:
                                st.warning(
                                    "No completed year in the current simulation window has valid annual-return data for every selected instrument. "
                                    "Annual Reset never fills or invents a missing stock/ETF return."
                                )
                            else:
                                reset_year_count = len(annual_reset_df)
                                positive_year_count = int((annual_reset_df["Annual Return (%)"] > 0).sum())
                                funded_year_count = int((annual_reset_df["Withdrawal Status"] == "Funded").sum())
                                best_idx = annual_reset_df["Annual Return (%)"].idxmax()
                                worst_idx = annual_reset_df["Annual Return (%)"].idxmin()
                                best_year = int(annual_reset_df.loc[best_idx, "Year"])
                                best_return = float(annual_reset_df.loc[best_idx, "Annual Return (%)"])
                                worst_year = int(annual_reset_df.loc[worst_idx, "Year"])
                                worst_return = float(annual_reset_df.loc[worst_idx, "Annual Return (%)"])

                                reset_kpis = st.columns(6)
                                reset_kpis[0].metric("Reset start each year", f"${float(portfolio_total):,.2f}")
                                reset_kpis[1].metric("Annual withdrawal", f"${float(portfolio_annual_withdrawal):,.2f}")
                                reset_kpis[2].metric("Eligible years", f"{reset_year_count}")
                                reset_kpis[3].metric("Positive years", f"{positive_year_count}/{reset_year_count}")
                                reset_kpis[4].metric("Withdrawal funded", f"{funded_year_count}/{reset_year_count}")
                                reset_kpis[5].metric("Best / Worst", f"{best_return:+.2f}% / {worst_return:+.2f}%")

                                allocation_text = " • ".join(
                                    f"{sym} {float(portfolio_weights.get(sym, 0.0)):.2f}%"
                                    for sym in selected_portfolio_symbols
                                )
                                st.caption(
                                    f"Allocation reset every year: {allocation_text}. Best year: {best_year} ({best_return:+.2f}%). "
                                    f"Worst year: {worst_year} ({worst_return:+.2f}%). "
                                    "Withdrawal occurs after that year's return. A partial/failed withdrawal in one row does not affect any later row."
                                )

                                reset_column_config = {
                                    "Year": st.column_config.NumberColumn("Year", format="%d"),
                                    "Starting Balance ($)": st.column_config.NumberColumn("Starting Balance", format="$%.2f"),
                                    "Annual Return (%)": st.column_config.NumberColumn("Annual Return", format="%+.2f%%"),
                                    "Gain / Loss ($)": st.column_config.NumberColumn("Gain / Loss", format="$%+.2f"),
                                    "Before Withdrawal ($)": st.column_config.NumberColumn("Before Withdrawal", format="$%.2f"),
                                    "Withdrawal ($)": st.column_config.NumberColumn("Withdrawal", format="$%.2f"),
                                    "Remaining After Withdrawal ($)": st.column_config.NumberColumn("Remaining After Withdrawal", format="$%.2f"),
                                    "Withdrawal Status": st.column_config.TextColumn("Withdrawal Status"),
                                }
                                for _sym in selected_portfolio_symbols:
                                    reset_column_config[f"{_sym} Return (%)"] = st.column_config.NumberColumn(
                                        f"{_sym} Return",
                                        format="%+.2f%%",
                                    )

                                st.dataframe(
                                    annual_reset_df,
                                    use_container_width=True,
                                    hide_index=True,
                                    height=min(660, 56 + 36 * len(annual_reset_df)),
                                    column_config=reset_column_config,
                                    key="portfolio_annual_reset_performance_table",
                                )

                        start_year_rb_paths_df = _portfolio_start_year_paths_dataframe(
                            market,
                            list(selected_portfolio_symbols),
                            dict(portfolio_weights),
                            float(portfolio_total),
                            float(portfolio_annual_withdrawal),
                            list(effective_portfolio_years),
                            True,
                        )
                        start_year_nr_paths_df = _portfolio_start_year_paths_dataframe(
                            market,
                            list(selected_portfolio_symbols),
                            dict(portfolio_weights),
                            float(portfolio_total),
                            float(portfolio_annual_withdrawal),
                            list(effective_portfolio_years),
                            False,
                        )
                        start_year_rb_depletion = _start_year_depletion_summary(start_year_rb_paths_df)
                        start_year_nr_depletion = _start_year_depletion_summary(start_year_nr_paths_df)

                        def _render_start_year_depletion_dashboard() -> None:
                            """Two wide cards containing every annual cohort outcome."""
                            st.markdown(
                                "<div style='font-size:.72rem;font-weight:800;letter-spacing:.06em;margin:.7rem 0 .25rem 0;'>"
                                "ACCOUNT DEPLETION · ROLLING START-YEAR COHORTS</div>",
                                unsafe_allow_html=True,
                            )
                            dep_rb_col, dep_nr_col = st.columns(2)
                            for _col, _label, _summary in (
                                (dep_rb_col, "RB first depletion year", start_year_rb_depletion),
                                (dep_nr_col, "NR first depletion year", start_year_nr_depletion),
                            ):
                                _col.markdown(
                                    _annual_depletion_card_html(_label, _summary),
                                    unsafe_allow_html=True,
                                )

                        def _render_start_year_paths_tab(
                            *,
                            paths_df: pd.DataFrame,
                            table_key: str,
                            title: str,
                            caption: str,
                        ) -> None:
                            st.caption(caption)

                            if paths_df.empty:
                                st.warning(
                                    f"No {title.lower()} start-year paths can be calculated for the current portfolio/window. "
                                    "Every included year must have a valid annual return for every selected instrument."
                                )
                                return

                            cohort_count = int(paths_df["Start Year"].nunique())
                            earliest_start = int(paths_df["Start Year"].min())
                            latest_start = int(paths_df["Start Year"].max())
                            total_rows = len(paths_df)

                            sp1, sp2, sp3, sp4, sp5 = st.columns(5)
                            sp1.metric("Initial investment", f"${float(portfolio_total):,.2f}")
                            sp2.metric("Annual withdrawal", f"${float(portfolio_annual_withdrawal):,.2f}")
                            sp3.metric("Start-year cohorts", f"{cohort_count}")
                            sp4.metric("Earliest / Latest", f"{earliest_start} / {latest_start}")
                            sp5.metric("Path rows", f"{total_rows:,}")

                            _render_start_year_depletion_dashboard()

                            st.caption(
                                "Profit ($) and Profit (%) are cumulative versus the original investment and include cash already withdrawn: "
                                "Remaining After Withdrawal + Cumulative Withdrawn − Initial Investment. "
                                "Depletion year is the earliest calendar year where any rolling cohort reaches a $0 remaining balance."
                            )

                            start_year_column_config = {
                                "Start Year": st.column_config.NumberColumn("Start Year", format="%d"),
                                "Year": st.column_config.NumberColumn("Year", format="%d"),
                                "Year #": st.column_config.NumberColumn("Year #", format="%d"),
                                "Starting Balance ($)": st.column_config.NumberColumn("Starting Balance", format="$%.2f"),
                                "Annual Return (%)": st.column_config.NumberColumn("Annual Return", format="%+.2f%%"),
                                "Year Gain / Loss ($)": st.column_config.NumberColumn("Year Gain / Loss", format="$%+.2f"),
                                "Before Withdrawal ($)": st.column_config.NumberColumn("Before Withdrawal", format="$%.2f"),
                                "Withdrawal ($)": st.column_config.NumberColumn("Withdrawal", format="$%.2f"),
                                "Remaining After Withdrawal ($)": st.column_config.NumberColumn("Remaining After Withdrawal", format="$%.2f"),
                                "Cumulative Withdrawn ($)": st.column_config.NumberColumn("Cumulative Withdrawn", format="$%.2f"),
                                "Profit ($)": st.column_config.NumberColumn("Profit", format="$%+.2f"),
                                "Profit (%)": st.column_config.NumberColumn("Profit %", format="%+.2f%%"),
                                "Withdrawal Status": st.column_config.TextColumn("Withdrawal Status"),
                            }

                            st.dataframe(
                                paths_df,
                                use_container_width=True,
                                hide_index=True,
                                height=min(760, 70 + 34 * len(paths_df)),
                                column_config=start_year_column_config,
                                key=table_key,
                            )

                        with start_year_rb_tab:
                            _render_start_year_paths_tab(
                                paths_df=start_year_rb_paths_df,
                                table_key="portfolio_start_year_rebalanced_table",
                                title="Rebalanced",
                                caption=(
                                    "Each Start Year begins with the same original investment. After every yearly return and withdrawal, "
                                    "the remaining portfolio is restored to the original target weights before the next year. "
                                    "The remaining balance still carries forward; only the weights are rebalanced."
                                ),
                            )

                        with start_year_nr_tab:
                            _render_start_year_paths_tab(
                                paths_df=start_year_nr_paths_df,
                                table_key="portfolio_start_year_not_rebalanced_table",
                                title="Not-Rebalanced",
                                caption=(
                                    "Each Start Year begins with the same original investment. After every yearly return and withdrawal, "
                                    "the remaining balance carries forward and the holdings keep their drifted weights. "
                                    "No annual rebalance is performed."
                                ),
                            )

                        for label, result in (("Rebalanced", portfolio_withdrawal_rebalanced_result), ("Not rebalanced", portfolio_withdrawal_not_rebalanced_result)):
                            if result.get("depleted_year"):
                                st.error(f"{label} portfolio is depleted during {result.get('depleted_year')} under this withdrawal amount; later withdrawals cannot be funded.")

                if not annual_withdrawal_tabs_rendered:
                    # The tab row is structural UI and must never disappear. Calculations populate
                    # once Yearly Withdrawal is active and all required portfolio data is available.
                    rb_tab, nr_tab, compare_tab, reset_tab, start_year_rb_tab, start_year_nr_tab = st.tabs([
                        "↻ Rebalanced annually",
                        "↝ Not rebalanced",
                        "⚖ Side-by-side",
                        "📅 Annual Reset",
                        "📈 Start-Year Rebalanced",
                        "📉 Start-Year Not Rebalanced",
                    ])

                    if not portfolio_withdrawals_enabled:
                        _annual_tab_message = (
                            "Enable **Yearly withdrawal** above to populate the annual withdrawal calculations. "
                            "The tabs remain visible so the Build Simulation layout never changes."
                        )
                    elif float(portfolio_annual_withdrawal or 0.0) <= 0:
                        _annual_tab_message = (
                            "Enter a **Withdrawal / year ($)** amount greater than $0 to populate these annual tables."
                        )
                    elif unresolved_amount > 0.005:
                        _annual_tab_message = (
                            "Complete the portfolio allocation/return inputs before the annual withdrawal tables can be calculated."
                        )
                    else:
                        _unavailable_reason = (
                            portfolio_withdrawal_rebalanced_result.get("reason")
                            or portfolio_withdrawal_not_rebalanced_result.get("reason")
                            or "Required annual return data is unavailable for the selected portfolio/window."
                        )
                        _annual_tab_message = f"Annual withdrawal calculation is currently unavailable: {_unavailable_reason}"

                    with rb_tab:
                        st.caption("After each completed-year withdrawal, the remaining balance is restored to the original target weights.")
                        st.info(_annual_tab_message)
                    with nr_tab:
                        st.caption("After each withdrawal, holdings keep their post-return weights; no annual rebalance is performed.")
                        st.info(_annual_tab_message)
                    with compare_tab:
                        st.caption("Compares the annual Rebalanced and Not-Rebalanced withdrawal paths year by year.")
                        st.info(_annual_tab_message)
                    with reset_tab:
                        st.caption(
                            "Independent annual reset test: every eligible year restarts from the same original investment "
                            "and target allocation, then applies that year's return and the selected annual withdrawal."
                        )
                        if not portfolio_withdrawals_enabled:
                            st.info(
                                "Enable **Yearly withdrawal** above to apply the **Withdrawal / year ($)** amount "
                                "to each independent Annual Reset row."
                            )
                        else:
                            st.info(_annual_tab_message)

                    with start_year_rb_tab:
                        st.caption(
                            "Rolling Rebalanced start-year analysis: each possible Start Year begins with the same initial investment; "
                            "remaining balance carries forward while target weights are restored after every yearly withdrawal."
                        )
                        if not portfolio_withdrawals_enabled:
                            st.info(
                                "Enable **Yearly withdrawal** above to calculate Start-Year Rebalanced paths with the selected annual withdrawal."
                            )
                        else:
                            st.info(_annual_tab_message)

                    with start_year_nr_tab:
                        st.caption(
                            "Rolling Not-Rebalanced start-year analysis: each possible Start Year begins with the same initial investment; "
                            "remaining balance and drifted holding weights carry forward after every yearly withdrawal."
                        )
                        if not portfolio_withdrawals_enabled:
                            st.info(
                                "Enable **Yearly withdrawal** above to calculate Start-Year Not-Rebalanced paths with the selected annual withdrawal."
                            )
                        else:
                            st.info(_annual_tab_message)

                # v5.9.82 - keep the complete monthly strategy tab row visible and
                # apply the annual Reset/Start-Year requirements at monthly granularity.
                monthly_withdrawal_tabs_rendered = False

                # Monthly withdrawal mode uses actual adjusted month-to-month returns
                # from durable monthly history, with an on-demand Yahoo daily-history fallback.
                if portfolio_monthly_withdrawals_enabled and portfolio_monthly_withdrawal > 0 and unresolved_amount <= 0.005:
                    actual_monthly_payload = cached_actual_monthly_returns(
                        tuple(str(s).upper() for s in selected_portfolio_symbols),
                        tuple(str(y) for y in effective_portfolio_years),
                    )
                    if actual_monthly_payload.get("unavailable"):
                        portfolio_monthly_withdrawal_not_rebalanced_result = {
                            "unavailable": True,
                            "reason": actual_monthly_payload.get("reason") or "Actual monthly return history is unavailable.",
                        }
                        portfolio_monthly_withdrawal_rebalanced_result = dict(portfolio_monthly_withdrawal_not_rebalanced_result)
                    else:
                        monthly_withdrawal_args = (
                            market,
                            list(selected_portfolio_symbols),
                            dict(portfolio_weights),
                            float(portfolio_total),
                            str(portfolio_period or "YTD"),
                            float(portfolio_monthly_withdrawal),
                            effective_portfolio_years,
                        )
                        portfolio_monthly_withdrawal_not_rebalanced_result = _portfolio_monthly_withdrawal_schedule(
                            *monthly_withdrawal_args,
                            rebalance_after_withdrawal=False,
                            actual_monthly_returns=actual_monthly_payload.get("returns") or {},
                        )
                        portfolio_monthly_withdrawal_rebalanced_result = _portfolio_monthly_withdrawal_schedule(
                            *monthly_withdrawal_args,
                            rebalance_after_withdrawal=True,
                            actual_monthly_returns=actual_monthly_payload.get("returns") or {},
                        )
                    portfolio_monthly_withdrawal_result = portfolio_monthly_withdrawal_not_rebalanced_result
                    unavailable = [
                        r for r in (portfolio_monthly_withdrawal_rebalanced_result, portfolio_monthly_withdrawal_not_rebalanced_result)
                        if r.get("unavailable")
                    ]
                    if unavailable:
                        st.warning(f"Monthly withdrawal schedule unavailable: {unavailable[0].get('reason', 'required actual monthly return data is unavailable')}")
                    else:
                        st.markdown("<div class='portfolio-analytics-title'>MONTHLY WITHDRAWAL — REBALANCED VS NOT REBALANCED</div>", unsafe_allow_html=True)
                        st.caption(
                            "Each row uses the actual adjusted return from one historical month to the next, sourced from the same daily history as Market Table. "
                            "The monthly path is reconciled to each displayed annual return. Rebalanced restores target weights after every monthly withdrawal; Not rebalanced lets holdings drift."
                        )
                        rb_end = float(portfolio_monthly_withdrawal_rebalanced_result.get("ending_balance") or 0)
                        nr_end = float(portfolio_monthly_withdrawal_not_rebalanced_result.get("ending_balance") or 0)
                        rb_positive = int(portfolio_monthly_withdrawal_rebalanced_result.get("positive_months") or 0)
                        nr_positive = int(portfolio_monthly_withdrawal_not_rebalanced_result.get("positive_months") or 0)
                        rb_months = int(portfolio_monthly_withdrawal_rebalanced_result.get("months_modeled") or 0)
                        nr_months = int(portfolio_monthly_withdrawal_not_rebalanced_result.get("months_modeled") or 0)
                        st.markdown(
                            _monthly_withdrawal_kpi_grid(
                                float(portfolio_monthly_withdrawal),
                                rb_end,
                                nr_end,
                                rb_positive,
                                rb_months,
                                nr_positive,
                                nr_months,
                            ),
                            unsafe_allow_html=True,
                        )

                        monthly_return_data = actual_monthly_payload.get("returns") or {}
                        monthly_reset_df = _portfolio_monthly_reset_dataframe(
                            list(selected_portfolio_symbols),
                            dict(portfolio_weights),
                            float(portfolio_total),
                            float(portfolio_monthly_withdrawal),
                            list(effective_portfolio_years),
                            monthly_return_data,
                        )
                        monthly_start_year_rb_paths_df = _portfolio_monthly_start_year_paths_dataframe(
                            market,
                            list(selected_portfolio_symbols),
                            dict(portfolio_weights),
                            float(portfolio_total),
                            float(portfolio_monthly_withdrawal),
                            list(effective_portfolio_years),
                            True,
                            monthly_return_data,
                        )
                        monthly_start_year_nr_paths_df = _portfolio_monthly_start_year_paths_dataframe(
                            market,
                            list(selected_portfolio_symbols),
                            dict(portfolio_weights),
                            float(portfolio_total),
                            float(portfolio_monthly_withdrawal),
                            list(effective_portfolio_years),
                            False,
                            monthly_return_data,
                        )
                        monthly_start_year_rb_depletion = _monthly_start_year_depletion_summary(
                            monthly_start_year_rb_paths_df
                        )
                        monthly_start_year_nr_depletion = _monthly_start_year_depletion_summary(
                            monthly_start_year_nr_paths_df
                        )

                        def _monthly_withdrawal_table_rows(result: dict) -> list[dict]:
                            rows = []
                            for row in result.get("schedule") or []:
                                rows.append({
                                    "Month": row.get("period"),
                                    "Starting Balance": f"${float(row.get('starting_balance') or 0):,.2f}",
                                    "Monthly Return": f"{float(row.get('portfolio_return_pct') or 0):+.3f}%",
                                    "Gain / Loss": f"${float(row.get('gain_loss') or 0):+,.2f}",
                                    "Before Withdrawal": f"${float(row.get('balance_before_withdrawal') or 0):,.2f}",
                                    "Withdrawal": f"${float(row.get('withdrawal') or 0):,.2f}",
                                    "Remaining": f"${float(row.get('ending_balance') or 0):,.2f}",
                                })
                            return rows

                        mrb_tab, mnr_tab, mcompare_tab, mreset_tab, mstart_year_rb_tab, mstart_year_nr_tab = st.tabs([
                            "↻ Rebalanced monthly",
                            "↝ Not rebalanced monthly",
                            "⚖ Monthly side-by-side",
                            "📅 Monthly Reset",
                            "📈 Monthly Start-Year Rebalanced",
                            "📉 Monthly Start-Year Not Rebalanced",
                        ])
                        monthly_withdrawal_tabs_rendered = True
                        with mrb_tab:
                            st.caption("After every month-end withdrawal, the remaining balance is restored to the original target weights.")
                            rows = _monthly_withdrawal_table_rows(portfolio_monthly_withdrawal_rebalanced_result)
                            if rows:
                                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=560)
                        with mnr_tab:
                            st.caption("After every month-end withdrawal, holdings retain their drifted post-return weights.")
                            rows = _monthly_withdrawal_table_rows(portfolio_monthly_withdrawal_not_rebalanced_result)
                            if rows:
                                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=560)
                        with mcompare_tab:
                            rb_schedule = list(portfolio_monthly_withdrawal_rebalanced_result.get("schedule") or [])
                            nr_schedule = list(portfolio_monthly_withdrawal_not_rebalanced_result.get("schedule") or [])
                            compare_rows = []
                            for i in range(max(len(rb_schedule), len(nr_schedule))):
                                rb = rb_schedule[i] if i < len(rb_schedule) else {}
                                nr = nr_schedule[i] if i < len(nr_schedule) else {}
                                rb_remaining = float(rb.get("ending_balance") or 0)
                                nr_remaining = float(nr.get("ending_balance") or 0)
                                compare_rows.append({
                                    "Month": rb.get("period") or nr.get("period"),
                                    "Rebalanced Return": f"{float(rb.get('portfolio_return_pct') or 0):+.3f}%",
                                    "Rebalanced Remaining": f"${rb_remaining:,.2f}",
                                    "Not Rebalanced Return": f"{float(nr.get('portfolio_return_pct') or 0):+.3f}%",
                                    "Not Rebalanced Remaining": f"${nr_remaining:,.2f}",
                                    "Difference": f"${(rb_remaining - nr_remaining):+,.2f}",
                                })
                            if compare_rows:
                                st.dataframe(pd.DataFrame(compare_rows), use_container_width=True, hide_index=True, height=560)

                        with mreset_tab:
                            st.caption(
                                "Independent monthly reset test: every historical month restarts with the same original investment and target allocation, "
                                "applies that month's actual returns, and takes one monthly withdrawal. Nothing carries into the next reset row."
                            )
                            if monthly_reset_df.empty:
                                st.warning(
                                    "No monthly reset rows can be calculated because valid actual monthly returns are required for every selected instrument."
                                )
                            else:
                                mr1, mr2, mr3, mr4, mr5 = st.columns(5)
                                mr1.metric("Initial investment", f"${float(portfolio_total):,.2f}")
                                mr2.metric("Monthly withdrawal", f"${float(portfolio_monthly_withdrawal):,.2f}")
                                mr3.metric("Reset months", f"{len(monthly_reset_df):,}")
                                mr4.metric(
                                    "Positive months",
                                    f"{int((monthly_reset_df['Monthly Return (%)'] > 0).sum())}/{len(monthly_reset_df)}",
                                )
                                mr5.metric(
                                    "Funded months",
                                    f"{int((monthly_reset_df['Withdrawal Status'] == 'Funded').sum())}/{len(monthly_reset_df)}",
                                )
                                monthly_reset_column_config = {
                                    "Month": st.column_config.TextColumn("Month"),
                                    "Starting Balance ($)": st.column_config.NumberColumn("Starting Balance", format="$%.2f"),
                                    "Monthly Return (%)": st.column_config.NumberColumn("Monthly Return", format="%+.3f%%"),
                                    "Month Gain / Loss ($)": st.column_config.NumberColumn("Month Gain / Loss", format="$%+.2f"),
                                    "Before Withdrawal ($)": st.column_config.NumberColumn("Before Withdrawal", format="$%.2f"),
                                    "Withdrawal ($)": st.column_config.NumberColumn("Withdrawal", format="$%.2f"),
                                    "Remaining After Withdrawal ($)": st.column_config.NumberColumn("Remaining After Withdrawal", format="$%.2f"),
                                    "Withdrawal Status": st.column_config.TextColumn("Withdrawal Status"),
                                }
                                for _sym in selected_portfolio_symbols:
                                    monthly_reset_column_config[f"{_sym} Return (%)"] = st.column_config.NumberColumn(
                                        f"{_sym} Return", format="%+.3f%%"
                                    )
                                st.dataframe(
                                    monthly_reset_df,
                                    use_container_width=True,
                                    hide_index=True,
                                    height=min(760, 70 + 34 * len(monthly_reset_df)),
                                    column_config=monthly_reset_column_config,
                                    key="portfolio_monthly_reset_table",
                                )

                        def _render_monthly_start_year_depletion_dashboard() -> None:
                            st.markdown(
                                "<div style='font-size:.72rem;font-weight:800;letter-spacing:.06em;margin:.7rem 0 .25rem 0;'>"
                                "ACCOUNT DEPLETION · MONTHLY ROLLING START-YEAR COHORTS</div>",
                                unsafe_allow_html=True,
                            )
                            dep_rb_col, dep_nr_col = st.columns(2)
                            for _col, _label, _summary in (
                                (dep_rb_col, "RB first depletion month", monthly_start_year_rb_depletion),
                                (dep_nr_col, "NR first depletion month", monthly_start_year_nr_depletion),
                            ):
                                _col.markdown(
                                    _monthly_depletion_card_html(_label, _summary),
                                    unsafe_allow_html=True,
                                )

                        def _render_monthly_start_year_paths_tab(
                            *, paths_df: pd.DataFrame, table_key: str, title: str, caption: str
                        ) -> None:
                            st.caption(caption)
                            if paths_df.empty:
                                st.warning(
                                    f"No {title.lower()} monthly start-year paths can be calculated for the current portfolio/window. "
                                    "Every included month must have an actual return for every selected instrument."
                                )
                                return
                            cohort_count = int(paths_df["Start Year"].nunique())
                            earliest_start = int(paths_df["Start Year"].min())
                            latest_start = int(paths_df["Start Year"].max())
                            sp1, sp2, sp3, sp4, sp5 = st.columns(5)
                            sp1.metric("Initial investment", f"${float(portfolio_total):,.2f}")
                            sp2.metric("Monthly withdrawal", f"${float(portfolio_monthly_withdrawal):,.2f}")
                            sp3.metric("Start-year cohorts", f"{cohort_count}")
                            sp4.metric("Earliest / Latest", f"{earliest_start} / {latest_start}")
                            sp5.metric("Path rows", f"{len(paths_df):,}")
                            _render_monthly_start_year_depletion_dashboard()
                            st.caption(
                                "Profit ($) and Profit (%) are cumulative versus the original investment and include cash already withdrawn: "
                                "Remaining After Withdrawal + Cumulative Withdrawn − Initial Investment. Remaining balance carries forward every month, including across year boundaries."
                            )
                            monthly_start_year_column_config = {
                                "Start Year": st.column_config.NumberColumn("Start Year", format="%d"),
                                "Month": st.column_config.TextColumn("Month"),
                                "Month #": st.column_config.NumberColumn("Month #", format="%d"),
                                "Year": st.column_config.NumberColumn("Year", format="%d"),
                                "Starting Balance ($)": st.column_config.NumberColumn("Starting Balance", format="$%.2f"),
                                "Monthly Return (%)": st.column_config.NumberColumn("Monthly Return", format="%+.3f%%"),
                                "Month Gain / Loss ($)": st.column_config.NumberColumn("Month Gain / Loss", format="$%+.2f"),
                                "Before Withdrawal ($)": st.column_config.NumberColumn("Before Withdrawal", format="$%.2f"),
                                "Withdrawal ($)": st.column_config.NumberColumn("Withdrawal", format="$%.2f"),
                                "Remaining After Withdrawal ($)": st.column_config.NumberColumn("Remaining After Withdrawal", format="$%.2f"),
                                "Cumulative Withdrawn ($)": st.column_config.NumberColumn("Cumulative Withdrawn", format="$%.2f"),
                                "Profit ($)": st.column_config.NumberColumn("Profit", format="$%+.2f"),
                                "Profit (%)": st.column_config.NumberColumn("Profit %", format="%+.2f%%"),
                                "Withdrawal Status": st.column_config.TextColumn("Withdrawal Status"),
                            }
                            st.dataframe(
                                paths_df,
                                use_container_width=True,
                                hide_index=True,
                                height=min(800, 70 + 34 * len(paths_df)),
                                column_config=monthly_start_year_column_config,
                                key=table_key,
                            )

                        with mstart_year_rb_tab:
                            _render_monthly_start_year_paths_tab(
                                paths_df=monthly_start_year_rb_paths_df,
                                table_key="portfolio_monthly_start_year_rebalanced_table",
                                title="Rebalanced",
                                caption=(
                                    "Each Start Year begins in January with the same original investment. Actual monthly returns and withdrawals carry forward continuously; "
                                    "after every monthly withdrawal, the remaining portfolio is restored to the original target weights."
                                ),
                            )

                        with mstart_year_nr_tab:
                            _render_monthly_start_year_paths_tab(
                                paths_df=monthly_start_year_nr_paths_df,
                                table_key="portfolio_monthly_start_year_not_rebalanced_table",
                                title="Not-Rebalanced",
                                caption=(
                                    "Each Start Year begins in January with the same original investment. Actual monthly returns, remaining balance, and drifted holding weights "
                                    "carry forward continuously with no monthly or annual rebalance."
                                ),
                            )

                        for label, result in (("Rebalanced", portfolio_monthly_withdrawal_rebalanced_result), ("Not rebalanced", portfolio_monthly_withdrawal_not_rebalanced_result)):
                            if result.get("depleted_period"):
                                st.error(f"{label} portfolio is depleted during {result.get('depleted_period')} under this monthly withdrawal amount.")

                if not monthly_withdrawal_tabs_rendered:
                    mrb_tab, mnr_tab, mcompare_tab, mreset_tab, mstart_year_rb_tab, mstart_year_nr_tab = st.tabs([
                        "↻ Rebalanced monthly",
                        "↝ Not rebalanced monthly",
                        "⚖ Monthly side-by-side",
                        "📅 Monthly Reset",
                        "📈 Monthly Start-Year Rebalanced",
                        "📉 Monthly Start-Year Not Rebalanced",
                    ])
                    if not portfolio_monthly_withdrawals_enabled:
                        _monthly_tab_message = (
                            "Enable **Monthly withdrawal** above to populate the monthly calculations. "
                            "These tabs remain visible so the Build Simulation layout stays consistent."
                        )
                    elif float(portfolio_monthly_withdrawal or 0.0) <= 0:
                        _monthly_tab_message = "Enter a **Withdrawal / month ($)** amount greater than $0 to populate these monthly tables."
                    elif unresolved_amount > 0.005:
                        _monthly_tab_message = "Complete the portfolio allocation/return inputs before the monthly withdrawal tables can be calculated."
                    else:
                        _monthly_reason = (
                            portfolio_monthly_withdrawal_rebalanced_result.get("reason")
                            or portfolio_monthly_withdrawal_not_rebalanced_result.get("reason")
                            or "Required actual monthly return data is unavailable for the selected portfolio/window."
                        )
                        _monthly_tab_message = f"Monthly withdrawal calculation is currently unavailable: {_monthly_reason}"

                    with mrb_tab:
                        st.caption("After each month-end withdrawal, remaining holdings are restored to the target weights.")
                        st.info(_monthly_tab_message)
                    with mnr_tab:
                        st.caption("After each month-end withdrawal, holdings keep their drifted weights.")
                        st.info(_monthly_tab_message)
                    with mcompare_tab:
                        st.caption("Compares the monthly Rebalanced and Not-Rebalanced paths month by month.")
                        st.info(_monthly_tab_message)
                    with mreset_tab:
                        st.caption("Each historical month independently restarts from the same original investment before one monthly withdrawal.")
                        st.info(_monthly_tab_message)
                    with mstart_year_rb_tab:
                        st.caption(
                            "Each Start Year begins with the same investment; monthly returns and withdrawals carry forward continuously while target weights are restored after each month."
                        )
                        st.info(_monthly_tab_message)
                    with mstart_year_nr_tab:
                        st.caption(
                            "Each Start Year begins with the same investment; monthly returns, balance, and drifted weights carry forward continuously without rebalancing."
                        )
                        st.info(_monthly_tab_message)

                # v5.9.6 - populate the portfolio analytics table immediately after the simulation runs.
                if portfolio_results:
                    portfolio_income_metrics = cached_income_metrics(tuple(str(s).upper() for s in selected_portfolio_symbols))
                    analytics_monthly_stats: dict[str, dict] = {}
                    analytics_years = tuple(str(y) for y in (effective_portfolio_years or [])[:10])
                    if analytics_years:
                        analytics_monthly_payload = cached_actual_monthly_returns(
                            tuple(str(s).upper() for s in selected_portfolio_symbols),
                            analytics_years,
                        )
                        if not analytics_monthly_payload.get("unavailable"):
                            for _sym, _month_map in (analytics_monthly_payload.get("returns") or {}).items():
                                _values = [float(v) for v in _month_map.values() if v is not None and np.isfinite(v)]
                                analytics_monthly_stats[str(_sym).upper()] = {
                                    "positive_months": sum(1 for v in _values if v > 0.0),
                                    "available_months": len(_values),
                                }
                    market_lookup_for_analytics = market.set_index(market["Symbol"].astype(str).str.upper(), drop=False)
                    portfolio_analytics = []
                    result_lookup = {str(item.get("symbol") or "").upper(): item for item in portfolio_results}
                    for sym in selected_portfolio_symbols:
                        if sym not in market_lookup_for_analytics.index:
                            continue
                        meta_row = market_lookup_for_analytics.loc[sym]
                        if isinstance(meta_row, pd.DataFrame):
                            meta_row = meta_row.iloc[0]
                        result = result_lookup.get(sym) or {
                            "symbol": sym,
                            "weight": portfolio_weights.get(sym, 0.0),
                            "allocated": float(portfolio_total) * float(portfolio_weights.get(sym, 0.0)) / 100.0,
                        }
                        portfolio_analytics.append(
                            _portfolio_analytics_payload(
                                meta_row,
                                result,
                                portfolio_income_metrics.get(sym, {}),
                                analytics_monthly_stats.get(str(sym).upper(), {}),
                            )
                        )

                    if portfolio_analytics:
                        st.markdown("<div class='portfolio-analytics-title'>PORTFOLIO INFORMATION & PERFORMANCE TABLE</div>", unsafe_allow_html=True)
                        st.caption(
                            "10-year CAGR is calculated from the 10 completed calendar-year returns when all 10 are available. "
                            "Positive months counts actual adjusted month-end returns above 0% within the active completed-year simulation window (up to the actual months available for the selected horizon). "
                            "Regular yield is a trailing Yahoo dividend/distribution yield estimate. Est. annual dividend = allocated dollars × regular yield; it is not a forecast."
                        )
                        portfolio_analytics_df = _portfolio_analytics_dataframe(portfolio_analytics)
                        st.dataframe(
                            portfolio_analytics_df,
                            use_container_width=True,
                            hide_index=True,
                            height=min(520, 62 + 42 * len(portfolio_analytics_df)),
                        )
        else:
            st.info("Select two or more instruments to simulate a split portfolio.")

    # Save / Manage portfolio simulations lives inside the dedicated Portfolio workspace.
    _saved_count_preview = len(cached_saved_simulations())
    with portfolio_manage_tab:
        st.caption(f"{_saved_count_preview} saved portfolio simulation(s) currently in the library.")
        saved_simulations = cached_saved_simulations()
        if st.session_state.simulation_library_message:
            _sim_ok, _sim_msg = st.session_state.simulation_library_message
            (st.success if _sim_ok else st.warning)(_sim_msg)
            st.session_state.simulation_library_message = None

        st.markdown("<div class='simulation-save-title'>SAVE / MANAGE PORTFOLIO SIMULATIONS</div>", unsafe_allow_html=True)

        # v5.9.78: repeat the active withdrawal outcome here so the income
        # assumptions/results remain visible at the exact point where the user
        # names, saves or manages the simulation.
        if (
            portfolio_withdrawals_enabled
            and float(portfolio_annual_withdrawal or 0.0) > 0
            and portfolio_withdrawal_rebalanced_result
            and portfolio_withdrawal_not_rebalanced_result
            and not portfolio_withdrawal_rebalanced_result.get("unavailable")
            and not portfolio_withdrawal_not_rebalanced_result.get("unavailable")
        ):
            _manage_rb_end = float(portfolio_withdrawal_rebalanced_result.get("ending_balance") or 0.0)
            _manage_nr_end = float(portfolio_withdrawal_not_rebalanced_result.get("ending_balance") or 0.0)
            _manage_rb_positive, _manage_rb_years = _annual_withdrawal_positive_year_counts(
                portfolio_withdrawal_rebalanced_result
            )
            _manage_nr_positive, _manage_nr_years = _annual_withdrawal_positive_year_counts(
                portfolio_withdrawal_not_rebalanced_result
            )
            st.markdown(
                "<div class='portfolio-analytics-title save-manage-withdrawal-title'>ACTIVE ANNUAL WITHDRAWAL SUMMARY</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                _annual_withdrawal_kpi_grid(
                    float(portfolio_annual_withdrawal),
                    _manage_rb_end,
                    _manage_nr_end,
                    _manage_rb_positive,
                    _manage_rb_years,
                    _manage_nr_positive,
                    _manage_nr_years,
                ),
                unsafe_allow_html=True,
            )
        elif (
            portfolio_monthly_withdrawals_enabled
            and float(portfolio_monthly_withdrawal or 0.0) > 0
            and portfolio_monthly_withdrawal_rebalanced_result
            and portfolio_monthly_withdrawal_not_rebalanced_result
            and not portfolio_monthly_withdrawal_rebalanced_result.get("unavailable")
            and not portfolio_monthly_withdrawal_not_rebalanced_result.get("unavailable")
        ):
            st.markdown(
                "<div class='portfolio-analytics-title save-manage-withdrawal-title'>ACTIVE MONTHLY WITHDRAWAL SUMMARY</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                _monthly_withdrawal_kpi_grid(
                    float(portfolio_monthly_withdrawal),
                    float(portfolio_monthly_withdrawal_rebalanced_result.get("ending_balance") or 0.0),
                    float(portfolio_monthly_withdrawal_not_rebalanced_result.get("ending_balance") or 0.0),
                    int(portfolio_monthly_withdrawal_rebalanced_result.get("positive_months") or 0),
                    int(portfolio_monthly_withdrawal_rebalanced_result.get("months_modeled") or 0),
                    int(portfolio_monthly_withdrawal_not_rebalanced_result.get("positive_months") or 0),
                    int(portfolio_monthly_withdrawal_not_rebalanced_result.get("months_modeled") or 0),
                ),
                unsafe_allow_html=True,
            )

        save_cols = st.columns([2.4, 1.3, 1.3, 2.1])
        with save_cols[0]:
            simulation_name = st.text_input(
                "Simulation name",
                value=f"Portfolio {now_et().strftime('%b %d %Y %I%M %p')}",
                key="portfolio_simulation_name",
                help="This name appears in the in-app Saved Simulations library and in the PDF file name.",
            )

        portfolio_save_ready = bool(
            selected_portfolio_symbols
            and allocation_valid
            and float(portfolio_total or 0) > 0
            and portfolio_results
            and calculated
            and len(calculated) == len(portfolio_results)
            and unresolved_amount <= 0.005
            and (
                (not portfolio_withdrawals_enabled and not portfolio_monthly_withdrawals_enabled)
                or (
                    portfolio_withdrawals_enabled
                    and float(portfolio_annual_withdrawal or 0) > 0
                    and portfolio_withdrawal_result
                    and not portfolio_withdrawal_result.get("unavailable")
                )
                or (
                    portfolio_monthly_withdrawals_enabled
                    and float(portfolio_monthly_withdrawal or 0) > 0
                    and portfolio_monthly_withdrawal_result
                    and not portfolio_monthly_withdrawal_result.get("unavailable")
                )
            )
        )

        with save_cols[1]:
            save_simulation_clicked = st.button(
                "💾 Save PDF to Library",
                key="save_portfolio_simulation_pdf",
                use_container_width=True,
                type="primary",
                disabled=not portfolio_save_ready,
                help="Save this completed simulation into the in-app PDF library.",
            )
        with save_cols[2]:
            if st.button(
                f"📚 Saved ({len(saved_simulations)})" if not st.session_state.simulation_library_open else "📚 Hide Library",
                key="toggle_simulation_library",
                use_container_width=True,
            ):
                st.session_state.simulation_library_open = not st.session_state.simulation_library_open
                st.rerun()
        with save_cols[3]:
            if portfolio_save_ready:
                st.caption("The saved PDF starts with combined portfolio performance and combined timeframe returns, then preserves the individual allocation and analytics detail.")
            else:
                st.caption("Complete a portfolio simulation with return data available for every selected instrument before saving the PDF.")

        if save_simulation_clicked and portfolio_save_ready:
            portfolio_market = _hydrate_price_targets(market, tuple(selected_portfolio_symbols))
            market_lookup = portfolio_market.set_index(portfolio_market["Symbol"].astype(str).str.upper(), drop=False)
            saved_instruments = []
            for result in portfolio_results:
                sym = str(result.get("symbol") or "").upper()
                meta_row = market_lookup.loc[sym] if sym in market_lookup.index else None
                if isinstance(meta_row, pd.DataFrame):
                    meta_row = meta_row.iloc[0]
                analytics = next((item for item in portfolio_analytics if str(item.get("stock") or "").upper() == sym), {})
                saved_instruments.append({
                    "symbol": sym,
                    "type": str(meta_row.get("Type") if meta_row is not None else ""),
                    "sector": str(meta_row.get("Sector") if meta_row is not None else ""),
                    "industry": str(analytics.get("industry") or (meta_row.get("Industry") if meta_row is not None else "")),
                    "name": str(meta_row.get("Name") if meta_row is not None else sym),
                    "analyst_rating": str(meta_row.get("Analyst Rating") if meta_row is not None else "Not Rated"),
                    "history_verification": str(meta_row.get("History Verification") if meta_row is not None else "Pending"),
                    "verification_coverage": str(meta_row.get("Verification Coverage") if meta_row is not None else ""),
                    "verification_exceptions": str(meta_row.get("Verification Exceptions") if meta_row is not None else ""),
                    "verification_source": str(meta_row.get("Verification Source") if meta_row is not None else ""),
                    "max_verification_diff_pp": (
                        float(pd.to_numeric(pd.Series([meta_row.get("Max Verification Diff (pp)")]), errors="coerce").iloc[0])
                        if meta_row is not None and pd.notna(pd.to_numeric(pd.Series([meta_row.get("Max Verification Diff (pp)")]), errors="coerce").iloc[0])
                        else None
                    ),
                    "current_price": (
                        float(meta_row.get("Price"))
                        if meta_row is not None and pd.notna(pd.to_numeric(pd.Series([meta_row.get("Price")]), errors="coerce").iloc[0])
                        else None
                    ),
                    "price_target_low": (
                        float(meta_row.get("Price Target Low"))
                        if meta_row is not None and pd.notna(pd.to_numeric(pd.Series([meta_row.get("Price Target Low")]), errors="coerce").iloc[0])
                        else None
                    ),
                    "price_target_average": (
                        float(meta_row.get("Price Target Average"))
                        if meta_row is not None and pd.notna(pd.to_numeric(pd.Series([meta_row.get("Price Target Average")]), errors="coerce").iloc[0])
                        else None
                    ),
                    "price_target_high": (
                        float(meta_row.get("Price Target High"))
                        if meta_row is not None and pd.notna(pd.to_numeric(pd.Series([meta_row.get("Price Target High")]), errors="coerce").iloc[0])
                        else None
                    ),
                    "weight": float(result.get("weight") or 0),
                    "allocated": float(result.get("allocated") or 0),
                    "ending_value": float(result.get("ending_value") or 0),
                    "profit": float(result.get("profit") or 0),
                    "return_pct": float(result.get("return_pct") or 0),
                    "unavailable": bool(result.get("unavailable")),
                    "cagr_10y_pct": analytics.get("cagr_10y_pct"),
                    "positive_years": int(analytics.get("positive_years") or 0),
                    "available_years": int(analytics.get("available_years") or 0),
                    "positive_months": (int(analytics.get("positive_months")) if analytics.get("positive_months") is not None else None),
                    "available_months": (int(analytics.get("available_months")) if analytics.get("available_months") is not None else None),
                    "worst_year": analytics.get("worst_year"),
                    "worst_year_pct": analytics.get("worst_year_pct"),
                    "best_year": analytics.get("best_year"),
                    "best_year_pct": analytics.get("best_year_pct"),
                    "regular_yield_pct": analytics.get("regular_yield_pct"),
                    "est_annual_dividend": analytics.get("est_annual_dividend"),
                    "yield_source": analytics.get("yield_source"),
                    "performance": analytics.get("performance") or {},
                })

            created = now_et()
            record = {
                "id": simulation_id(),
                "name": str(simulation_name or "Portfolio Simulation").strip() or "Portfolio Simulation",
                "created_at_et": created.isoformat(),
                "created_at_display_et": format_et(created),
                "created_date": created.date().isoformat(),
                "period": str(portfolio_period or "YTD"),
                "include_current_ytd": bool(portfolio_include_ytd),
                "allocation_mode": str(portfolio_allocation_mode or "Equal split"),
                "total_invested": float(portfolio_total),
                "ending_value": float(total_ending),
                "profit_loss": float(total_profit),
                "total_return": float(total_return),
                "instrument_count": len(saved_instruments),
                "instruments": saved_instruments,
                "effective_calendar_years": list(effective_portfolio_years or []),
                "monthly_positive_months_rebalanced": int(portfolio_monthly_withdrawal_rebalanced_result.get("positive_months") or 0) if portfolio_monthly_withdrawals_enabled else None,
                "monthly_positive_months_not_rebalanced": int(portfolio_monthly_withdrawal_not_rebalanced_result.get("positive_months") or 0) if portfolio_monthly_withdrawals_enabled else None,
                "monthly_months_modeled_rebalanced": int(portfolio_monthly_withdrawal_rebalanced_result.get("months_modeled") or 0) if portfolio_monthly_withdrawals_enabled else None,
                "monthly_months_modeled_not_rebalanced": int(portfolio_monthly_withdrawal_not_rebalanced_result.get("months_modeled") or 0) if portfolio_monthly_withdrawals_enabled else None,
                "annual_withdrawals_enabled": bool(portfolio_withdrawals_enabled),
                "annual_withdrawal_amount": float(portfolio_annual_withdrawal or 0) if portfolio_withdrawals_enabled else 0.0,
                "annual_positive_years_rebalanced": (
                    _annual_withdrawal_positive_year_counts(portfolio_withdrawal_rebalanced_result)[0]
                    if portfolio_withdrawals_enabled else None
                ),
                "annual_positive_years_not_rebalanced": (
                    _annual_withdrawal_positive_year_counts(portfolio_withdrawal_not_rebalanced_result)[0]
                    if portfolio_withdrawals_enabled else None
                ),
                "annual_years_modeled_rebalanced": (
                    _annual_withdrawal_positive_year_counts(portfolio_withdrawal_rebalanced_result)[1]
                    if portfolio_withdrawals_enabled else None
                ),
                "annual_years_modeled_not_rebalanced": (
                    _annual_withdrawal_positive_year_counts(portfolio_withdrawal_not_rebalanced_result)[1]
                    if portfolio_withdrawals_enabled else None
                ),
                "annual_withdrawals_funded_rebalanced": (
                    _annual_withdrawal_funding_counts(portfolio_withdrawal_rebalanced_result, float(portfolio_annual_withdrawal or 0))[0]
                    if portfolio_withdrawals_enabled else None
                ),
                "annual_withdrawals_targeted_rebalanced": (
                    _annual_withdrawal_funding_counts(portfolio_withdrawal_rebalanced_result, float(portfolio_annual_withdrawal or 0))[1]
                    if portfolio_withdrawals_enabled else None
                ),
                "annual_withdrawals_funded_not_rebalanced": (
                    _annual_withdrawal_funding_counts(portfolio_withdrawal_not_rebalanced_result, float(portfolio_annual_withdrawal or 0))[0]
                    if portfolio_withdrawals_enabled else None
                ),
                "annual_withdrawals_targeted_not_rebalanced": (
                    _annual_withdrawal_funding_counts(portfolio_withdrawal_not_rebalanced_result, float(portfolio_annual_withdrawal or 0))[1]
                    if portfolio_withdrawals_enabled else None
                ),
                # Legacy fields intentionally retain the not-rebalanced path for backward compatibility.
                "withdrawal_total": float(portfolio_withdrawal_not_rebalanced_result.get("total_withdrawn") or 0) if portfolio_withdrawals_enabled else 0.0,
                "withdrawal_ending_balance": float(portfolio_withdrawal_not_rebalanced_result.get("ending_balance") or 0) if portfolio_withdrawals_enabled else None,
                "withdrawal_net_value": float(portfolio_withdrawal_not_rebalanced_result.get("net_value_including_withdrawals") or 0) if portfolio_withdrawals_enabled else None,
                "withdrawal_net_profit": float(portfolio_withdrawal_not_rebalanced_result.get("net_profit_including_withdrawals") or 0) if portfolio_withdrawals_enabled else None,
                "withdrawal_depleted_year": portfolio_withdrawal_not_rebalanced_result.get("depleted_year") if portfolio_withdrawals_enabled else None,
                "withdrawal_schedule": list(portfolio_withdrawal_not_rebalanced_result.get("schedule") or []) if portfolio_withdrawals_enabled else [],
                "withdrawal_not_rebalanced": dict(portfolio_withdrawal_not_rebalanced_result) if portfolio_withdrawals_enabled else {},
                "withdrawal_rebalanced": dict(portfolio_withdrawal_rebalanced_result) if portfolio_withdrawals_enabled else {},
                "withdrawal_not_rebalanced_schedule": list(portfolio_withdrawal_not_rebalanced_result.get("schedule") or []) if portfolio_withdrawals_enabled else [],
                "withdrawal_rebalanced_schedule": list(portfolio_withdrawal_rebalanced_result.get("schedule") or []) if portfolio_withdrawals_enabled else [],
                "monthly_withdrawals_enabled": bool(portfolio_monthly_withdrawals_enabled),
                "monthly_withdrawal_amount": float(portfolio_monthly_withdrawal or 0) if portfolio_monthly_withdrawals_enabled else 0.0,
                "monthly_withdrawal_total": float(portfolio_monthly_withdrawal_not_rebalanced_result.get("total_withdrawn") or 0) if portfolio_monthly_withdrawals_enabled else 0.0,
                "monthly_withdrawal_ending_balance": float(portfolio_monthly_withdrawal_not_rebalanced_result.get("ending_balance") or 0) if portfolio_monthly_withdrawals_enabled else None,
                "monthly_withdrawal_depleted_period": portfolio_monthly_withdrawal_not_rebalanced_result.get("depleted_period") if portfolio_monthly_withdrawals_enabled else None,
                "monthly_withdrawal_not_rebalanced": dict(portfolio_monthly_withdrawal_not_rebalanced_result) if portfolio_monthly_withdrawals_enabled else {},
                "monthly_withdrawal_rebalanced": dict(portfolio_monthly_withdrawal_rebalanced_result) if portfolio_monthly_withdrawals_enabled else {},
                "monthly_withdrawal_not_rebalanced_schedule": list(portfolio_monthly_withdrawal_not_rebalanced_result.get("schedule") or []) if portfolio_monthly_withdrawals_enabled else [],
                "monthly_withdrawal_rebalanced_schedule": list(portfolio_monthly_withdrawal_rebalanced_result.get("schedule") or []) if portfolio_monthly_withdrawals_enabled else [],
                "monthly_return_method": "Actual adjusted month-end return from Yahoo/yfinance daily history" if portfolio_monthly_withdrawals_enabled else None,
                "app_version": MARKETSCOPE_VERSION,
                "pdf_layout": "MarketScope Portfolio Split Simulator v37 - v5.9.82 monthly reset + monthly start-year RB/NR depletion dashboard + continuous monthly start-year paths + start-year RB/NR depletion dashboard + split start-year strategies + persistent Build Simulation withdrawal tabs + annual and monthly reset views + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1",
            }
            # v5.9.19: create and persist the actual PDF artifact before saving its library record.
            # The server copy is immediately available at an HTTPS static-file URL for mobile
            # viewing/sharing; GitHub (or an optional persistent Render disk) provides recovery
            # after server restart/redeploy.
            try:
                _pdf_check = build_portfolio_simulation_pdf(record)
                if not _pdf_check.startswith(b"%PDF"):
                    raise ValueError("PDF generator did not return a PDF file")
                pdf_ok, pdf_msg, pdf_meta = persist_pdf_artifact(
                    _pdf_check,
                    record,
                    BASE_DIR,
                    f"data: save MarketScope PDF artifact {record['id']}",
                )
                record.update(pdf_meta)
                updated_library = add_simulation(saved_simulations, record)
                library_ok, library_msg = persist_saved_simulations(
                    updated_library,
                    BASE_DIR / "data",
                    f"data: save MarketScope portfolio simulation {record['id']}",
                )
                combined_ok = bool(pdf_ok and library_ok)
                st.session_state.simulation_library_message = (
                    combined_ok,
                    f"{pdf_msg} {library_msg}",
                )
                st.session_state.simulation_library_open = True
                cached_saved_simulations.clear()
                cached_simulation_pdf.clear()
                st.rerun()
            except Exception as exc:
                st.error(f"The simulation could not be saved as PDF: {exc}")

        if st.session_state.simulation_library_open:
            saved_simulations = cached_saved_simulations()
            st.markdown(
                "<div class='simulation-library-header'><span>SAVED SIMULATIONS</span>"
                "<small>PDFs are stored as server files. On phones, use Open / Share PDF for the native Mail, Messages, group-chat, AirDrop and Files share sheet.</small></div>",
                unsafe_allow_html=True,
            )
            if not saved_simulations:
                st.info("No portfolio simulations have been saved yet.")
            else:
                for rec in saved_simulations:
                    rec_id = str(rec.get("id") or "")
                    rec_name = str(rec.get("name") or rec_id)
                    profit_value = float(rec.get("profit_loss") or 0)
                    return_value = float(rec.get("total_return") or 0)
                    profit_class = "pos" if profit_value > 0 else ("neg" if profit_value < 0 else "flat")
                    _saved_withdrawal_inline = _saved_simulation_withdrawal_inline_html(rec)
                    st.markdown(
                        "<div class='simulation-library-card'>"
                        f"<div class='simulation-library-identity'><span class='simulation-library-name'>{escape(rec_name)}</span>"
                        f"<small>{escape(str(rec.get('created_at_display_et') or ''))} • {escape(str(rec.get('period') or 'YTD'))} • "
                        f"{int(rec.get('instrument_count') or len(rec.get('instruments') or []))} instrument(s)</small></div>"
                        f"<div class='simulation-library-metric'><small>INVESTED</small><b>${float(rec.get('total_invested') or 0):,.2f}</b></div>"
                        f"<div class='simulation-library-metric'><small>ENDING</small><b>${float(rec.get('ending_value') or 0):,.2f}</b></div>"
                        f"<div class='simulation-library-metric'><small>PROFIT / LOSS</small><b class='{profit_class}'>${profit_value:+,.2f}</b></div>"
                        f"<div class='simulation-library-metric'><small>RETURN</small><b class='{profit_class}'>{return_value:+.2f}%</b></div>"
                        f"{_saved_withdrawal_inline}"
                        "</div>",
                        unsafe_allow_html=True,
                    )
                    action_cols = st.columns([1.35, 1.15, 1.0, 3.7])
                    pdf_record = _enrich_pdf_record_with_current_market(rec, market)
                    record_json = json.dumps(pdf_record, sort_keys=True, separators=(",", ":"))
                    # v5.9.66 forces the first open of an older saved PDF through the current
                    # page-1 contract so current price/rating/low/avg/high targets are present.
                    pdf_bytes = cached_simulation_pdf(record_json)
                    with action_cols[0]:
                        st.link_button(
                            "📱 Open / Share PDF",
                            pdf_viewer_url(pdf_record),
                            use_container_width=True,
                            help="Open the MarketScope mobile PDF viewer. Share PDF uses the phone's native share sheet; Back to MarketScope returns to the app.",
                        )
                    with action_cols[1]:
                        st.download_button(
                            "⬇ Download PDF",
                            data=pdf_bytes,
                            file_name=safe_filename(pdf_record),
                            mime="application/pdf",
                            key=f"download_simulation_{rec_id}",
                            use_container_width=True,
                        )
                    with action_cols[2]:
                        if st.button("🗑 Delete", key=f"delete_simulation_{rec_id}", use_container_width=True):
                            st.session_state.pending_delete_simulation = rec_id
                            st.rerun()
                    with action_cols[3]:
                        symbols_text = ", ".join(str(x.get("symbol") or "") for x in (rec.get("instruments") or []))
                        st.caption(f"{rec.get('allocation_mode', 'Equal split')} • {symbols_text}")
                        st.caption(f"PDF storage: {rec.get('pdf_storage', 'legacy record — auto-migrated when opened')}")

                    if st.session_state.pending_delete_simulation == rec_id:
                        st.warning(f"Delete saved simulation '{rec_name}'? This removes it from the in-app library.")
                        confirm_cols = st.columns([1, 1, 4])
                        with confirm_cols[0]:
                            if st.button("Confirm Delete", key=f"confirm_delete_simulation_{rec_id}", type="primary", use_container_width=True):
                                pdf_delete_ok, pdf_delete_msg = delete_pdf_artifact(
                                    rec,
                                    BASE_DIR,
                                    f"data: delete MarketScope PDF artifact {rec_id}",
                                )
                                updated = delete_simulation(saved_simulations, rec_id)
                                library_delete_ok, library_delete_msg = persist_saved_simulations(
                                    updated,
                                    BASE_DIR / "data",
                                    f"data: delete MarketScope portfolio simulation {rec_id}",
                                )
                                st.session_state.simulation_library_message = (
                                    bool(pdf_delete_ok and library_delete_ok),
                                    f"{pdf_delete_msg} {library_delete_msg}",
                                )
                                st.session_state.pending_delete_simulation = None
                                cached_saved_simulations.clear()
                                cached_simulation_pdf.clear()
                                st.rerun()
                        with confirm_cols[1]:
                            if st.button("Cancel", key=f"cancel_delete_simulation_{rec_id}", use_container_width=True):
                                st.session_state.pending_delete_simulation = None
                                st.rerun()


if future_tab.open:
    with future_tab:
        _projection_data_as_of = _valid_status_text(metadata.get("updated_at_display_et"))
        if not _projection_data_as_of and "Snapshot Updated ET" in market.columns:
            _projection_data_as_of = _latest_display_timestamp(market["Snapshot Updated ET"].tolist())
        _current_projection_payload = projection_payload_from_simulator(
            dict(st.session_state),
            list(selected_portfolio_symbols),
        )
        render_future_projection(
            market=market,
            annual_year_columns=list(YEAR_RETURN_COLS),
            latest_completed_year=int(LATEST_COMPLETED_YEAR),
            data_as_of=_projection_data_as_of or "Not available",
            model_as_of=now_et().date().isoformat(),
            monthly_loader=cached_future_projection_monthly_returns,
            live_loader=lambda symbols: cached_future_projection_live_context(tuple(symbols), market),
            logo_loader=cached_logo_urls,
            current_simulator_payload=_current_projection_payload,
        )


if favorite_tab.open:
    with favorite_tab:
        _favorite_data_as_of = _valid_status_text(metadata.get("updated_at_display_et"))
        if not _favorite_data_as_of and "Snapshot Updated ET" in market.columns:
            _favorite_data_as_of = _latest_display_timestamp(market["Snapshot Updated ET"].tolist())
        st.markdown("<div class='favorite-picks-title'>FAVORITE PICKS</div>", unsafe_allow_html=True)
        st.markdown(
            "MarketScope screens every eligible stock, then applies the Future Projection engine's "
            "historical shrinkage, current market regime, valuation, fundamentals, volatility, trend, "
            "and three-model ensemble to select up to **two stocks from each sector**."
        )
        st.info(
            "Favorite Picks are probabilistic research rankings, not guaranteed results or individualized investment advice. "
            "P25-P75 is the most useful planning range; P10 is the downside case and P50 is the central estimate."
        )
        pick_controls = st.columns([1.1, 2.9])
        with pick_controls[0]:
            run_favorite_picks = st.button(
                "Pick Fav",
                key="run_favorite_picks",
                type="primary",
                use_container_width=True,
                help="Refresh the finalist inputs and calculate the current Top 2 stocks within every eligible sector.",
            )
        with pick_controls[1]:
            st.caption(
                "The click performs a fresh ranking using the current MarketScope snapshot and the latest available "
                "supplemental data. Missing live inputs fall back to labeled historical assumptions instead of zero."
            )

        if run_favorite_picks:
            favorite_symbols = favorite_candidate_symbols(market, YEAR_RETURN_COLS)
            if not favorite_symbols:
                st.error(
                    "Favorite Picks could not find stocks with a valid sector and at least three completed years of history. "
                    "Refresh the MarketScope dataset, then try again."
                )
            else:
                with st.status("Building Favorite Picks…", expanded=True) as favorite_status:
                    try:
                        st.write(f"Screened the MarketScope stock universe; enriching {len(favorite_symbols):,} sector finalists.")
                        favorite_live_context = cached_future_projection_live_context(tuple(favorite_symbols), market)
                        st.write("Conditioning expected returns, volatility, and the starting market regime.")
                        favorite_result = build_favorite_picks(
                            market=market,
                            annual_year_columns=YEAR_RETURN_COLS,
                            live_context=favorite_live_context,
                            projection_years=5,
                            simulations=5_000,
                            random_seed=20260904,
                            data_as_of=_favorite_data_as_of or "Not available",
                        )
                        st.session_state.favorite_picks_result = favorite_result
                        st.write("Comparing this run with the last permanently saved sector picks and risk ratings.")
                        latest_history = merge_favorite_picks_ledgers(
                            favorite_picks_history,
                            load_remote_favorite_picks_history(timeout=12),
                        )
                        favorite_picks_history, favorite_change_events = record_favorite_picks_run(
                            latest_history,
                            favorite_result["table"],
                            observed_at=now_et(),
                            data_as_of=favorite_result.get("data_as_of") or "Latest available",
                            random_seed=favorite_result.get("random_seed"),
                        )
                        durable_history_ok, history_message = persist_favorite_picks_history(
                            favorite_picks_history,
                            FAVORITE_PICKS_HISTORY_FILE,
                        )
                        st.session_state.favorite_picks_history_message = (
                            durable_history_ok,
                            history_message,
                            len(favorite_change_events),
                        )
                        try:
                            favorite_picks_history = merge_favorite_picks_ledgers(
                                favorite_picks_history,
                                json.loads(FAVORITE_PICKS_HISTORY_FILE.read_text(encoding="utf-8")),
                            )
                        except Exception:
                            pass
                        load_favorite_picks_history.clear()
                        favorite_picks_change_frame = favorite_change_history_frame(favorite_picks_history)
                        favorite_picks_run_frame = favorite_run_history_frame(favorite_picks_history)
                        favorite_status.update(
                            label=(
                                f"Favorite Picks complete — {favorite_result['pick_count']} stocks across "
                                f"{favorite_result['sector_count']} sectors; {len(favorite_change_events)} new change event(s)"
                            ),
                            state="complete",
                            expanded=False,
                        )
                    except Exception:
                        favorite_status.update(label="Favorite Picks could not be completed", state="error", expanded=True)
                        st.error(
                            "The ranking could not be completed with the currently loaded data. Refresh MarketScope and try again; "
                            "no portfolio or historical simulator values were changed."
                        )

        favorite_result = st.session_state.get("favorite_picks_result")
        if not isinstance(favorite_result, dict) or favorite_result.get("table") is None:
            st.markdown(
                "<div class='favorite-empty'><b>Ready to rank</b><span>Select Pick Fav to calculate the latest sector-by-sector favorites.</span></div>",
                unsafe_allow_html=True,
            )
        else:
            favorite_table = favorite_result["table"].copy()
            favorite_state = favorite_result.get("market_state") or {}
            favorite_probabilities = favorite_state.get("regime_probabilities") or {}
            favorite_metrics = st.columns(5)
            favorite_metrics[0].metric("Eligible stocks", f"{int(favorite_result.get('eligible_stock_count', 0)):,}")
            favorite_metrics[1].metric("Sectors represented", f"{int(favorite_result.get('sector_count', 0)):,}")
            favorite_metrics[2].metric("Favorite picks", f"{int(favorite_result.get('pick_count', 0)):,}")
            favorite_metrics[3].metric("Market regime score", f"{float(favorite_state.get('regime_score', 50.0)):.1f}/100")
            favorite_metrics[4].metric("Projection confidence", str(favorite_state.get("projection_confidence") or "Low"))
            st.markdown(
                "<div class='favorite-regime-grid'>"
                f"<div><span>Bear probability</span><b>{float(favorite_probabilities.get('Bear', 0.0)):.2f}%</b></div>"
                f"<div><span>Normal probability</span><b>{float(favorite_probabilities.get('Normal', 0.0)):.2f}%</b></div>"
                f"<div><span>Bull probability</span><b>{float(favorite_probabilities.get('Bull', 0.0)):.2f}%</b></div>"
                f"<div><span>Market trend</span><b>{escape(str(favorite_state.get('market_trend') or 'Unknown'))}</b></div>"
                f"<div><span>Volatility</span><b>{escape(str(favorite_state.get('volatility_environment') or 'Historical'))}</b></div>"
                f"<div><span>Data as of</span><b>{escape(str(favorite_result.get('data_as_of') or 'Latest available'))}</b></div>"
                "</div>",
                unsafe_allow_html=True,
            )

            st.markdown("### Top 2 stocks by sector")
            st.caption(
                "P10, P25, P50, P75, and P90 are five-year annualized model outcomes and are displayed in ascending order. "
                "The Why Selected and Key Risk columns explain the evidence behind each ranking."
            )
            favorite_percentile_columns = [f"P{percentile} 5Y CAGR %" for percentile in (10, 25, 50, 75, 90)]
            favorite_column_config = {
                "Sector Rank": st.column_config.NumberColumn("Sector Rank", format="%d"),
                "Favorite Score": st.column_config.ProgressColumn("Favorite Score", min_value=0.0, max_value=100.0, format="%.1f"),
                "Risk Score": st.column_config.ProgressColumn("Risk Score", min_value=0.0, max_value=100.0, format="%.1f"),
                "Current Price": st.column_config.NumberColumn("Current Price", format="$%.2f"),
                "Expected Annual Return %": st.column_config.NumberColumn("Expected Return", format="%.2f%%"),
                "Historical CAGR %": st.column_config.NumberColumn("Historical CAGR", format="%.2f%%"),
                "Positive Years %": st.column_config.NumberColumn("Positive Years", format="%.1f%%"),
                "Conditioned Volatility %": st.column_config.NumberColumn("Modeled Volatility", format="%.2f%%"),
                "6M": st.column_config.NumberColumn("6M Return", format="%.2f%%"),
                "Distance From 52W High %": st.column_config.NumberColumn("From 52W High", format="%.2f%%"),
                "Fundamental Score": st.column_config.ProgressColumn("Fundamentals", min_value=0.0, max_value=100.0, format="%.0f"),
                "Valuation Score": st.column_config.ProgressColumn("Valuation", min_value=0.0, max_value=100.0, format="%.0f"),
                "Trend Score": st.column_config.ProgressColumn("Trend", min_value=0.0, max_value=100.0, format="%.0f"),
                **{
                    column: st.column_config.NumberColumn(column.replace(" 5Y CAGR", ""), format="%.2f%%")
                    for column in favorite_percentile_columns
                },
            }
            st.dataframe(
                favorite_table,
                use_container_width=True,
                hide_index=True,
                height=min(920, 92 + 38 * len(favorite_table)),
                column_config=favorite_column_config,
                column_order=list(favorite_table.columns),
                key="favorite_picks_results_table",
            )
            download_columns = [
                "Sector", "Sector Rank", "Symbol", "Name", "Favorite Score", "Model Confidence", "Risk Rating", "Risk Score",
                "Expected Annual Return %", *favorite_percentile_columns, "Historical CAGR %", "Positive Years %",
                "Historical Worst Year", "Conditioned Volatility %", "6M", "Fundamental Score", "Valuation Score",
                "Trend Score", "Observed Years", "Live Data Quality", "Why Selected", "Key Risk", "Data As Of",
            ]
            st.download_button(
                "Download Favorite Picks CSV",
                data=favorite_table[download_columns].to_csv(index=False).encode("utf-8"),
                file_name=f"MarketScope_Favorite_Picks_{now_et().date().isoformat()}.csv",
                mime="text/csv",
                key="download_favorite_picks_csv",
            )
            with st.expander("How Favorite Picks are calculated"):
                st.write(favorite_result.get("methodology") or "Methodology unavailable.")
                weights = favorite_result.get("ensemble_weights") or {}
                if weights:
                    st.dataframe(
                        pd.DataFrame(
                            [{"Model": name, "Ensemble Weight %": float(weight) * 100.0} for name, weight in weights.items()]
                        ),
                        use_container_width=True,
                        hide_index=True,
                        column_config={"Ensemble Weight %": st.column_config.NumberColumn(format="%.2f%%")},
                    )
                st.caption(
                    "The ranking favors calibrated probability ranges, downside resilience, data quality, and repeatable evidence. "
                    "It does not automatically add a stock to a portfolio or forecast a guaranteed future price."
                )
            with st.expander("Data freshness and ranking warnings"):
                freshness = favorite_state.get("data_freshness") or {}
                if freshness:
                    st.dataframe(
                        pd.DataFrame([{"Dataset": name, **values} for name, values in freshness.items()]),
                        use_container_width=True,
                        hide_index=True,
                    )
                warnings = favorite_result.get("warnings") or []
                if warnings:
                    for warning in warnings:
                        st.warning(str(warning))
                else:
                    st.success("No supplemental data warnings were reported for this ranking run.")
            st.caption("To test any Favorite Pick in a portfolio, open Future Projection and select one or more of the ranked tickers.")

        if st.session_state.favorite_picks_history_message:
            history_ok, history_message, history_change_count = st.session_state.favorite_picks_history_message
            if history_ok:
                st.success(f"Change trail saved permanently. {history_change_count} new first-detected event(s) were added. {history_message}")
            else:
                st.warning(
                    f"The ranking completed and {history_change_count} change event(s) were recorded locally. {history_message}"
                )
            st.session_state.favorite_picks_history_message = None

        st.markdown("### Pick Fav Change Trail")
        st.caption(
            "This audit table is append-only. It compares each manual or scheduled run with the prior saved Top 2 in every "
            "sector and permanently keeps the date each replacement or Favorite risk-rating change was first detected."
        )
        if favorite_picks_change_frame.empty:
            st.info("No changes have been recorded yet. The first completed run establishes the initial sector favorites.")
        else:
            st.dataframe(
                favorite_picks_change_frame,
                use_container_width=True,
                hide_index=True,
                height=min(620, 72 + max(1, len(favorite_picks_change_frame)) * 35),
                key="favorite_picks_change_history_tab",
            )
            with st.expander(f"Previous Pick Fav runs ({len(favorite_picks_run_frame):,})"):
                st.dataframe(
                    favorite_picks_run_frame,
                    use_container_width=True,
                    hide_index=True,
                    height=min(480, 72 + max(1, len(favorite_picks_run_frame)) * 35),
                    key="favorite_picks_run_history_tab",
                )
    
        from top12_ui import render_top12_rankings
        from top12_data import load_monthly as top12_monthly
        render_top12_rankings(market, list(YEAR_RETURN_COLS), _favorite_data_as_of, top12_monthly, lambda symbols: cached_future_projection_live_context(tuple(symbols), market))


with market_tab:
    st.markdown("<div class='investment-title'>INVESTMENT SIMULATOR</div>", unsafe_allow_html=True)
    sim_cols = st.columns([1.2, 2.8, 1.2, 2.4])
    with sim_cols[0]:
        investment_amount = st.number_input(
            "Investment amount ($)",
            min_value=0.0,
            max_value=1_000_000_000.0,
            value=float(_query_scalar_early("profit_amount", "10000") or 10000),
            step=1_000.0,
            format="%.2f",
            key="investment_amount",
        )
    with sim_cols[1]:
        investment_period_choice = st.segmented_control(
            "Investment period",
            ["YTD", *ANNUAL_HORIZON_OPTIONS],
            default=(_query_scalar_early("sim_period", "10Y") if _query_scalar_early("sim_period", "10Y") in ["YTD", *ANNUAL_HORIZON_OPTIONS] else "10Y"),
            key="investment_period_choice",
            format_func=timeframe_display_label,
            help=f"Choose YTD only, or compound 1–{ANNUAL_HISTORY_YEARS} of the most recent completed calendar years.",
        )
        investment_period_choice = str(investment_period_choice or "10Y")
        investment_is_ytd = investment_period_choice == "YTD"
        investment_years = 0 if investment_is_ytd else int(investment_period_choice.replace("Y", ""))
    with sim_cols[2]:
        include_current_ytd_toggle = st.toggle(
            "Include current YTD",
            value=_query_scalar_early("include_ytd", "1").lower() in {"1", "true", "yes"},
            key="include_current_ytd",
            disabled=investment_is_ytd,
            help=f"For 1Y–{ANNUAL_HISTORY_YEARS}Y selections, apply the current YTD return after the completed calendar years. YTD-only always uses YTD by itself.",
        )
        include_current_ytd = True if investment_is_ytd else bool(include_current_ytd_toggle)
    with sim_cols[3]:
        st.caption(
            f"Investment years: choose YTD for a current-year-only profit calculation, or 1–{ANNUAL_HISTORY_YEARS} completed calendar years for historical compounding. The maximum grows automatically after each year closes. "
            "You can also tap any return period/year inside an individual card to calculate profit for that exact period using this dollar amount."
        )

    table_withdraw_cols = st.columns([1.35, 1.55, 4.7])
    with table_withdraw_cols[0]:
        market_table_withdrawals_enabled = st.toggle(
            "Table yearly withdrawal",
            value=False,
            key="market_table_withdrawals_enabled",
            disabled=investment_is_ytd,
            help=f"Add a withdrawal simulation to Market Table using the exact annual-return columns shown in the table. The maximum {ANNUAL_HISTORY_YEARS}Y selection uses every tracked completed year where the instrument has full history.",
        )
    with table_withdraw_cols[1]:
        market_table_annual_withdrawal = st.number_input(
            "Table withdrawal / year ($)",
            min_value=0.0,
            max_value=1_000_000_000.0,
            value=10_000.0,
            step=5_000.0,
            format="%.2f",
            key="market_table_annual_withdrawal",
            disabled=not bool(market_table_withdrawals_enabled),
        )
    with table_withdraw_cols[2]:
        if market_table_withdrawals_enabled:
            st.caption(
                f"Withdrawal source: the exact annual returns displayed in Market Table for {timeframe_display_label(investment_period_choice)}. "
                "Returns are applied oldest-to-newest; the cash withdrawal is taken after each completed year's return. "
                f"For {ANNUAL_HISTORY_YEARS}Y, this uses {ANNUAL_HISTORY_FIRST_YEAR}–{LATEST_COMPLETED_YEAR} where the instrument traded for the full required history."
            )
        else:
            st.caption(
                "Enable Table yearly withdrawal to rank individual stocks/ETFs by remaining balance and net value after recurring annual cash withdrawals."
            )

    # Display-mode tabs: preserve the full futuristic card experience while adding a sortable table view.
    view_filtered = filtered.copy()
    st.markdown(
        "<div class='view-switch-title'>DISPLAY MODE</div><div class='view-switch-subtitle'>Switch between the interactive instrument cards and a dense sortable market table.</div>",
        unsafe_allow_html=True,
    )
    card_view_tab, table_view_tab = st.tabs(["▦ Card View", "▤ Table View"])

    with card_view_tab:
        # Keep card sorting/pagination isolated from the shared filtered universe used by Table View.
        filtered = view_filtered.copy()
        # Futuristic card navigator — every card exposes the complete performance ladder.
        for col in DISPLAY_COLS:
            if col not in filtered.columns:
                filtered[col] = pd.NA

        st.markdown(
            "<div class='navigator-title'><span>MARKET NAVIGATOR</span>"
            f"<small>Every card shows short-horizon + {ANNUAL_HISTORY_YEARS} calendar-year returns • tap News for catalysts or Open for yearly charts</small></div>",
            unsafe_allow_html=True,
        )

        # v5.9.78: use the same searchable dropdown interaction as Portfolio
        # Simulator / Comparison rather than a plain free-text filter.
        _card_search_rows = filtered.copy()
        _card_search_rows["Symbol"] = _card_search_rows["Symbol"].astype(str).str.upper().str.strip()
        _card_search_rows = _card_search_rows.drop_duplicates("Symbol", keep="last")
        _card_search_options = sorted(_card_search_rows["Symbol"].tolist())
        _card_search_lookup = (
            _card_search_rows.set_index("Symbol").to_dict(orient="index")
            if not _card_search_rows.empty else {}
        )
        _card_valid_set = set(_card_search_options)
        _card_saved_selection = [
            str(symbol).upper()
            for symbol in st.session_state.get("card_local_search_selector", [])
            if str(symbol).upper() in _card_valid_set
        ]
        if _card_saved_selection != list(st.session_state.get("card_local_search_selector", [])):
            st.session_state.card_local_search_selector = _card_saved_selection

        card_local_selection = st.multiselect(
            "Search / select stocks & ETFs",
            options=_card_search_options,
            key="card_local_search_selector",
            format_func=lambda symbol: (
                f"{symbol} — {_card_search_lookup.get(symbol, {}).get('Name', symbol)}"
                + (f" • {_card_search_lookup.get(symbol, {}).get('Type')}"
                   if str(_card_search_lookup.get(symbol, {}).get('Type') or '').strip() not in {'', 'Unknown', 'nan'} else "")
                + (f" • {_card_search_lookup.get(symbol, {}).get('Sector')}"
                   if str(_card_search_lookup.get(symbol, {}).get('Sector') or '').strip() not in {'', 'Unknown', 'nan'} else "")
            ),
            placeholder="Search ticker, company / ETF name, type, or sector…",
            help=(
                "Type inside the dropdown to search the currently filtered universe, then select one or more "
                "stocks/ETFs. Leave it empty to show every currently filtered Card View instrument."
            ),
        )
        _card_selected_symbols = list(dict.fromkeys(str(symbol).upper() for symbol in card_local_selection))
        if _card_selected_symbols:
            filtered = filtered.loc[
                filtered["Symbol"].astype(str).str.upper().isin(_card_selected_symbols)
            ].copy()
            st.caption(
                f"Card View selection: {len(_card_selected_symbols):,} instrument(s). "
                "Remove selections from the dropdown to return to the full filtered Card View universe."
            )

        def _investment_projection_for_sort(row: pd.Series, principal: float, include_ytd: bool, years_requested: int) -> dict | None:
            """Calculate the same historical investment result used by each card, for sorting."""
            try:
                principal = float(principal)
            except Exception:
                return None
            if not np.isfinite(principal) or principal <= 0:
                return None

            if int(years_requested) == 0:
                ytd = pd.to_numeric(pd.Series([row.get("YTD")]), errors="coerce").iloc[0]
                if pd.isna(ytd) or not np.isfinite(ytd):
                    return None
                value = principal * (1.0 + float(ytd) / 100.0)
                return {"ending_value": value, "profit": value - principal}

            newest_to_oldest: list[tuple[str, float]] = []
            for year in YEAR_RETURN_COLS:
                value = pd.to_numeric(pd.Series([row.get(year)]), errors="coerce").iloc[0]
                if pd.isna(value) or not np.isfinite(value):
                    break
                newest_to_oldest.append((year, float(value)))
            years_requested = max(1, min(ANNUAL_HISTORY_YEARS, int(years_requested)))
            if len(newest_to_oldest) < years_requested:
                return None
            newest_to_oldest = newest_to_oldest[:years_requested]

            value = principal
            for _, annual_pct in reversed(newest_to_oldest):
                factor = 1.0 + annual_pct / 100.0
                if factor < 0:
                    return None
                value *= factor

            if include_ytd:
                ytd = pd.to_numeric(pd.Series([row.get("YTD")]), errors="coerce").iloc[0]
                if pd.notna(ytd) and np.isfinite(ytd):
                    factor = 1.0 + float(ytd) / 100.0
                    if factor >= 0:
                        value *= factor

            return {"ending_value": value, "profit": value - principal}


        SORT_OPTIONS = ["Market Cap", "Total Profit ($)", *PERF_COLS, "Rating"]

        if st.button(
            "✦ Sort Cards By" if not st.session_state.sort_menu_open else "✦ Hide Sort Options",
            key="toggle_sort_menu",
            use_container_width=True,
            type="primary" if st.session_state.sort_menu_open else "secondary",
        ):
            st.session_state.sort_menu_open = not st.session_state.sort_menu_open
            st.rerun()
        st.markdown(
            f"<div class='sort-summary'>Sorted by <strong>{escape(timeframe_display_label(st.session_state.card_sort_choice))}</strong> "
            f"• {'low to high' if st.session_state.card_sort_ascending else 'high to low'}</div>",
            unsafe_allow_html=True,
        )

        if st.session_state.sort_menu_open:
            st.markdown("<div class='sort-kicker'>SORT CARDS BY</div>", unsafe_allow_html=True)
            for start_idx in range(0, len(SORT_OPTIONS), 6):
                chunk = SORT_OPTIONS[start_idx:start_idx + 6]
                sort_cols = st.columns(len(chunk))
                for col_widget, option in zip(sort_cols, chunk):
                    active = st.session_state.card_sort_choice == option
                    label = f"● {timeframe_display_label(option)}" if active else timeframe_display_label(option)
                    if col_widget.button(
                        label,
                        key=f"sort_card_{option}",
                        use_container_width=True,
                        type="primary" if active else "secondary",
                    ):
                        if st.session_state.card_sort_choice != option:
                            st.session_state.card_sort_choice = option
                            st.session_state.card_page = 0
                        st.rerun()

            order_cols = st.columns([1.25, 1.25, 4.5])
            with order_cols[0]:
                if st.button(
                    "↓ High → Low",
                    key="sort_desc",
                    use_container_width=True,
                    type="primary" if not st.session_state.card_sort_ascending else "secondary",
                ):
                    st.session_state.card_sort_ascending = False
                    st.session_state.card_page = 0
                    st.rerun()
            with order_cols[1]:
                if st.button(
                    "↑ Low → High",
                    key="sort_asc",
                    use_container_width=True,
                    type="primary" if st.session_state.card_sort_ascending else "secondary",
                ):
                    st.session_state.card_sort_ascending = True
                    st.session_state.card_page = 0
                    st.rerun()
            with order_cols[2]:
                st.caption(
                    f"Sorting by {st.session_state.card_sort_choice} • "
                    f"{'low to high' if st.session_state.card_sort_ascending else 'high to low'}"
                )

        sort_choice = st.session_state.card_sort_choice
        sort_map = {"Market Cap": "MarketCap", "Rating": "Analyst Rating"}
        sort_col = sort_map.get(sort_choice, sort_choice)
        ascending = bool(st.session_state.card_sort_ascending)
        if sort_choice == "Total Profit ($)":
            profit_values = filtered.apply(
                lambda row: (
                    (_investment_projection_for_sort(row, investment_amount, include_current_ytd, investment_years) or {}).get("profit", np.nan)
                ),
                axis=1,
            )
            filtered = (
                filtered.assign(_profit_sort=pd.to_numeric(profit_values, errors="coerce"))
                .sort_values(["_profit_sort", "MarketCap"], ascending=[ascending, False], na_position="last")
                .drop(columns="_profit_sort")
            )
        elif sort_col in filtered.columns:
            if sort_choice == "Rating":
                rank = {"Strong Buy": 5, "Buy": 4, "Hold": 3, "Sell": 2, "Strong Sell": 1, "Not Rated": 0}
                filtered = (
                    filtered.assign(_sort=filtered[sort_col].map(rank).fillna(0))
                    .sort_values(["_sort", "MarketCap"], ascending=[ascending, False], na_position="last")
                    .drop(columns="_sort")
                )
            else:
                filtered = filtered.sort_values(sort_col, ascending=ascending, na_position="last")

        if filtered.empty:
            st.info("No instruments match the current Card View filters/search. Clear the Card View search or filters to show instruments.")

        CARDS_PER_PAGE = 12
        pages = max(1, (len(filtered) + CARDS_PER_PAGE - 1) // CARDS_PER_PAGE)
        if st.session_state.card_page >= pages:
            st.session_state.card_page = 0
        page_cols = st.columns([1, 1, 3, 1, 1])
        with page_cols[0]:
            if st.button("◀", key="prev_cards", use_container_width=True, disabled=st.session_state.card_page <= 0):
                st.session_state.card_page -= 1
                st.rerun()
        with page_cols[1]:
            st.markdown(f"<div class='page-chip'>Page {st.session_state.card_page + 1}</div>", unsafe_allow_html=True)
        with page_cols[3]:
            st.markdown(f"<div class='page-chip'>{len(filtered):,} results</div>", unsafe_allow_html=True)
        with page_cols[4]:
            if st.button("▶", key="next_cards", use_container_width=True, disabled=st.session_state.card_page >= pages - 1):
                st.session_state.card_page += 1
                st.rerun()

        page_start = st.session_state.card_page * CARDS_PER_PAGE
        card_rows = filtered.iloc[page_start:page_start + CARDS_PER_PAGE].copy()

        # Upgrade-safe lazy target enrichment: old durable snapshots do not yet contain
        # v5.9 target columns. Only the visible stock cards are queried, cached for six
        # hours, and filled without slowing the entire universe. The scheduled/manual
        # refresh persists these values later.
        # Ensure visible stock cards always receive the same Low / Average / High target range
        # used by Table View, Comparison, Portfolio Simulator and saved PDFs.
        visible_stock_symbols = card_rows.loc[
            card_rows["Type"].astype(str).str.upper().eq("STOCK"), "Symbol"
        ].astype(str).tolist()
        card_rows = _hydrate_price_targets(card_rows, visible_stock_symbols)

        # One batched Yahoo request supplies two years of adjusted 1-day closes for
        # every visible card. The result is cached for 30 minutes to keep paging fast.
        visible_chart_histories = cached_card_two_year_histories(
            tuple(card_rows["Symbol"].astype(str).str.upper().tolist())
        )
        visible_logo_urls = cached_logo_urls(
            tuple(card_rows["Symbol"].astype(str).str.upper().tolist())
        )

        def _card_chart_svg(symbol: str, chart_histories: dict[str, pd.DataFrame] | None = None) -> str:
            """Compact 2Y / 1D SVG chart using the caller's exact visible-symbol history set."""
            history_map = chart_histories if chart_histories is not None else visible_chart_histories
            history = history_map.get(str(symbol).upper())
            if history is None or history.empty or "Close" not in history.columns:
                return (
                    '<div class="card-mini-chart card-mini-chart-empty">'
                    '<span>2Y • 1D</span><b>Chart unavailable</b></div>'
                )
            close = pd.to_numeric(history["Close"], errors="coerce").dropna()
            if len(close) < 2:
                return (
                    '<div class="card-mini-chart card-mini-chart-empty">'
                    '<span>2Y • 1D</span><b>Chart unavailable</b></div>'
                )
            # Limit the inline SVG to roughly 180 points while preserving endpoints.
            step = max(1, int(np.ceil(len(close) / 180)))
            sampled = close.iloc[::step].copy()
            if sampled.index[-1] != close.index[-1]:
                sampled = pd.concat([sampled, close.iloc[[-1]]])
            values = sampled.to_numpy(dtype=float)
            lo, hi = float(np.nanmin(values)), float(np.nanmax(values))
            span = hi - lo
            if not np.isfinite(span) or span <= 0:
                span = max(abs(hi), 1.0) * 0.01
            width, height = 250.0, 92.0
            pad_x, pad_y = 6.0, 9.0
            usable_w, usable_h = width - 2 * pad_x, height - 2 * pad_y
            points = []
            denom = max(1, len(values) - 1)
            for i, value in enumerate(values):
                x = pad_x + usable_w * i / denom
                y = pad_y + usable_h * (1.0 - (float(value) - lo) / span)
                points.append(f"{x:.1f},{y:.1f}")
            change = (float(values[-1]) / float(values[0]) - 1.0) * 100.0 if float(values[0]) else 0.0
            tone = "up" if change >= 0 else "down"
            return (
                f'<div class="card-mini-chart card-mini-chart-{tone}">'
                f'<div class="card-mini-chart-label"><span>2Y • 1D</span><b>{change:+.1f}%</b></div>'
                f'<svg viewBox="0 0 {int(width)} {int(height)}" role="img" aria-label="{escape(str(symbol))} two-year daily adjusted price chart">'
                '<line x1="6" y1="24" x2="244" y2="24" class="mini-grid-line" />'
                '<line x1="6" y1="48" x2="244" y2="48" class="mini-grid-line" />'
                '<line x1="6" y1="72" x2="244" y2="72" class="mini-grid-line" />'
                f'<polyline points="{" ".join(points)}" class="mini-price-line" fill="none" />'
                '</svg></div>'
            )

        def _period_profit_projection(row: pd.Series, principal: float, metric: str) -> dict | None:
            if metric not in PERF_COLS:
                return None
            try:
                principal = float(principal)
            except Exception:
                return None
            if not np.isfinite(principal) or principal <= 0:
                return None
            pct = pd.to_numeric(pd.Series([row.get(metric)]), errors="coerce").iloc[0]
            if pd.isna(pct) or not np.isfinite(pct):
                return {"unavailable": True, "period": metric}
            ending_value = principal * (1.0 + float(pct) / 100.0)
            return {
                "period": metric,
                "return_pct": float(pct),
                "ending_value": ending_value,
                "profit": ending_value - principal,
            }


        def _period_profit_result_html(row: pd.Series, principal: float, metric: str | None) -> str:
            if not metric:
                return '<div class="period-profit-hint">Tap a timeframe/year below to calculate profit for that exact period.</div>'
            result = _period_profit_projection(row, principal, metric)
            if result is None or result.get("unavailable"):
                return (
                    '<div class="period-profit-card"><span>SELECTED PERIOD • ' + escape(str(metric)) + '</span>'
                    '<b>Return data unavailable</b><small>No profit was estimated.</small></div>'
                )
            profit = float(result["profit"])
            klass = "pos" if profit > 0 else ("neg" if profit < 0 else "flat")
            return (
                '<div class="period-profit-card">'
                f'<span>SELECTED PERIOD • {escape(timeframe_display_label(result["period"]))} • ${float(principal):,.2f} invested</span>'
                f'<b>${float(result["ending_value"]):,.2f}</b>'
                f'<small class="{klass}">Profit {profit:+,.2f} • Return {float(result["return_pct"]):+.2f}%</small>'
                '</div>'
            )


    

        def _default_profit_metric(row: pd.Series) -> str:
            """Choose a useful available period when a card is first shown."""
            preferred = ["YTD", "1M", "1D"]
            ordered = preferred + [metric for metric in PERF_COLS if metric not in preferred]
            for metric in ordered:
                value = pd.to_numeric(pd.Series([row.get(metric)]), errors="coerce").iloc[0]
                if pd.notna(value) and np.isfinite(value):
                    return metric
            return PERF_COLS[0]


        def _set_card_profit_period(symbol: str, metric: str, namespace: str = "navigator") -> None:
            """Button callback: save a card-local return period without cross-view key collisions."""
            clean_symbol = str(symbol or "").upper()
            clean_namespace = ''.join(ch if ch.isalnum() else '_' for ch in str(namespace or "navigator").lower())
            if metric in PERF_COLS and clean_symbol:
                st.session_state[f"card_profit_period_selected_{clean_namespace}_{clean_symbol}"] = metric


        def _profit_tile_tone(row: pd.Series, metric: str, active: bool) -> str:
            """Return a DOM marker class used to color each native Streamlit button."""
            value = pd.to_numeric(pd.Series([row.get(metric)]), errors="coerce").iloc[0]
            if pd.isna(value) or not np.isfinite(value):
                base = "flat"
            elif float(value) > 0:
                base = "positive"
            elif float(value) < 0:
                base = "negative"
            else:
                base = "flat"
            return f"profit-tone-{base}{'-active' if active else ''}"


        @st.fragment
        def render_card_profit_period_fragment(row_data: dict, principal: float, namespace: str = "navigator") -> None:
            """Render reliable, card-local period buttons and exact-period profit output.

            Native Streamlit button callbacks update session state *before* the fragment
            reruns. This fixes the previous behavior where a clicked tile could render
            without the new period being applied. Only this fragment reruns, so the
            update remains smooth, updates only this card area, and the user's scroll position stays stable.
            """
            row = pd.Series(row_data)
            symbol = str(row.get("Symbol") or "").upper()
            clean_namespace = ''.join(ch if ch.isalnum() else '_' for ch in str(namespace or "navigator").lower())
            selected_key = f"card_profit_period_selected_{clean_namespace}_{symbol}"
            if not st.session_state.get(selected_key):
                st.session_state[selected_key] = _default_profit_metric(row)

            st.markdown(
                '<div class="period-profit-control-title">RETURN PERIODS • CLICK ANY TILE TO CALCULATE PROFIT</div>',
                unsafe_allow_html=True,
            )
            for idx in range(0, len(PERF_COLS), 3):
                tile_cols = st.columns(3, gap="small")
                for col, metric in zip(tile_cols, PERF_COLS[idx:idx + 3]):
                    active = st.session_state.get(selected_key) == metric
                    with col:
                        # The hidden marker lets CSS style this *native* Streamlit button
                        # by the sign of its return while preserving the reliable Python
                        # callback behavior. No `help=` tooltip is used, so there is no
                        # floating hover message when the user clicks or hovers a tile.
                        tone_class = _profit_tile_tone(row, metric, active)
                        st.markdown(
                            f'<span class="profit-tone-marker {tone_class}"></span>',
                            unsafe_allow_html=True,
                        )
                        _metric_raw = pd.to_numeric(pd.Series([row.get(metric)]), errors="coerce").iloc[0]
                        _metric_available = bool(pd.notna(_metric_raw) and np.isfinite(_metric_raw))
                        st.button(
                            f"{timeframe_display_label(metric)}  {format_pct(row.get(metric))}",
                            key=f"profit_tile_{clean_namespace}_{symbol}_{metric}",
                            use_container_width=True,
                            type="primary" if active and _metric_available else "secondary",
                            disabled=not _metric_available,
                            help=None if _metric_available else "No saved return exists for this period (for example, the instrument may not have existed yet).",
                            on_click=_set_card_profit_period,
                            args=(symbol, metric, clean_namespace),
                        )

            chosen_metric = str(st.session_state.get(selected_key) or _default_profit_metric(row))
            st.markdown(
                _period_profit_result_html(row, float(principal), chosen_metric),
                unsafe_allow_html=True,
            )

        def _card_anchor_id(symbol: str) -> str:
            safe = ''.join(ch if ch.isalnum() else '-' for ch in str(symbol).upper())
            return f"card-{safe}"


        def _tone(v):
            try:
                f = float(v)
                return "pos" if f > 0 else ("neg" if f < 0 else "flat")
            except Exception:
                return "flat"

        def _rating_class(r):
            r = str(r or "Not Rated")
            if r in {"Strong Buy", "Buy"}: return "rating-buy"
            if r == "Hold": return "rating-hold"
            if r in {"Sell", "Strong Sell"}: return "rating-sell"
            return "rating-na"

        def _card_display_name(row: pd.Series) -> str:
            """Use ETF Sector as the card label when available; stocks keep company name."""
            instrument_type = str(row.get("Type") or "").strip().upper()
            if instrument_type == "ETF":
                sector = str(row.get("Sector") or "").strip()
                if sector and sector.lower() not in {"unknown", "nan", "none", ""}:
                    return sector
            return str(row.get("Name") or row.get("Symbol") or "")


        def _stock_sector_html(row: pd.Series) -> str:
            """Show the stock sector directly under the company name."""
            if str(row.get("Type") or "").strip().upper() != "STOCK":
                return ""
            sector = str(row.get("Sector") or "").strip()
            if not sector or sector.lower() in {"unknown", "nan", "none"}:
                sector = "Sector unavailable"
            return f'<div class="stock-sector">{escape(sector)}</div>'



        def _history_verification_badge_html(row: pd.Series) -> str:
            """Compact independent-history cross-check flag for cards/comparison."""
            status = str(row.get("History Verification") or "Pending").strip()
            if status.lower() in {"", "nan", "none", "—"}:
                status = "Pending"
            coverage = str(row.get("Verification Coverage") or "").strip()
            if coverage.lower() in {"nan", "none", "—"}:
                coverage = ""
            max_diff = pd.to_numeric(pd.Series([row.get("Max Verification Diff (pp)")]), errors="coerce").iloc[0]
            exceptions = str(row.get("Verification Exceptions") or "").strip()
            palette = {
                "verified": ("#062f27", "#5eead4", "✓"),
                "review": ("#3a1d19", "#fca5a5", "⚠"),
                "partial": ("#30270b", "#fde68a", "◐"),
                "unavailable": ("#1e293b", "#cbd5e1", "○"),
                "pending": ("#1e293b", "#cbd5e1", "…"),
            }
            bg, fg, icon = palette.get(status.lower(), palette["pending"])
            suffix = f" {coverage}" if coverage else ""
            diff_text = f" • max Δ {float(max_diff):.2f}pp" if pd.notna(max_diff) and np.isfinite(max_diff) else ""
            title = exceptions or str(row.get("Verification Source") or "Independent historical cross-check")
            return (
                f'<div title="{escape(title, quote=True)}" style="margin-top:6px;">'
                f'<span style="display:inline-block;padding:3px 7px;border-radius:999px;'
                f'background:{bg};color:{fg};font-size:10px;font-weight:700;border:1px solid {fg}55;">'
                f'{icon} History {escape(status)}{escape(suffix)}{escape(diff_text)}</span></div>'
            )


        def _instrument_card_header_html(
            row: pd.Series, price: str, cap_display: str,
            logo_url: str = "", chart_histories: dict[str, pd.DataFrame] | None = None,
        ) -> str:
            """Card header with logo plus compact 2Y daily chart from the caller's ticker set."""
            raw_symbol = str(row.get("Symbol") or "")
            symbol = escape(raw_symbol)
            instrument_type = escape(str(row.get("Type") or ""))
            display_name = escape(_card_display_name(row))
            chart_html = _card_chart_svg(raw_symbol, chart_histories=chart_histories)
            logo_html = _card_logo_html(raw_symbol, logo_url)
            sector_html = _stock_sector_html(row)
            if str(row.get("Type") or "").strip().upper() == "ETF":
                sector = str(row.get("Sector") or "ETF / Fund").strip() or "ETF / Fund"
                sector_html = f'<div class="stock-sector">{escape(sector)}</div>'
            parts = [
                f'<div id="{_card_anchor_id(raw_symbol)}" class="instrument-card-head full-metrics-card">',
                '<div class="card-header-grid">',
                '<div class="card-header-identity">',
                '<div class="market-card-logo-identity">' + logo_html + '<div>',
                f'<div class="card-top"><span class="ticker">{symbol}</span></div>',
                f'<div class="company-name">{display_name}</div>',
                sector_html,
                '</div></div>',
                '<div class="card-header-chart">',
                f'<div class="asset-type-row"><span class="asset-type">{instrument_type}</span></div>',
                chart_html,
                '</div>',
                '</div>',
                f'<div class="card-quote-row"><span class="price-line">{escape(price)}</span><span class="cap-line">Mkt Cap {escape(cap_display)}</span></div>',
                _price_target_html(row),
                _history_verification_badge_html(row),
                '</div>',
            ]
            return ''.join(part for part in parts if part)


        # Legacy call shape remains supported: _instrument_card_html(row, price, cap_display, rating, signal)
        def _instrument_card_html(
            row: pd.Series, price: str, cap_display: str, rating: str, signal: str,
            logo_url: str = "", chart_histories: dict[str, pd.DataFrame] | None = None,
        ) -> str:
            """Full-metrics card header shared by Navigator and Comparison."""
            return _instrument_card_header_html(
                row, price, cap_display, logo_url=logo_url, chart_histories=chart_histories
            )


        def _card_bottom_html(rating: str, signal: str) -> str:
            return (
                '<div class="card-bottom">'
                f'<span class="rating-pill {_rating_class(rating)}">{escape(rating)}</span>'
                f'<span class="signal-pill">{escape(signal)}</span>'
                '</div>'
            )

        def _performance_cells(row: pd.Series, clickable: bool = False) -> str:
            cells = []
            for metric in PERF_COLS:
                value_html = (
                    f'<span>{escape(timeframe_display_label(metric))}</span>'
                    f'<b class="{_tone(row.get(metric))}">{escape(format_pct(row.get(metric)))}</b>'
                )
                cells.append('<div class="perf-cell">' + value_html + '</div>')
            return "".join(cells)

        def _detail_performance_html(row: pd.Series) -> str:
            # Detail matrix is informational; the clickable profit controls live in each market card.
            return '<div class="detail-performance-grid">' + _performance_cells(row, clickable=False) + '</div>'

        def _investment_projection(row: pd.Series, principal: float, include_ytd: bool, years_requested: int) -> dict | None:
            try:
                principal = float(principal)
            except Exception:
                return None
            if not np.isfinite(principal) or principal <= 0:
                return None

            if int(years_requested) == 0:
                ytd = pd.to_numeric(pd.Series([row.get("YTD")]), errors="coerce").iloc[0]
                if pd.isna(ytd) or not np.isfinite(ytd):
                    return {"insufficient": True, "available_years": 0, "requested_years": 0, "requested_period": "YTD"}
                value = principal * (1.0 + float(ytd) / 100.0)
                return {
                    "start_year": f"{now_et().year} YTD",
                    "end_year": f"{now_et().year} YTD",
                    "completed_years": 0,
                    "ytd_applied": True,
                    "ytd_only": True,
                    "ending_value": value,
                    "profit": value - principal,
                    "total_pct": float(ytd),
                }

            # Use the most recent contiguous run of completed calendar years.
            # This avoids pretending a partial IPO year or a missing year was a full-year return.
            newest_to_oldest: list[tuple[str, float]] = []
            for year in YEAR_RETURN_COLS:
                value = pd.to_numeric(pd.Series([row.get(year)]), errors="coerce").iloc[0]
                if pd.isna(value) or not np.isfinite(value):
                    break
                newest_to_oldest.append((year, float(value)))
            years_requested = max(1, min(ANNUAL_HISTORY_YEARS, int(years_requested)))
            if len(newest_to_oldest) < years_requested:
                return {"insufficient": True, "available_years": len(newest_to_oldest), "requested_years": years_requested}
            newest_to_oldest = newest_to_oldest[:years_requested]

            chronological = list(reversed(newest_to_oldest))
            value = principal
            for _, annual_pct in chronological:
                factor = 1.0 + annual_pct / 100.0
                if factor < 0:
                    return None
                value *= factor

            ytd_applied = False
            if include_ytd:
                ytd = pd.to_numeric(pd.Series([row.get("YTD")]), errors="coerce").iloc[0]
                if pd.notna(ytd) and np.isfinite(ytd):
                    factor = 1.0 + float(ytd) / 100.0
                    if factor >= 0:
                        value *= factor
                        ytd_applied = True

            profit = value - principal
            total_pct = (value / principal - 1.0) * 100.0
            return {
                "start_year": chronological[0][0],
                "end_year": chronological[-1][0],
                "completed_years": len(chronological),
                "ytd_applied": ytd_applied,
                "ending_value": value,
                "profit": profit,
                "total_pct": total_pct,
            }

        def _money_or_dash(value) -> str:
            value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
            if pd.isna(value) or not np.isfinite(value) or float(value) <= 0:
                return "—"
            return f"${float(value):,.2f}"


        def _price_target_html(row: pd.Series) -> str:
            if str(row.get("Type") or "").strip().upper() != "STOCK":
                return ""
            low = _money_or_dash(row.get("Price Target Low"))
            avg = _money_or_dash(row.get("Price Target Average"))
            high = _money_or_dash(row.get("Price Target High"))
            avg_num = pd.to_numeric(pd.Series([row.get("Price Target Average")]), errors="coerce").iloc[0]
            price_num = pd.to_numeric(pd.Series([row.get("Price")]), errors="coerce").iloc[0]
            implied = ""
            implied_class = "flat"
            if pd.notna(avg_num) and pd.notna(price_num) and float(price_num) > 0:
                pct = (float(avg_num) / float(price_num) - 1.0) * 100.0
                implied = f"<small class='{('pos' if pct > 0 else ('neg' if pct < 0 else 'flat'))}'>AVG implied {pct:+.1f}%</small>"
            return (
                '<div class="price-target-strip">'
                '<span class="target-title">ANALYST TARGETS</span>'
                f'<span><small>LOW</small><b>{escape(low)}</b></span>'
                f'<span><small>AVG</small><b>{escape(avg)}</b></span>'
                f'<span><small>HIGH</small><b>{escape(high)}</b></span>'
                f'{implied}'
                '</div>'
            )


        def _intraday_close_series(history: pd.DataFrame) -> pd.Series:
            if history is None or history.empty or "Close" not in history.columns:
                return pd.Series(dtype="float64")
            close = pd.to_numeric(history["Close"], errors="coerce").dropna()
            if close.empty:
                return close
            idx = pd.to_datetime(close.index)
            try:
                if idx.tz is not None:
                    idx = idx.tz_convert("America/New_York")
            except Exception:
                pass
            close.index = idx
            return close


        @st.fragment(run_every="60s")
        def render_live_intraday_chart(symbol: str) -> None:
            """Near-real-time Yahoo intraday chart for the single opened instrument."""
            with st.spinner(f"Loading live intraday chart for {symbol}..."):
                intraday = provider.download_intraday_history(symbol, period="1d", interval="1m", prepost=False)
                if intraday is None or intraday.empty:
                    intraday = provider.download_intraday_history(symbol, period="5d", interval="5m", prepost=False)
            close = _intraday_close_series(intraday)
            if close.empty:
                st.info(f"Yahoo did not return intraday data for {symbol} right now. The historical year chart remains available below.")
                return
            first = float(close.iloc[0])
            last = float(close.iloc[-1])
            change = (last / first - 1.0) * 100.0 if first > 0 else np.nan
            lc1, lc2, lc3, lc4 = st.columns(4)
            lc1.metric("Latest", f"${last:,.2f}")
            lc2.metric("Session / window", f"{change:+.2f}%" if np.isfinite(change) else "—")
            lc3.metric("High", f"${float(close.max()):,.2f}")
            lc4.metric("Low", f"${float(close.min()):,.2f}")
            st.line_chart(close.rename("Live adjusted price"), use_container_width=True, height=390)
            last_ts = pd.Timestamp(close.index[-1])
            try:
                last_label = last_ts.strftime("%b %d, %Y %I:%M:%S %p %Z")
            except Exception:
                last_label = str(last_ts)
            st.caption(
                f"Yahoo Finance via yfinance • intraday 1-minute data when available • last bar {last_label} • "
                "this panel refreshes automatically about every 60 seconds while the instrument is open. "
                "Exchange/Yahoo delays can apply; this is near-real-time rather than exchange-direct tick data."
            )


        def _investment_html(row: pd.Series) -> str:
            result = _investment_projection(row, investment_amount, include_current_ytd, investment_years)
            if result is None:
                return '<div class="investment-card"><span>Investment simulation</span><b>Needs completed calendar-year data</b></div>'
            if result.get("insufficient"):
                if result.get("requested_period") == "YTD":
                    return (
                        '<div class="investment-card"><span>Investment simulation • YTD</span>'
                        '<b>YTD return unavailable</b><small>No YTD profit was estimated.</small></div>'
                    )
                return (
                    '<div class="investment-card"><span>Investment simulation</span>'
                    f'<b>{result["requested_years"]}Y history unavailable</b>'
                    f'<small>Only {result["available_years"]} contiguous completed year(s) are available.</small></div>'
                )
            end_label = f"{now_et().year} YTD" if result["ytd_applied"] else result["end_year"]
            profit = result["profit"]
            profit_class = "pos" if profit > 0 else ("neg" if profit < 0 else "flat")
            return (
                '<div class="investment-card">'
                f'<span>${investment_amount:,.0f} invested • {("YTD only" if result.get("ytd_only") else result["start_year"] + " → " + end_label)}</span>'
                f'<b>${result["ending_value"]:,.2f}</b>'
                f'<small class="{profit_class}">Profit {profit:+,.2f} ({result["total_pct"]:+.2f}%)'
                f'{" • YTD" if result.get("ytd_only") else " • " + str(result["completed_years"]) + " full year(s)"}</small>'
                '</div>'
            )

        rows = list(card_rows.iterrows())
        for r0 in range(0, len(rows), 3):
            cols = st.columns(3)
            for c, (_, row) in zip(cols, rows[r0:r0+3]):
                symbol = str(row["Symbol"])
                price = f"${float(row['Price']):,.2f}" if pd.notna(row.get("Price")) else "—"
                name = _card_display_name(row)
                rating = str(row.get("Analyst Rating") or "Not Rated")
                signal = "LONG BUY" if bool(row.get("Long Buy")) else ("SHORT BUY" if bool(row.get("Short Buy")) else "")
                market_cap = pd.to_numeric(pd.Series([row.get("MarketCap")]), errors="coerce").iloc[0]
                cap_display = f"${market_cap / 1_000_000_000:,.0f}B" if pd.notna(market_cap) else "—"
                with c:
                    safe_card_symbol = ''.join(ch if ch.isalnum() else '_' for ch in symbol.upper())
                    # The complete information/profit area is inside one card boundary,
                    # while action buttons remain below it as in the v5.9.7 layout.
                    with st.container(border=True, key=f"market_card_{safe_card_symbol}"):
                        st.markdown(
                            _instrument_card_html(
                                row, price, cap_display, rating, signal,
                                logo_url=visible_logo_urls.get(symbol.upper(), ""),
                                chart_histories=visible_chart_histories,
                            ),
                            unsafe_allow_html=True,
                        )
                        render_card_profit_period_fragment(row.to_dict(), float(investment_amount), namespace="navigator")
                        st.markdown(_investment_html(row), unsafe_allow_html=True)
                        st.markdown(_card_bottom_html(rating, signal), unsafe_allow_html=True)

                    is_etf = str(row.get("Type") or "").strip().upper() == "ETF"
                    action_cols = st.columns(4 if is_etf else 3)
                    with action_cols[0]:
                        if st.button(f"Open {symbol}", key=f"open_{symbol}_{page_start}", use_container_width=True):
                            st.session_state.selected_symbol = symbol
                            st.session_state.scroll_to_chart = True
                            st.rerun()
                    with action_cols[1]:
                        news_open = st.session_state.news_symbol == symbol
                        if st.button(
                            "Hide News" if news_open else "📰 News",
                            key=f"news_{symbol}_{page_start}",
                            use_container_width=True,
                            type="primary" if news_open else "secondary",
                        ):
                            st.session_state.news_symbol = None if news_open else symbol
                            st.rerun()
                    if is_etf:
                        with action_cols[2]:
                            holdings_open = st.session_state.holdings_symbol == symbol
                            if st.button(
                                "Hide Holdings" if holdings_open else "◫ Holdings",
                                key=f"holdings_{symbol}_{page_start}",
                                use_container_width=True,
                                type="primary" if holdings_open else "secondary",
                            ):
                                st.session_state.holdings_symbol = None if holdings_open else symbol
                                st.rerun()
                        compare_col = action_cols[3]
                    else:
                        compare_col = action_cols[2]
                    with compare_col:
                        st.caption("Compare from the Stock & ETF Comparison tab")
                    if st.session_state.news_symbol == symbol:
                        with st.spinner(f"Checking recent fundamental news for {symbol}..."):
                            news_items = cached_recent_news(symbol, name, str(row.get("Type") or ""))
                        st.markdown(_news_panel_html(symbol, news_items), unsafe_allow_html=True)
                    if is_etf and st.session_state.holdings_symbol == symbol:
                        with st.spinner(f"Loading top holdings for {symbol}..."):
                            holdings_items = cached_etf_holdings(symbol)
                        st.markdown(_holdings_panel_html(symbol, holdings_items), unsafe_allow_html=True)

        # Duplicate pagination at the bottom of the card grid so mobile/desktop users
        # can move between pages without scrolling back to the top controls.
        st.markdown("<div class='bottom-pagination-label'>CARD PAGES</div>", unsafe_allow_html=True)
        bottom_page_cols = st.columns([1.2, 1.25, 2.6, 1.25, 1.2])
        with bottom_page_cols[0]:
            if st.button(
                "◀ Previous",
                key="prev_cards_bottom",
                use_container_width=True,
                disabled=st.session_state.card_page <= 0,
            ):
                st.session_state.card_page -= 1
                st.rerun()
        with bottom_page_cols[1]:
            st.markdown(
                f"<div class='page-chip'>Page {st.session_state.card_page + 1} of {pages}</div>",
                unsafe_allow_html=True,
            )
        with bottom_page_cols[3]:
            st.markdown(f"<div class='page-chip'>{len(filtered):,} results</div>", unsafe_allow_html=True)
        with bottom_page_cols[4]:
            if st.button(
                "Next ▶",
                key="next_cards_bottom",
                use_container_width=True,
                disabled=st.session_state.card_page >= pages - 1,
            ):
                st.session_state.card_page += 1
                st.rerun()

        selected = st.session_state.selected_symbol
        if selected and selected in set(market["Symbol"].astype(str)):
            detail_source = market.loc[market["Symbol"].astype(str) == selected].copy()
            detail_source = _hydrate_price_targets(detail_source, (selected,))
            detail_row = detail_source.iloc[0].copy()
            detail_price = f"${float(detail_row['Price']):,.2f}" if pd.notna(detail_row.get("Price")) else "—"
            detail_display_name = _card_display_name(detail_row)
            st.markdown(f"<div class='detail-header'><div><span class='detail-kicker'>INSTRUMENT INTELLIGENCE</span><h2>{selected}</h2><p>{escape(detail_display_name)}</p></div><div class='detail-price'>{detail_price}</div></div>", unsafe_allow_html=True)
            top = st.columns(4)
            top[0].metric("Analyst Rating", str(detail_row.get("Analyst Rating") or "Not Rated"))
            top[1].metric("Sector", str(detail_row.get("Sector") or "—"))
            top[2].metric("Short Signal", "BUY" if bool(detail_row.get("Short Buy")) else "—")
            top[3].metric("Long Signal", "BUY" if bool(detail_row.get("Long Buy")) else "—")

            if str(detail_row.get("Type") or "").strip().upper() == "STOCK":
                st.markdown("#### Analyst price targets")
                pt1, pt2, pt3, pt4 = st.columns(4)
                pt1.metric("Low target", _money_or_dash(detail_row.get("Price Target Low")))
                pt2.metric("Average target", _money_or_dash(detail_row.get("Price Target Average")))
                pt3.metric("High target", _money_or_dash(detail_row.get("Price Target High")))
                avg_target = pd.to_numeric(pd.Series([detail_row.get("Price Target Average")]), errors="coerce").iloc[0]
                current_price = pd.to_numeric(pd.Series([detail_row.get("Price")]), errors="coerce").iloc[0]
                implied = (float(avg_target) / float(current_price) - 1.0) * 100.0 if pd.notna(avg_target) and pd.notna(current_price) and float(current_price) > 0 else np.nan
                pt4.metric("Avg implied move", f"{implied:+.1f}%" if np.isfinite(implied) else "—")
                target_stamp = _valid_status_text(detail_row.get("Price Target Updated ET"))
                if target_stamp:
                    st.caption(f"Yahoo analyst target range • updated {target_stamp}")

            st.markdown("#### Performance matrix")
            st.markdown(_detail_performance_html(detail_row), unsafe_allow_html=True)

            st.markdown("#### Investment result")
            detail_projection = _investment_projection(detail_row, investment_amount, include_current_ytd, investment_years)
            if detail_projection and not detail_projection.get("insufficient"):
                d1, d2, d3, d4 = st.columns(4)
                d1.metric("Starting investment", f"${investment_amount:,.2f}")
                d2.metric("Estimated value", f"${detail_projection['ending_value']:,.2f}")
                d3.metric("Profit / loss", f"${detail_projection['profit']:+,.2f}")
                d4.metric("Total return", f"{detail_projection['total_pct']:+.2f}%")
                if detail_projection.get("ytd_only"):
                    st.caption(f"YTD-only calculation using the saved {now_et().year} adjusted YTD return. No CAGR or future-return assumption is used.")
                else:
                    st.caption(
                        f"Actual adjusted annual returns compounded from {detail_projection['start_year']} through {detail_projection['end_year']}"
                        + (f", then {now_et().year} YTD" if detail_projection["ytd_applied"] else "")
                        + f" • {detail_projection['completed_years']} completed calendar year(s)."
                    )
            elif detail_projection and detail_projection.get("insufficient"):
                if detail_projection.get("requested_period") == "YTD":
                    st.info("YTD was selected, but this instrument does not currently have a saved YTD return.")
                else:
                    st.info(
                        f"{investment_years} completed years were selected, but this instrument has only "
                        f"{detail_projection['available_years']} contiguous completed year(s) available."
                    )
            else:
                st.info("Completed calendar-year return data is required before the investment simulator can calculate this instrument.")

            st.markdown('<div id="instrument-chart-anchor" class="chart-scroll-anchor"></div>', unsafe_allow_html=True)
            st.markdown("#### Live intraday chart")
            render_live_intraday_chart(selected)

            st.markdown("#### Year-by-year historical chart")
            current_year = int(now_et().year)
            chart_year_options = chart_year_labels(as_of=now_et(), include_current=True)
            chart_year = st.segmented_control(
                "Chart year",
                chart_year_options,
                default=str(current_year),
                key=f"chart_year_{selected}",
                help=f"Choose the current year or any tracked calendar year back to {ANNUAL_HISTORY_FIRST_YEAR}. The graph and summary metrics update to that year only.",
            )
            selected_chart_year = int(chart_year or current_year)
            with st.spinner(f"Loading {selected} history for {selected_chart_year}..."):
                full_chart_history = cached_max_chart_history(selected)
            detail_hist = _filter_history_for_calendar_year(full_chart_history, selected_chart_year)
            chart_stats = _year_chart_stats(detail_hist)
            if chart_stats and "Close" in detail_hist:
                saved_return = detail_row.get("YTD") if selected_chart_year == current_year else detail_row.get(str(selected_chart_year))
                ch1, ch2, ch3, ch4, ch5 = st.columns(5)
                ch1.metric(f"{selected_chart_year} return", format_pct(saved_return))
                ch2.metric("Year start", f"${chart_stats['start']:,.2f}")
                ch3.metric("Latest / year end", f"${chart_stats['end']:,.2f}")
                ch4.metric("High close", f"${chart_stats['high']:,.2f}")
                ch5.metric("Low close", f"${chart_stats['low']:,.2f}")
                chart_series = pd.to_numeric(detail_hist["Close"], errors="coerce").dropna().rename("Adjusted Close")
                st.line_chart(chart_series, use_container_width=True, height=360)
                st.caption(
                    f"{selected} adjusted daily closes for calendar year {selected_chart_year} • "
                    f"{chart_stats['days']:,} trading-day observations. Selecting another year replaces both the graph and year summary."
                )
            else:
                st.info(f"No adjusted daily price history is available for {selected} in {selected_chart_year}.")

            # Open Instrument is a chart-first navigation action: after the chart has rendered,
            # move the browser to this section once. Subsequent year changes stay in place.
            if st.session_state.scroll_to_chart:
                st.session_state.scroll_to_chart = False
                components.html(
                    """
                    <script>
                    (() => {
                      const scroll = () => {
                        try {
                          const doc = window.parent.document;
                          const target = doc.getElementById('instrument-chart-anchor');
                          if (target) {
                            target.scrollIntoView({behavior: 'smooth', block: 'start'});
                            return;
                          }
                          window.parent.scrollTo({top: doc.body.scrollHeight, behavior: 'smooth'});
                        } catch (e) {
                          try { window.parent.scrollTo(0, 999999); } catch (_) {}
                        }
                      };
                      setTimeout(scroll, 120);
                      setTimeout(scroll, 650);
                    })();
                    </script>
                    """,
                    height=1,
                )
        else:
            st.info("Choose an instrument card to open its full short-horizon and {ANNUAL_HISTORY_YEARS}-calendar-year performance view.")



    with table_view_tab:
        st.markdown(
            "<div class='table-view-header'><span>MARKET TABLE</span><small>All currently filtered instruments • click any column header to sort interactively</small></div>",
            unsafe_allow_html=True,
        )
        table_df = view_filtered.copy()
        table_target_symbols = table_df.loc[
            table_df["Type"].astype(str).str.upper().eq("STOCK"), "Symbol"
        ].astype(str).tolist()
        table_df = _hydrate_price_targets(table_df, table_target_symbols)
        # Authoritative PDF handoff: any Low/Avg/High value visible in Market Table
        # is remembered verbatim and reused on Portfolio PDF page 1.
        _remember_price_targets(table_df, table_target_symbols, source_context="Market Table")

        # Add the same investment simulation result currently selected above so the
        # table can be ranked by estimated dollar profit as well as raw market data.
        sim_ending_values = []
        sim_profit_values = []
        sim_return_values = []
        withdrawal_remaining_values = []
        withdrawal_total_values = []
        withdrawal_net_values = []
        withdrawal_profit_values = []
        withdrawal_years_used = []
        withdrawal_years_funded = []
        for _, _row in table_df.iterrows():
            _projection = _portfolio_horizon_projection(
                _row,
                float(investment_amount),
                str(investment_period_choice),
                bool(include_current_ytd),
            )
            if not _projection or _projection.get("unavailable"):
                sim_ending_values.append(np.nan)
                sim_profit_values.append(np.nan)
                sim_return_values.append(np.nan)
            else:
                sim_ending_values.append(float(_projection.get("ending_value", np.nan)))
                sim_profit_values.append(float(_projection.get("profit", np.nan)))
                sim_return_values.append(float(_projection.get("return_pct", np.nan)))

            if market_table_withdrawals_enabled:
                _withdrawal_projection = _market_table_annual_withdrawal_projection(
                    _row,
                    float(investment_amount),
                    str(investment_period_choice),
                    float(market_table_annual_withdrawal),
                    bool(include_current_ytd),
                )
                if not _withdrawal_projection or _withdrawal_projection.get("unavailable"):
                    withdrawal_remaining_values.append(np.nan)
                    withdrawal_total_values.append(np.nan)
                    withdrawal_net_values.append(np.nan)
                    withdrawal_profit_values.append(np.nan)
                    withdrawal_years_used.append(np.nan)
                    withdrawal_years_funded.append(np.nan)
                else:
                    withdrawal_remaining_values.append(float(_withdrawal_projection.get("ending_balance", np.nan)))
                    withdrawal_total_values.append(float(_withdrawal_projection.get("total_withdrawn", np.nan)))
                    withdrawal_net_values.append(float(_withdrawal_projection.get("net_value_including_withdrawals", np.nan)))
                    withdrawal_profit_values.append(float(_withdrawal_projection.get("net_profit_including_withdrawals", np.nan)))
                    withdrawal_years_used.append(float(_withdrawal_projection.get("years_used", np.nan)))
                    withdrawal_years_funded.append(float(_withdrawal_projection.get("withdrawals_funded", np.nan)))
            else:
                withdrawal_remaining_values.append(np.nan)
                withdrawal_total_values.append(np.nan)
                withdrawal_net_values.append(np.nan)
                withdrawal_profit_values.append(np.nan)
                withdrawal_years_used.append(np.nan)
                withdrawal_years_funded.append(np.nan)

        table_df["Market Cap ($B)"] = pd.to_numeric(table_df.get("MarketCap"), errors="coerce") / 1_000_000_000
        table_df["Simulation Period"] = timeframe_display_label(investment_period_choice)
        table_df["Investment Amount ($)"] = float(investment_amount)
        table_df["Estimated Value ($)"] = sim_ending_values
        table_df["Profit / Loss ($)"] = sim_profit_values
        table_df["Simulation Return %"] = sim_return_values
        table_df["Withdrawal / Year ($)"] = (
            float(market_table_annual_withdrawal) if market_table_withdrawals_enabled else np.nan
        )
        table_df["Withdrawal Years Used"] = withdrawal_years_used
        table_df["Withdrawals Fully Funded"] = withdrawal_years_funded
        table_df["Total Withdrawn ($)"] = withdrawal_total_values
        table_df["Remaining After Withdrawals ($)"] = withdrawal_remaining_values
        table_df["Net Value incl. Withdrawals ($)"] = withdrawal_net_values
        table_df["Net Profit incl. Withdrawals ($)"] = withdrawal_profit_values

        # v5.9.44: expose the weakest completed calendar year in Market Table View.
        # Uses the same actual annual-return columns shown in cards; missing pre-IPO
        # years are ignored rather than treated as zero.
        table_df["Worst Year"] = table_df.apply(worst_completed_year_label, axis=1)

        # Average analyst target implied move is useful in table view but remains
        # stock-only; ETF values stay blank rather than being fabricated.
        _avg_target = pd.to_numeric(table_df.get("Price Target Average"), errors="coerce")
        _price = pd.to_numeric(table_df.get("Price"), errors="coerce")
        table_df["Avg Target Implied %"] = np.where(
            (_avg_target.notna()) & (_price.notna()) & (_price > 0),
            (_avg_target / _price - 1.0) * 100.0,
            np.nan,
        )

        TABLE_COLUMNS = [
            "Symbol", "Name", "Type", "Sector", "Industry", "Price", "Market Cap ($B)",
            "Price Target Low", "Price Target Average", "Price Target High", "Avg Target Implied %",
            "Price Target Source", "Price Target Updated ET",
            "Analyst Rating", "Worst Year", "History Verification", "Verification Coverage",
            "Verification Discrepancies", "Max Verification Diff (pp)", "Verification Exceptions",
            "Short Buy", "Long Buy", "Fundamental Buy",
            *PERF_COLS,
            "Simulation Period", "Investment Amount ($)", "Estimated Value ($)", "Profit / Loss ($)", "Simulation Return %",
            "Withdrawal / Year ($)", "Withdrawal Years Used", "Withdrawals Fully Funded",
            "Total Withdrawn ($)", "Remaining After Withdrawals ($)",
            "Net Value incl. Withdrawals ($)", "Net Profit incl. Withdrawals ($)",
            "Signal Reasons",
        ]
        for _col in TABLE_COLUMNS:
            if _col not in table_df.columns:
                table_df[_col] = pd.NA
        table_df = table_df[TABLE_COLUMNS].copy()

        # Explicit table sorting complements Streamlit's native click-the-header sort.
        table_sort_options = [
            "Symbol", "Name", "Price", "Market Cap ($B)", "Analyst Rating", "Worst Year", "History Verification",
            "Price Target Average", "Avg Target Implied %", "Profit / Loss ($)", "Simulation Return %",
            "Remaining After Withdrawals ($)", "Net Profit incl. Withdrawals ($)",
            *PERF_COLS,
        ]
        # v5.9.78: Table View uses the same searchable multiselect dropdown
        # behavior as Portfolio Simulator / Stock & ETF Comparison.
        _table_search_rows = table_df.copy()
        _table_search_rows["Symbol"] = _table_search_rows["Symbol"].astype(str).str.upper().str.strip()
        _table_search_rows = _table_search_rows.drop_duplicates("Symbol", keep="last")
        _table_search_options = sorted(_table_search_rows["Symbol"].tolist())
        _table_search_lookup = (
            _table_search_rows.set_index("Symbol").to_dict(orient="index")
            if not _table_search_rows.empty else {}
        )
        _table_valid_set = set(_table_search_options)
        _table_saved_selection = [
            str(symbol).upper()
            for symbol in st.session_state.get("table_local_search_selector", [])
            if str(symbol).upper() in _table_valid_set
        ]
        if _table_saved_selection != list(st.session_state.get("table_local_search_selector", [])):
            st.session_state.table_local_search_selector = _table_saved_selection

        ts1, ts_search, ts2, ts3 = st.columns([2.0, 2.55, 1.5, 2.95])
        with ts1:
            table_sort_choice = st.selectbox(
                "Sort table by",
                table_sort_options,
                index=table_sort_options.index("Market Cap ($B)"),
                key="table_sort_choice",
                format_func=timeframe_display_label,
            )
        with ts_search:
            table_local_selection = st.multiselect(
                "Search / select stocks & ETFs",
                options=_table_search_options,
                key="table_local_search_selector",
                format_func=lambda symbol: (
                    f"{symbol} — {_table_search_lookup.get(symbol, {}).get('Name', symbol)}"
                    + (f" • {_table_search_lookup.get(symbol, {}).get('Type')}"
                       if str(_table_search_lookup.get(symbol, {}).get('Type') or '').strip() not in {'', 'Unknown', 'nan'} else "")
                    + (f" • {_table_search_lookup.get(symbol, {}).get('Sector')}"
                       if str(_table_search_lookup.get(symbol, {}).get('Sector') or '').strip() not in {'', 'Unknown', 'nan'} else "")
                ),
                placeholder="Search ticker, company / ETF name, type, or sector…",
                help=(
                    "Type directly in this dropdown and select one or more stocks/ETFs. "
                    "Leave it empty to show every currently filtered Table View instrument."
                ),
            )
        with ts2:
            table_sort_direction = st.segmented_control(
                "Order",
                ["High → Low", "Low → High"],
                default="High → Low",
                key="table_sort_direction",
            )
        with ts3:
            st.caption(
                "Use these controls for a default ranking, or click any table column header for an instant interactive re-sort. "
                f"Profit columns use ${investment_amount:,.2f} and the currently selected {investment_period_choice} simulator period. "
                + (
                    f"Withdrawal columns use ${market_table_annual_withdrawal:,.2f}/year against the exact displayed annual returns."
                    if market_table_withdrawals_enabled else
                    "Enable Table yearly withdrawal above to add recurring-withdrawal results."
                )
            )

        _table_selected_symbols = list(dict.fromkeys(str(symbol).upper() for symbol in table_local_selection))
        if _table_selected_symbols:
            table_df = table_df.loc[
                table_df["Symbol"].astype(str).str.upper().isin(_table_selected_symbols)
            ].copy()
            st.caption(
                f"Table View selection: {len(_table_selected_symbols):,} instrument(s). "
                "Remove selections from the dropdown to return to the full filtered Table View universe."
            )

        _table_ascending = table_sort_direction == "Low → High"
        if table_sort_choice == "Analyst Rating":
            _rating_rank = {"Strong Buy": 5, "Buy": 4, "Hold": 3, "Sell": 2, "Strong Sell": 1, "Not Rated": 0}
            table_df = (
                table_df.assign(_table_rating_sort=table_df["Analyst Rating"].map(_rating_rank).fillna(0))
                .sort_values(["_table_rating_sort", "Market Cap ($B)"], ascending=[_table_ascending, False], na_position="last")
                .drop(columns="_table_rating_sort")
            )
        else:
            table_df = table_df.sort_values(table_sort_choice, ascending=_table_ascending, na_position="last")

        # Use column configuration for readable numbers while keeping the underlying
        # values numeric, so native dataframe sorting continues to work correctly.
        table_column_config = {
            "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
            "Market Cap ($B)": st.column_config.NumberColumn("Market Cap ($B)", format="$%.2fB"),
            "Worst Year": st.column_config.TextColumn("Worst Year"),
            "History Verification": st.column_config.TextColumn("History Check"),
            "Verification Coverage": st.column_config.TextColumn("Verified Coverage"),
            "Verification Discrepancies": st.column_config.NumberColumn("Review Years", format="%d"),
            "Max Verification Diff (pp)": st.column_config.NumberColumn("Max Δ (pp)", format="%.2f"),
            "Verification Exceptions": st.column_config.TextColumn("Verification Exceptions"),
            "Price Target Low": st.column_config.NumberColumn("Target Low", format="$%.2f"),
            "Price Target Average": st.column_config.NumberColumn("Target Avg", format="$%.2f"),
            "Price Target High": st.column_config.NumberColumn("Target High", format="$%.2f"),
            "Avg Target Implied %": st.column_config.NumberColumn("Avg Target Implied", format="%.2f%%"),
            "Price Target Source": st.column_config.TextColumn("Target Source"),
            "Price Target Updated ET": st.column_config.TextColumn("Target Updated ET"),
            "Investment Amount ($)": st.column_config.NumberColumn("Investment", format="$%.2f"),
            "Estimated Value ($)": st.column_config.NumberColumn("Est. Value", format="$%.2f"),
            "Profit / Loss ($)": st.column_config.NumberColumn("Profit / Loss", format="$%.2f"),
            "Simulation Return %": st.column_config.NumberColumn("Simulation Return", format="%.2f%%"),
            "Withdrawal / Year ($)": st.column_config.NumberColumn("Withdraw / Yr", format="$%.2f"),
            "Withdrawal Years Used": st.column_config.NumberColumn("Return Years Used", format="%d"),
            "Withdrawals Fully Funded": st.column_config.NumberColumn("Withdrawals Funded", format="%d"),
            "Total Withdrawn ($)": st.column_config.NumberColumn("Total Withdrawn", format="$%.2f"),
            "Remaining After Withdrawals ($)": st.column_config.NumberColumn("Remaining After Withdrawals", format="$%.2f"),
            "Net Value incl. Withdrawals ($)": st.column_config.NumberColumn("Net Value incl. Withdrawals", format="$%.2f"),
            "Net Profit incl. Withdrawals ($)": st.column_config.NumberColumn("Net Profit incl. Withdrawals", format="$%.2f"),
            "Short Buy": st.column_config.CheckboxColumn("Short Buy"),
            "Long Buy": st.column_config.CheckboxColumn("Long Buy"),
            "Fundamental Buy": st.column_config.CheckboxColumn("Fundamental Buy"),
        }
        for _perf_col in PERF_COLS:
            table_column_config[_perf_col] = st.column_config.NumberColumn(_perf_col, format="%.2f%%")

        table_column_config.update(timeframe_column_config([c for c in PERF_COLS if c in table_df.columns]))
        table_event = st.dataframe(
            table_df,
            use_container_width=True,
            hide_index=True,
            height=760,
            column_config=table_column_config,
            on_select="rerun",
            selection_mode="multi-row",
            key="market_table_selectable",
        )
        selected_table_rows = []
        try:
            selected_table_rows = list(table_event.selection.rows)
        except Exception:
            selected_table_rows = []
        st.caption(
            "To add or remove comparison instruments, use the single searchable selector in the Stock & ETF Comparison tab."
        )
        st.caption(
            f"Table View contains {len(table_df):,} instrument(s) after the same filters used by Card View. "
            "History Check compares Yahoo/yfinance annual returns with independent Stooq bulk historical Close data. "
            "A Review flag means at least one compared year differs by more than 0.25 percentage points; Yahoo remains the primary calculation source."
        )


def _commit_stock_compare_selector() -> None:
    """Make the comparison selector the authoritative source of comparison membership."""
    values = st.session_state.get("stock_compare_selector", []) or []
    selected = list(dict.fromkeys(str(x).strip().upper() for x in values if str(x).strip()))
    st.session_state.compare_symbols = selected
    st.session_state.compare_page = 0


with compare_tab:
    # v5.9.21: the searchable multiselect below is the single source of truth for
    # choosing comparison instruments. Card/Table actions and the separate enhanced
    # search box were intentionally removed to keep the workflow unambiguous on phones.
    st.markdown(
        "<div class='comparison-workspace-header'><span>⚖ STOCK & ETF COMPARISON</span>"
        "<small>Choose every comparison instrument from the selector below.</small></div>",
        unsafe_allow_html=True,
    )
    if st.session_state.comparison_search_message:
        _cmp_ok, _cmp_msg = st.session_state.comparison_search_message
        (st.success if _cmp_ok else st.warning)(_cmp_msg)
        st.session_state.comparison_search_message = None

    all_compare_rows = market.copy()
    all_compare_rows["Symbol"] = all_compare_rows["Symbol"].astype(str).str.upper().str.strip()
    all_compare_rows = all_compare_rows.drop_duplicates("Symbol", keep="last")
    all_compare_symbols = sorted(all_compare_rows["Symbol"].tolist())
    compare_lookup = all_compare_rows.set_index("Symbol").to_dict(orient="index") if not all_compare_rows.empty else {}

    # Drop only truly stale symbols. v5.9.23 IMPORTANT: do not overwrite the
    # multiselect widget here. Streamlit applies widget changes before the rerun;
    # resetting stock_compare_selector from the older compare_symbols value at this
    # point erased every new phone/desktop selection before it could render.
    valid_symbol_set = set(all_compare_symbols)
    valid_compare_symbols = [
        symbol for symbol in list(dict.fromkeys(str(x).upper() for x in st.session_state.compare_symbols))
        if symbol in valid_symbol_set
    ]
    if valid_compare_symbols != list(st.session_state.compare_symbols):
        st.session_state.compare_symbols = valid_compare_symbols
    # Keep the widget clean only when it contains symbols that no longer exist.
    widget_symbols = [
        symbol for symbol in list(dict.fromkeys(str(x).upper() for x in st.session_state.get("stock_compare_selector", [])))
        if symbol in valid_symbol_set
    ]
    if widget_symbols != list(st.session_state.get("stock_compare_selector", [])):
        st.session_state.stock_compare_selector = widget_symbols

    st.caption(
        f"{len(st.session_state.compare_symbols):,} instrument(s) selected • unlimited selection • "
        "type a ticker, company/fund name, asset type, or sector directly inside this selector to filter choices."
    )
    compare_selector = st.multiselect(
        "Stocks & ETFs to compare (unlimited selection)",
        options=all_compare_symbols,
        key="stock_compare_selector",
        format_func=lambda symbol: (
            f"{symbol} — {compare_lookup.get(symbol, {}).get('Name', symbol)}"
            + (f" • {compare_lookup.get(symbol, {}).get('Type')}" if str(compare_lookup.get(symbol, {}).get('Type') or '').strip() not in {'', 'Unknown', 'nan'} else "")
            + (f" • {compare_lookup.get(symbol, {}).get('Sector')}" if str(compare_lookup.get(symbol, {}).get('Sector') or '').strip() not in {'', 'Unknown', 'nan'} else "")
        ),
        placeholder="Search ticker, company/fund name, type, or sector…",
        help="This is the only control that adds or removes instruments from Stock & ETF Comparison.",
        on_change=_commit_stock_compare_selector,
    )
    # Defensive sync for Streamlit versions where a programmatic widget change can
    # bypass on_change. Never write the old compare state back into the widget.
    selector_symbols = list(dict.fromkeys(str(x).upper() for x in compare_selector))
    if selector_symbols != list(st.session_state.compare_symbols):
        st.session_state.compare_symbols = selector_symbols
        st.session_state.compare_page = 0

    comparison_symbols = [s for s in st.session_state.compare_symbols if s in valid_symbol_set]
    if not comparison_symbols:
        st.info("Add two or more stocks and/or ETFs to build a comparison. You can still compare a single instrument while assembling the set.")
    else:
        comparison_df = all_compare_rows.loc[all_compare_rows["Symbol"].isin(comparison_symbols)].copy()
        comparison_df = _hydrate_price_targets(comparison_df, comparison_symbols)
        comparison_df["_compare_order"] = comparison_df["Symbol"].map({s: i for i, s in enumerate(comparison_symbols)})
        comparison_df = comparison_df.sort_values("_compare_order").drop(columns="_compare_order")
        # Legacy logo path: _comparison_logo_html(symbol, comparison_logo_urls.get(symbol, ""))
        comparison_logo_urls = cached_logo_urls(tuple(comparison_symbols))
        # Comparison cards must load chart data for the selected comparison set itself.
        # v5.9.27 incorrectly reused the current Market Navigator page's history map,
        # which made charts unavailable whenever a selected symbol was not on that page.
        comparison_chart_histories = cached_card_two_year_histories(tuple(comparison_symbols))

        compare_cards_tab, compare_table_tab = st.tabs(["▦ Comparison Cards", "▤ Comparison Table"])

        with compare_cards_tab:
            COMPARE_CARDS_PER_PAGE = 12
            compare_pages = max(1, (len(comparison_df) + COMPARE_CARDS_PER_PAGE - 1) // COMPARE_CARDS_PER_PAGE)
            if st.session_state.compare_page >= compare_pages:
                st.session_state.compare_page = 0
            cc_nav = st.columns([1.1, 1.3, 3.0, 1.3, 1.1])
            with cc_nav[0]:
                if st.button("◀", key="compare_prev", use_container_width=True, disabled=st.session_state.compare_page <= 0):
                    st.session_state.compare_page -= 1
                    st.rerun()
            with cc_nav[1]:
                st.markdown(
                    f"<div class='page-chip'>Page {st.session_state.compare_page + 1} of {compare_pages}</div>",
                    unsafe_allow_html=True,
                )
            with cc_nav[3]:
                st.markdown(f"<div class='page-chip'>{len(comparison_df):,} instruments</div>", unsafe_allow_html=True)
            with cc_nav[4]:
                if st.button("▶", key="compare_next", use_container_width=True, disabled=st.session_state.compare_page >= compare_pages - 1):
                    st.session_state.compare_page += 1
                    st.rerun()

            compare_start = st.session_state.compare_page * COMPARE_CARDS_PER_PAGE
            compare_rows = list(comparison_df.iloc[compare_start:compare_start + COMPARE_CARDS_PER_PAGE].iterrows())
            for r0 in range(0, len(compare_rows), 3):
                card_cols = st.columns(3)
                for card_col, (_, row) in zip(card_cols, compare_rows[r0:r0+3]):
                    symbol = str(row.get("Symbol") or "")
                    price = f"${float(row['Price']):,.2f}" if pd.notna(row.get("Price")) else "—"
                    market_cap = pd.to_numeric(pd.Series([row.get("MarketCap")]), errors="coerce").iloc[0]
                    cap_display = f"${market_cap / 1_000_000_000:,.0f}B" if pd.notna(market_cap) else "—"
                    rating = str(row.get("Analyst Rating") or "Not Rated")
                    signal = "LONG BUY" if bool(row.get("Long Buy")) else ("SHORT BUY" if bool(row.get("Short Buy")) else "")
                    with card_col:
                        safe_compare_symbol = ''.join(ch if ch.isalnum() else '_' for ch in symbol.upper())
                        with st.container(border=True, key=f"comparison_card_{safe_compare_symbol}"):
                            st.markdown(
                                _instrument_card_html(
                                    row, price, cap_display, rating, signal,
                                    logo_url=comparison_logo_urls.get(symbol.upper(), ""),
                                    chart_histories=comparison_chart_histories,
                                ),
                                unsafe_allow_html=True,
                            )
                            render_card_profit_period_fragment(row.to_dict(), float(investment_amount), namespace="comparison")
                            st.markdown(_investment_html(row), unsafe_allow_html=True)
                            st.markdown(_card_bottom_html(rating, signal), unsafe_allow_html=True)

                        is_etf = str(row.get("Type") or "").strip().upper() == "ETF"
                        action_cols = st.columns(4 if is_etf else 3)
                        with action_cols[0]:
                            detail_open = st.session_state.comparison_detail_symbol == symbol
                            if st.button(
                                "Hide Details" if detail_open else "Open Full Details",
                                key=f"compare_detail_{symbol}_{compare_start}",
                                use_container_width=True,
                                type="primary" if detail_open else "secondary",
                            ):
                                st.session_state.comparison_detail_symbol = None if detail_open else symbol
                                st.rerun()
                        with action_cols[1]:
                            news_open = st.session_state.news_symbol == symbol
                            if st.button(
                                "Hide News" if news_open else "📰 News",
                                key=f"compare_news_{symbol}_{compare_start}",
                                use_container_width=True,
                                type="primary" if news_open else "secondary",
                            ):
                                st.session_state.news_symbol = None if news_open else symbol
                                st.rerun()
                        if is_etf:
                            with action_cols[2]:
                                holdings_open = st.session_state.holdings_symbol == symbol
                                if st.button(
                                    "Hide Holdings" if holdings_open else "◫ Holdings",
                                    key=f"compare_holdings_{symbol}_{compare_start}",
                                    use_container_width=True,
                                    type="primary" if holdings_open else "secondary",
                                ):
                                    st.session_state.holdings_symbol = None if holdings_open else symbol
                                    st.rerun()
                            remove_col = action_cols[3]
                        else:
                            remove_col = action_cols[2]
                        with remove_col:
                            if st.button(
                                f"Remove {symbol}",
                                key=f"remove_compare_{symbol}_{compare_start}",
                                use_container_width=True,
                            ):
                                updated = [x for x in st.session_state.compare_symbols if x != symbol]
                                st.session_state.compare_symbols = updated
                                st.session_state.stock_compare_selector = updated
                                st.session_state.compare_page = 0
                                st.rerun()

                    if st.session_state.news_symbol == symbol:
                        with card_col:
                            with st.spinner(f"Checking recent fundamental news for {symbol}..."):
                                news_items = cached_recent_news(symbol, _card_display_name(row), str(row.get("Type") or ""))
                            st.markdown(_news_panel_html(symbol, news_items), unsafe_allow_html=True)
                    if is_etf and st.session_state.holdings_symbol == symbol:
                        with card_col:
                            with st.spinner(f"Loading top holdings for {symbol}..."):
                                holdings_items = cached_etf_holdings(symbol)
                            st.markdown(_holdings_panel_html(symbol, holdings_items), unsafe_allow_html=True)

            comparison_detail_symbol = st.session_state.comparison_detail_symbol
            if comparison_detail_symbol and comparison_detail_symbol in set(comparison_df["Symbol"].astype(str)):
                detail_row = comparison_df.loc[comparison_df["Symbol"].astype(str) == comparison_detail_symbol].iloc[0].copy()
                detail_price = f"${float(detail_row['Price']):,.2f}" if pd.notna(detail_row.get("Price")) else "—"
                st.markdown(
                    f"<div class='detail-header'><div><span class='detail-kicker'>COMPARISON INSTRUMENT INTELLIGENCE</span><h2>{escape(comparison_detail_symbol)}</h2><p>{escape(_card_display_name(detail_row))}</p></div><div class='detail-price'>{escape(detail_price)}</div></div>",
                    unsafe_allow_html=True,
                )
                d1, d2, d3, d4 = st.columns(4)
                d1.metric("Analyst Rating", str(detail_row.get("Analyst Rating") or "Not Rated"))
                d2.metric("Sector", str(detail_row.get("Sector") or "—"))
                d3.metric("Short Signal", "BUY" if bool(detail_row.get("Short Buy")) else "—")
                d4.metric("Long Signal", "BUY" if bool(detail_row.get("Long Buy")) else "—")
                if str(detail_row.get("Type") or "").strip().upper() == "STOCK":
                    pt1, pt2, pt3, pt4 = st.columns(4)
                    pt1.metric("Low target", _money_or_dash(detail_row.get("Price Target Low")))
                    pt2.metric("Average target", _money_or_dash(detail_row.get("Price Target Average")))
                    pt3.metric("High target", _money_or_dash(detail_row.get("Price Target High")))
                    avg_t = pd.to_numeric(pd.Series([detail_row.get("Price Target Average")]), errors="coerce").iloc[0]
                    cur_p = pd.to_numeric(pd.Series([detail_row.get("Price")]), errors="coerce").iloc[0]
                    implied = (float(avg_t)/float(cur_p)-1)*100 if pd.notna(avg_t) and pd.notna(cur_p) and float(cur_p)>0 else np.nan
                    pt4.metric("Avg target implied", f"{implied:+.2f}%" if np.isfinite(implied) else "—")
                st.markdown("#### Complete return history")
                st.markdown(_detail_performance_html(detail_row), unsafe_allow_html=True)
                st.markdown("#### Live intraday chart")
                render_live_intraday_chart(comparison_detail_symbol)
                current_year = int(now_et().year)
                compare_chart_year = st.segmented_control(
                    "Comparison chart year",
                    chart_year_labels(as_of=now_et(), include_current=True),
                    default=str(current_year),
                    key=f"compare_chart_year_{comparison_detail_symbol}",
                )
                selected_compare_year = int(compare_chart_year or current_year)
                full_compare_history = cached_max_chart_history(comparison_detail_symbol)
                compare_hist = _filter_history_for_calendar_year(full_compare_history, selected_compare_year)
                compare_stats = _year_chart_stats(compare_hist)
                if compare_stats and "Close" in compare_hist:
                    st.line_chart(pd.to_numeric(compare_hist["Close"], errors="coerce").dropna().rename("Adjusted Close"), use_container_width=True, height=360)
                    st.caption(f"{comparison_detail_symbol} adjusted daily closes for {selected_compare_year}.")
                else:
                    st.info(f"No adjusted daily price history is available for {comparison_detail_symbol} in {selected_compare_year}.")

        with compare_table_tab:
            comp_table = comparison_df.copy()
            comp_table["Market Cap ($B)"] = pd.to_numeric(comp_table.get("MarketCap"), errors="coerce") / 1_000_000_000
            comp_avg_target = pd.to_numeric(comp_table.get("Price Target Average"), errors="coerce")
            comp_price = pd.to_numeric(comp_table.get("Price"), errors="coerce")
            comp_table["Avg Target Implied %"] = np.where(
                comp_avg_target.notna() & comp_price.notna() & (comp_price > 0),
                (comp_avg_target / comp_price - 1.0) * 100.0,
                np.nan,
            )
            comp_ending = []
            comp_profit = []
            comp_sim_return = []
            for _, comp_row in comp_table.iterrows():
                projection = _portfolio_horizon_projection(
                    comp_row,
                    float(investment_amount),
                    str(investment_period_choice),
                    bool(include_current_ytd),
                )
                if not projection or projection.get("unavailable"):
                    comp_ending.append(np.nan)
                    comp_profit.append(np.nan)
                    comp_sim_return.append(np.nan)
                else:
                    comp_ending.append(float(projection.get("ending_value", np.nan)))
                    comp_profit.append(float(projection.get("profit", np.nan)))
                    comp_sim_return.append(float(projection.get("return_pct", np.nan)))
            comp_table["Simulation Period"] = timeframe_display_label(investment_period_choice)
            comp_table["Investment Amount ($)"] = float(investment_amount)
            comp_table["Estimated Value ($)"] = comp_ending
            comp_table["Profit / Loss ($)"] = comp_profit
            comp_table["Simulation Return %"] = comp_sim_return
            comp_table["Logo"] = comp_table["Symbol"].map(lambda x: comparison_logo_urls.get(str(x).upper(), ""))

            comparison_columns = [
                "Logo", "Symbol", "Name", "Sector", "Industry", "Price", "Market Cap ($B)",
                "Analyst Rating", "Price Target Low", "Price Target Average", "Price Target High", "Avg Target Implied %",
                "Price Target Source", "Price Target Updated ET",
                "Short Buy", "Long Buy", "Fundamental Buy", *PERF_COLS,
                "Simulation Period", "Investment Amount ($)", "Estimated Value ($)", "Profit / Loss ($)", "Simulation Return %",
                "Signal Reasons",
            ]
            for comp_col in comparison_columns:
                if comp_col not in comp_table.columns:
                    comp_table[comp_col] = pd.NA
            comp_table = comp_table[comparison_columns].copy()

            comp_sort_options = [
                "Symbol", "Name", "Sector", "Industry", "Price", "Market Cap ($B)", "Analyst Rating",
                "Price Target Average", "Avg Target Implied %", "Profit / Loss ($)", "Simulation Return %", *PERF_COLS,
            ]
            cs1, cs2, cs3 = st.columns([2.2, 1.7, 3.5])
            with cs1:
                comp_sort_choice = st.selectbox(
                    "Sort comparison by",
                    comp_sort_options,
                    index=comp_sort_options.index("Market Cap ($B)"),
                    key="comparison_table_sort_choice",
                    format_func=timeframe_display_label,
                )
            with cs2:
                comp_sort_direction = st.segmented_control(
                    "Order",
                    ["High → Low", "Low → High"],
                    default="High → Low",
                    key="comparison_table_sort_direction",
                )
            with cs3:
                st.caption(
                    "The comparison table includes every selected stock/ETF and all current performance periods. Click any column header for another interactive sort."
                )
            comp_ascending = comp_sort_direction == "Low → High"
            if comp_sort_choice == "Analyst Rating":
                rating_rank = {"Strong Buy": 5, "Buy": 4, "Hold": 3, "Sell": 2, "Strong Sell": 1, "Not Rated": 0}
                comp_table = (
                    comp_table.assign(_compare_rating_sort=comp_table["Analyst Rating"].map(rating_rank).fillna(0))
                    .sort_values(["_compare_rating_sort", "Market Cap ($B)"], ascending=[comp_ascending, False], na_position="last")
                    .drop(columns="_compare_rating_sort")
                )
            else:
                comp_table = comp_table.sort_values(comp_sort_choice, ascending=comp_ascending, na_position="last")

            comp_column_config = {
                "Logo": st.column_config.ImageColumn("Logo", width="small", help="Instrument logo retrieved from Yahoo/company metadata when available."),
                "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "Market Cap ($B)": st.column_config.NumberColumn("Market Cap ($B)", format="$%.2fB"),
                "Price Target Low": st.column_config.NumberColumn("Target Low", format="$%.2f"),
                "Price Target Average": st.column_config.NumberColumn("Target Avg", format="$%.2f"),
                "Price Target High": st.column_config.NumberColumn("Target High", format="$%.2f"),
                "Avg Target Implied %": st.column_config.NumberColumn("Avg Target Implied", format="%.2f%%"),
                "Price Target Source": st.column_config.TextColumn("Target Source"),
                "Price Target Updated ET": st.column_config.TextColumn("Target Updated ET"),
                "Investment Amount ($)": st.column_config.NumberColumn("Investment", format="$%.2f"),
                "Estimated Value ($)": st.column_config.NumberColumn("Est. Value", format="$%.2f"),
                "Profit / Loss ($)": st.column_config.NumberColumn("Profit / Loss", format="$%.2f"),
                "Simulation Return %": st.column_config.NumberColumn("Simulation Return", format="%.2f%%"),
                "Short Buy": st.column_config.CheckboxColumn("Short Buy"),
                "Long Buy": st.column_config.CheckboxColumn("Long Buy"),
                "Fundamental Buy": st.column_config.CheckboxColumn("Fundamental Buy"),
            }
            for perf_col in PERF_COLS:
                comp_column_config[perf_col] = st.column_config.NumberColumn(perf_col, format="%.2f%%")

            comp_column_config.update(timeframe_column_config([c for c in PERF_COLS if c in comp_table.columns]))
            st.dataframe(
                comp_table,
                use_container_width=True,
                hide_index=True,
                height=min(840, 86 + max(1, len(comp_table)) * 35),
                column_config=comp_column_config,
                key="instrument_comparison_table",
            )

with sector_tab:
    st.markdown("### ◈ Stock Sector Performance")
    st.caption(
        "Stocks only. Each sector card combines every tracked stock in that sector. "
        "Default is equal-weight average return so one mega-cap stock cannot dominate the sector result."
    )

    sector_stocks = market.loc[market["Type"].astype(str).str.upper().eq("STOCK")].copy()
    if sector_stocks.empty:
        st.info("No stock sector data is available in the current MarketScope snapshot.")
    else:
        sector_weighting = st.segmented_control(
            "Sector aggregation",
            ["Equal weight", "Market-cap weighted"],
            default="Equal weight",
            key="sector_performance_weighting",
            help="Equal weight averages every stock return equally. Market-cap weighted gives larger companies more influence.",
        )
        sector_sort_period = st.selectbox(
            "Rank sectors by",
            PERF_COLS,
            index=PERF_COLS.index("YTD") if "YTD" in PERF_COLS else 0,
            key="sector_performance_sort_period",
        )

        if "sector_drilldown" not in st.session_state:
            st.session_state.sector_drilldown = None

        def _aggregate_sector_return(group: pd.DataFrame, metric: str, weighting: str) -> float:
            vals = pd.to_numeric(group.get(metric), errors="coerce")
            valid = vals.notna() & np.isfinite(vals)
            if not valid.any():
                return np.nan
            vals = vals.loc[valid].astype(float)
            if weighting == "Market-cap weighted":
                weights = pd.to_numeric(group.loc[valid, "MarketCap"], errors="coerce").fillna(0).clip(lower=0)
                positive = weights > 0
                if positive.any() and float(weights.loc[positive].sum()) > 0:
                    return float(np.average(vals.loc[positive], weights=weights.loc[positive]))
            return float(vals.mean())

        sector_rows = []
        for sector_name, group in sector_stocks.groupby("Sector", dropna=False):
            sector_name = str(sector_name or "Unknown").strip() or "Unknown"
            record = {
                "Sector": sector_name,
                "Stocks": int(len(group)),
                "MarketCap": float(pd.to_numeric(group.get("MarketCap"), errors="coerce").fillna(0).sum()),
            }
            for metric in PERF_COLS:
                record[metric] = _aggregate_sector_return(group, metric, str(sector_weighting))
            latest_ratings = group.get("Analyst Rating", pd.Series(index=group.index, dtype=object)).astype(str)
            bullish = latest_ratings.isin(["Strong Buy", "Buy"]).sum()
            record["Bullish Ratings %"] = (float(bullish) / len(group) * 100.0) if len(group) else np.nan
            positive_vals = pd.to_numeric(group.get(sector_sort_period), errors="coerce")
            valid_pos = positive_vals.notna() & np.isfinite(positive_vals)
            record["Positive Breadth %"] = (
                float((positive_vals.loc[valid_pos] > 0).mean() * 100.0) if valid_pos.any() else np.nan
            )
            sector_rows.append(record)

        sector_df = pd.DataFrame(sector_rows)
        sector_df = sector_df.sort_values(sector_sort_period, ascending=False, na_position="last").reset_index(drop=True)
        st.caption(
            f"{len(sector_df)} stock sectors • {len(sector_stocks)} tracked stocks • ranked by {sector_sort_period} • {sector_weighting.lower()}"
        )

        # v5.9.32: TOTAL STOCKS is the drill-down control. The popover keeps the details
        # inside the Sector Performance screen and lets the user recalculate profit by timeframe.
        def _render_sector_top_performers_popover(drill_sector: str, key_suffix: str) -> None:
            drill = sector_stocks.loc[sector_stocks["Sector"].astype(str).eq(str(drill_sector))].copy()
            if drill.empty:
                st.info("No stocks are available for this sector in the current MarketScope snapshot.")
                return

            st.markdown(f"#### {drill_sector} · Top Performers")
            st.caption("Tap a timeframe below to re-rank stocks and recalculate Total Profit / Total Profit %. The table shows short-period returns plus each completed calendar year as a standalone annual return (not compounded).")
            timeframe_options = ["1D", "1M", "3M", "6M", "YTD", *ANNUAL_HORIZON_OPTIONS]
            tf_key = f"sector_profit_timeframe_{key_suffix}"
            default_tf = str(st.session_state.get(tf_key) or sector_sort_period or "YTD")
            if default_tf not in timeframe_options:
                default_tf = "YTD"
            selected_tf = st.pills(
                "Clickable timeframe header",
                timeframe_options,
                selection_mode="single",
                default=default_tf,
                key=tf_key,
                format_func=timeframe_display_label,
            ) or default_tf
            basis_key = f"sector_profit_basis_{key_suffix}"
            profit_basis = st.number_input(
                "Investment basis ($ per stock)",
                min_value=0.0,
                max_value=1_000_000_000.0,
                value=float(st.session_state.get("investment_amount", 10_000.0) or 10_000.0),
                step=1_000.0,
                format="%.2f",
                key=basis_key,
                help="Total Profit uses the same hypothetical starting amount for each stock so performance is directly comparable.",
            )

            # v5.9.33: always return an index-aligned numeric Series. ``DataFrame.get`` can
            # return None for a missing timeframe (which pd.to_numeric converts into a scalar
            # numpy.float64 NaN), and duplicate source columns can return a DataFrame. Either
            # shape used to crash the popover when ``.notna()`` was called on the scalar.
            def _sector_numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
                if column not in frame.columns:
                    return pd.Series(np.nan, index=frame.index, dtype="float64")
                values = frame.loc[:, column]
                if isinstance(values, pd.DataFrame):
                    values = values.iloc[:, 0]
                numeric = pd.to_numeric(values, errors="coerce")
                if isinstance(numeric, pd.Series):
                    return numeric.reindex(frame.index).astype("float64")
                return pd.Series(float(numeric) if pd.notna(numeric) else np.nan, index=frame.index, dtype="float64")

            # v5.9.35: sector drill-down periods 1Y-{ANNUAL_HISTORY_YEARS}Y are derived cumulative returns,
            # not literal snapshot columns. The source snapshot stores completed calendar-year
            # returns (for example latest completed year, prior year, ...), so trying to read a literal "6Y" column
            # previously produced NaN/None for every stock. Compound the latest N completed
            # calendar-year returns to make the selected horizon directly usable for ranking
            # and Total Profit calculations. Short periods continue to use their direct fields.
            def _sector_period_return_series(frame: pd.DataFrame, timeframe: str) -> pd.Series:
                timeframe = str(timeframe or "").strip().upper()
                if timeframe in {"1D", "1M", "3M", "6M", "YTD"}:
                    return _sector_numeric_series(frame, timeframe)
                if timeframe.endswith("Y") and timeframe[:-1].isdigit():
                    years = max(1, min(ANNUAL_HISTORY_YEARS, int(timeframe[:-1])))
                    annual_cols = list(YEAR_RETURN_COLS[:years])
                    if len(annual_cols) < years:
                        return pd.Series(np.nan, index=frame.index, dtype="float64")
                    annual = pd.DataFrame(
                        {col: _sector_numeric_series(frame, col) for col in annual_cols},
                        index=frame.index,
                    )
                    finite = np.isfinite(annual.to_numpy(dtype="float64", na_value=np.nan)).all(axis=1)
                    compounded = ((1.0 + annual / 100.0).prod(axis=1) - 1.0) * 100.0
                    compounded = pd.to_numeric(compounded, errors="coerce").astype("float64")
                    compounded.loc[~finite] = np.nan
                    return compounded.reindex(frame.index)
                return _sector_numeric_series(frame, timeframe)

            drill["_rank"] = _sector_period_return_series(drill, selected_tf)
            drill = drill.sort_values(["_rank", "MarketCap"], ascending=[False, False], na_position="last").reset_index(drop=True)
            drill_symbols = drill["Symbol"].astype(str).str.upper().tolist()
            drill_logo_urls = cached_logo_urls(tuple(drill_symbols)) if drill_symbols else {}
            drill_table = drill.copy()
            drill_table["Logo"] = drill_table["Symbol"].astype(str).str.upper().map(lambda sym: drill_logo_urls.get(sym, ""))

            # v5.9.35: keep the profit/ranking selector on 1D/1M/3M/6M/YTD + 1Y-{ANNUAL_HISTORY_YEARS}Y,
            # but show true NON-COMPOUNDED calendar-year returns in the table. This avoids
            # presenting 2Y/3Y/... cells as if they were individual annual returns. The annual
            # columns are the snapshot's completed years (latest completed year, prior year, ...), each representing
            # that single calendar year's actual return for the stock.
            short_return_cols = ["1D", "1M", "3M", "6M", "YTD"]
            annual_return_cols = list(YEAR_RETURN_COLS)
            for timeframe in short_return_cols:
                drill_table[timeframe] = _sector_numeric_series(drill_table, timeframe)
            for year_col in annual_return_cols:
                drill_table[year_col] = _sector_numeric_series(drill_table, year_col)

            selected_returns = _sector_period_return_series(drill_table, selected_tf)
            valid_selected_returns = selected_returns.notna() & np.isfinite(selected_returns.to_numpy(dtype="float64", na_value=np.nan))
            drill_table["Total Profit %"] = selected_returns
            drill_table["Total Profit"] = np.where(
                valid_selected_returns,
                float(profit_basis) * selected_returns / 100.0,
                np.nan,
            )

            drill_cols = list(dict.fromkeys([
                "Logo", "Symbol", "Name", "Analyst Rating", "Price", "Total Profit", "Total Profit %",
                *short_return_cols, *annual_return_cols, "Price Target Average", "MarketCap",
            ]))
            for dc in drill_cols:
                if dc not in drill_table.columns:
                    drill_table[dc] = pd.NA

            st.caption(f"{len(drill_table)} stocks · ranked by {selected_tf} · profit basis ${float(profit_basis):,.2f} per stock")
            configs = {
                "Logo": st.column_config.ImageColumn("Logo", width="small"),
                "Price": st.column_config.NumberColumn("Current Price", format="$%.2f"),
                "Total Profit": st.column_config.NumberColumn(f"Total Profit ({selected_tf})", format="$%.2f"),
                "Total Profit %": st.column_config.NumberColumn(f"Total Profit % ({selected_tf})", format="%.2f%%"),
                "Price Target Average": st.column_config.NumberColumn("Avg Target", format="$%.2f"),
                "MarketCap": st.column_config.NumberColumn("Market Cap", format="$%.0f"),
            }
            configs.update({metric: st.column_config.NumberColumn(metric, format="%.2f%%") for metric in short_return_cols})
            configs.update({year_col: st.column_config.NumberColumn(timeframe_display_label(year_col), format="%.2f%%") for year_col in annual_return_cols})
            st.dataframe(
                drill_table[drill_cols],
                use_container_width=True,
                hide_index=True,
                height=min(520, 110 + len(drill_table) * 32),
                column_config=configs,
                column_order=drill_cols,
                key=f"sector_top_performers_table_{key_suffix}",
            )

        for start in range(0, len(sector_df), 3):
            sector_cols = st.columns(3)
            for col, (_, sector_row) in zip(sector_cols, sector_df.iloc[start:start+3].iterrows()):
                with col:
                    cap = pd.to_numeric(pd.Series([sector_row.get("MarketCap")]), errors="coerce").iloc[0]
                    cap_label = f"${cap/1_000_000_000_000:,.2f}T" if pd.notna(cap) and cap >= 1_000_000_000_000 else (f"${cap/1_000_000_000:,.0f}B" if pd.notna(cap) else "—")
                    rank_val = pd.to_numeric(pd.Series([sector_row.get(sector_sort_period)]), errors="coerce").iloc[0]
                    rank_tone = "pos" if pd.notna(rank_val) and rank_val > 0 else ("neg" if pd.notna(rank_val) and rank_val < 0 else "flat")
                    sector_button_key = ''.join(ch if ch.isalnum() else '_' for ch in str(sector_row["Sector"]).lower())
                    with st.container(border=True, key=f"sector_card_{sector_button_key}"):
                        st.markdown(
                            f'<div class="sector-performance-head"><span>STOCK SECTOR</span><b>{escape(str(sector_row["Sector"]))}</b></div>',
                            unsafe_allow_html=True,
                        )
                        kpi_period, kpi_stocks, kpi_cap = st.columns(3)
                        with kpi_period:
                            st.markdown(
                                f'<div class="sector-native-kpi"><span>{escape(str(sector_sort_period))}</span><b class="{rank_tone}">{escape(format_pct(rank_val))}</b></div>',
                                unsafe_allow_html=True,
                            )
                        with kpi_stocks:
                            with st.popover(
                                f'TOTAL STOCKS · {int(sector_row["Stocks"])}',
                                use_container_width=True,
                                help=f'Tap Total Stocks to view and rank all {sector_row["Sector"]} stocks.',
                            ):
                                _render_sector_top_performers_popover(str(sector_row["Sector"]), sector_button_key)
                        with kpi_cap:
                            st.markdown(
                                f'<div class="sector-native-kpi"><span>Combined Mkt Cap</span><b>{escape(cap_label)}</b></div>',
                                unsafe_allow_html=True,
                            )
                        st.markdown(
                            f'<div class="sector-performance-kpis compact"><div><span>Positive breadth</span><b>{escape(format_pct(sector_row.get("Positive Breadth %")))}</b></div>'
                            f'<div><span>Buy/Strong Buy</span><b>{escape(format_pct(sector_row.get("Bullish Ratings %")))}</b></div></div>'
                            + '<div class="performance-grid sector-performance-grid">'
                            + ''.join(
                                '<div class="perf-cell"><span>' + escape(timeframe_display_label(metric)) + '</span><b class="' + _tone(sector_row.get(metric)) + '">' + escape(format_pct(sector_row.get(metric))) + '</b></div>'
                                for metric in PERF_COLS
                            )
                            + '</div>',
                            unsafe_allow_html=True,
                        )

        st.markdown("#### Sector performance table")
        table_cols = ["Sector", "Stocks", "MarketCap", "Positive Breadth %", "Bullish Ratings %", *PERF_COLS]
        sector_table = sector_df[table_cols].copy()
        st.dataframe(
            sector_table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "MarketCap": st.column_config.NumberColumn("Combined Market Cap", format="$%.0f"),
                "Positive Breadth %": st.column_config.NumberColumn("Positive Breadth", format="%.2f%%"),
                "Bullish Ratings %": st.column_config.NumberColumn("Buy/Strong Buy", format="%.2f%%"),
                **{metric: st.column_config.NumberColumn(timeframe_display_label(metric), format="%.2f%%") for metric in PERF_COLS},
            },
        )

with alerts_tab:
    st.markdown("### Alerts, methodology & operational help")
    st.caption("Buy-signal alerts and detailed data methodology live here so the primary research tabs stay focused.")
    with st.expander("Data methodology, ratings, persistence & schedule"):
        st.markdown(
            """
    - **Universe:** Nasdaq Stock Screener rows with market capitalization strictly above **$100 billion**, plus the 213-ETF CSV allowlist and any manually persisted symbols.
    - **Stock analyst rating:** Nasdaq Stock Screener `recommendation` buckets: Strong Buy, Buy, Hold, Sell and Strong Sell.
    - **ETF analyst rating:** Nasdaq's public ETF screener does not expose the same stock-style analyst consensus. MarketScope shows **Not Rated** unless the Nasdaq ETF response itself provides a genuine analyst/recommendation field; it does not relabel a fund score or momentum signal as analyst consensus.
    - **Rating colors:** Strong Buy/Buy = green; Hold = yellow; Sell/Strong Sell = red; Not Rated = gray.
    - **Returns:** Yahoo/yfinance adjusted daily market history. 1D/1M/3M/6M/YTD are point-to-point adjusted returns. The twenty year-labeled fields are **actual completed calendar-year returns**, calculated from the adjusted close at the end of the prior year to the adjusted close at the end of that year. They are not CAGR. Stocks do not have NAV. ETF NAV is not shown in the cards; ETF returns use adjusted market history.
    - **Investment simulator:** choose an investment amount and **YTD or 1–{ANNUAL_HISTORY_YEARS} completed years**. YTD calculates profit from the current saved YTD return only. The 1Y–{ANNUAL_HISTORY_YEARS}Y choices remain available at all times; when a selected instrument did not exist for the full requested span, MarketScope automatically starts at the first completed year shared by every selected instrument and uses up to the requested number of common years. The optional current-YTD toggle can then extend that result through today. Every 1D/1M/3M/6M/YTD/calendar-year tile inside a card is also clickable and shows the dollar ending value and profit for that exact return period.
    - **Card / Table tabs:** Card View preserves the interactive futuristic cards. Table View shows all currently filtered instruments in one dense table with all current performance, rating, target, signal and selected investment-simulation fields. You can use the explicit table sort controls or click any column header to sort interactively.
    - **Unlimited Stock & ETF Comparison:** use the single searchable **Stocks & ETFs to compare** selector in the Comparison tab to add or remove instruments. There is no selection cap. Once selected, MarketScope retrieves the instrument logo from Yahoo/company metadata when available and shows it on Comparison Cards and in the Comparison Table. Cards paginate 12 at a time and now mirror Market Navigator Card View: 2-year mini chart, clickable return/profit tiles, investment simulation, analyst targets, rating/signal badges, News, ETF Holdings, and full detail/live/year charts. Comparison Table shows the full selected set with all current performance periods, ratings, available stock targets, signals and selected investment-simulation results.
    - **Portfolio split simulator:** enter a total amount (default $200,000), select multiple tracked stocks/ETFs, choose equal split or custom percentages, and select YTD or a 1Y–{ANNUAL_HISTORY_YEARS}Y historical horizon. MarketScope calculates each allocation independently, then totals the simulated ending value and profit. Pre-IPO/pre-inception history is never fabricated; the simulation begins at the first completed year common to every selected instrument. Outside the optional Yearly/Monthly withdrawal modes, no deposits, withdrawals, taxes, fees, or future returns are assumed. Monthly withdrawal mode uses actual adjusted month-end returns calculated from historical Yahoo/yfinance market prices; annual returns are never divided into synthetic monthly rates.
    - **News Impact:** the News button performs an on-demand Yahoo Finance news search for that symbol and shows up to three recent (7-day) headlines only when rule-based fundamental language produces a clear positive or negative directional read. Green ▲ means a positive fundamental catalyst; red ▼ means a negative fundamental catalyst. This is context, not a prediction or guarantee. Neutral/ambiguous stories are not forced into an UP/DOWN label.
    - **Live chart:** opening a card loads a Yahoo Finance/yfinance intraday chart for that one instrument and refreshes the chart about every 60 seconds while it remains open. Yahoo/exchange delays can apply, so it is near-real-time rather than an exchange-direct tick feed.
    - **Analyst price targets:** stock cards show Yahoo analyst **Low / Average / High** target prices when available. ETFs remain blank because stock-style analyst price-target ranges are not consistently available for funds. These are analyst estimates, not guaranteed outcomes.
    - **Year chart:** below the live chart, opening a card lets you choose the current year or any tracked calendar year back to the configured history baseline. The plotted adjusted daily closes and the chart summary update to the selected year only.
    - **Persistent data:** the daily GitHub Action commits `data/default_universe.csv`, `data/market_snapshot.csv`, and `data/snapshot_metadata.json`. Render serves the local snapshot immediately; GitHub is the durable source of truth.
    - **Manual persistence:** configure the Render secret `MARKETSCOPE_GITHUB_TOKEN` (fine-grained token, Contents read/write on this repository) so manual refreshes and manually added symbols are committed to the same persistent snapshot.
    - **Signals:** Short Buy is a rule-based technical signal using SMA20/SMA50, MACD, RSI and 1M/3M momentum. Long Buy uses long-trend technical rules plus Nasdaq Buy/Strong Buy consensus for stocks; ETFs use technical criteria because stock-style analyst consensus is generally unavailable. A Nasdaq Strong Buy is treated as a fundamental/consensus buy signal for stocks.
    - **Schedule:** every calendar day at **6:00 PM America/New_York**. All displayed refresh/rating timestamps use U.S. Eastern time.
            """
        )

st.markdown("---")
st.markdown(
    "<div class='small-note'>MarketScope is informational, not investment advice. Analyst consensus is an opinion summary, not a guarantee. Free public data can be delayed, unavailable, or revised. Verify order-critical prices with your broker and ETF NAV with the fund issuer.</div>",
    unsafe_allow_html=True,
)
