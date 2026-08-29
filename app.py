from __future__ import annotations

import json
import os
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
    calculate_performance,
    completed_year_labels,
)
from persistence import (
    format_et,
    load_remote_metadata,
    load_remote_snapshot,
    load_remote_universe_metadata,
    now_et,
    persist_snapshot,
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
from providers import YahooFinanceProvider
from providers.nasdaq import NasdaqScreenerProvider
from universe import is_render_runtime, load_default_universe

BASE_DIR = Path(__file__).resolve().parent
SNAPSHOT_FILE = BASE_DIR / "data" / "market_snapshot.csv"
BOOTSTRAP_SNAPSHOT_FILE = BASE_DIR / "data" / "market_snapshot.bootstrap.csv"
SNAPSHOT_META_FILE = BASE_DIR / "data" / "snapshot_metadata.json"
BOOTSTRAP_META_FILE = BASE_DIR / "data" / "snapshot_metadata.bootstrap.json"
UNIVERSE_META_FILE = BASE_DIR / "data" / "universe_metadata.json"
BOOTSTRAP_UNIVERSE_META_FILE = BASE_DIR / "data" / "universe_metadata.bootstrap.json"
YEAR_RETURN_COLS = completed_year_labels(as_of=now_et(), years=20)
PERF_COLS = ["1D", "1M", "3M", "6M", "YTD", *YEAR_RETURN_COLS]
ALL_RETURN_COLS = ["Since Inception"] + PERF_COLS
SIGNAL_COLS = ["Short Buy", "Long Buy", "Fundamental Buy"]
PRICE_TARGET_COLS = ["Price Target Low", "Price Target Average", "Price Target High"]
RATINGS = ["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell", "Not Rated"]
MIN_STOCK_MARKET_CAP = 100_000_000_000.0

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


def _normalize_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "Symbol" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["Symbol"] = df["Symbol"].astype(str).str.upper().str.strip()
    # v5.7 intentionally does not map legacy CAGR columns into calendar-year returns.
    # Annual return cells remain blank until a real historical refresh computes
    # each completed calendar year from adjusted year-end closes.
    numeric = ["MarketCap", "Price", "NAV", *PRICE_TARGET_COLS] + ALL_RETURN_COLS
    for col in numeric:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["Analyst Rating", "Rating Source", "Rating Updated ET", "Price Target Updated ET", "Snapshot Updated ET"]:
        if col not in df.columns:
            df[col] = "Not Rated" if col == "Analyst Rating" else "—"
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
    """Load durable generated data first, then GitHub, then bootstrap.

    v5.3 does not bundle data/market_snapshot.csv, so upgrades can no longer
    overwrite the populated snapshot. That lets normal startup stay fast: when
    the generated local snapshot is present, no network call is required.
    """
    local = pd.DataFrame()
    if SNAPSHOT_FILE.exists():
        try:
            local = _normalize_snapshot(pd.read_csv(SNAPSHOT_FILE))
        except Exception:
            local = pd.DataFrame()
    if _populated_price_count(local) > 0:
        return local

    remote = _normalize_snapshot(load_remote_snapshot())
    if _populated_price_count(remote) > 0:
        return remote

    if BOOTSTRAP_SNAPSHOT_FILE.exists():
        try:
            bootstrap = _normalize_snapshot(pd.read_csv(BOOTSTRAP_SNAPSHOT_FILE))
            if not bootstrap.empty:
                return bootstrap
        except Exception:
            pass
    return local if not local.empty else remote


def _read_metadata_file(path: Path) -> dict:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    return {}


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


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def cached_price_targets(symbols: tuple[str, ...]) -> dict:
    """Lazy Yahoo price-target fallback for stock cards visible on the current page."""
    clean = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
    if not clean:
        return {}
    try:
        return provider.get_price_targets_many(clean, max_workers=4)
    except Exception:
        return {}


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


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_logo_urls(symbols: tuple[str, ...]) -> dict:
    """Fetch logos only for instruments the user actually selected for comparison."""
    clean = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
    if not clean:
        return {}
    try:
        return provider.get_logo_urls_many(clean, max_workers=6)
    except Exception:
        return {}


def _comparison_logo_html(symbol: str, logo_url: str) -> str:
    symbol = str(symbol or "").strip().upper()
    initials = escape((symbol[:2] or "?").upper())
    url = escape(str(logo_url or "").strip(), quote=True)
    if url.startswith(("https://", "http://")):
        return f'<span class="comparison-logo"><img src="{url}" alt="{escape(symbol)} logo" loading="lazy"></span>'
    return f'<span class="comparison-logo comparison-logo-fallback">{initials}</span>'


def _enrich_pdf_record_with_current_market(record: dict, market_df: pd.DataFrame) -> dict:
    """Upgrade any saved simulation to the current first-page instrument data contract."""
    upgraded = json.loads(json.dumps(record))
    required_layout = "MarketScope Portfolio Split Simulator v5 - required instrument market data on page 1"
    upgraded["_force_pdf_rebuild"] = str(record.get("pdf_layout") or "") != required_layout
    if market_df is None or market_df.empty:
        upgraded["pdf_layout"] = required_layout
        return upgraded
    lookup_df = market_df.copy()
    lookup_df["Symbol"] = lookup_df["Symbol"].astype(str).str.upper().str.strip()
    lookup_df = lookup_df.drop_duplicates("Symbol", keep="last").set_index("Symbol", drop=False)
    for item in upgraded.get("instruments") or []:
        sym = str(item.get("symbol") or "").upper().strip()
        if sym not in lookup_df.index:
            continue
        row = lookup_df.loc[sym]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        item["name"] = str(row.get("Name") or item.get("name") or sym)
        item["sector"] = str(row.get("Sector") or item.get("sector") or "")
        item["analyst_rating"] = str(row.get("Analyst Rating") or item.get("analyst_rating") or "Not Rated")
        for key, col in (("current_price", "Price"), ("price_target_low", "Price Target Low"), ("price_target_average", "Price Target Average"), ("price_target_high", "Price Target High")):
            val = pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").iloc[0]
            if pd.notna(val):
                item[key] = float(val)
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
    histories = provider.download_daily_history([symbol], period="max")
    hist = histories.get(symbol)
    if hist is None or hist.empty:
        return {}
    perf = calculate_performance(hist)
    annual_returns = calculate_calendar_year_returns(hist, years=20)
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
            annual_returns = calculate_calendar_year_returns(hist, years=20)
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
            out.at[idx, year] = as_percent(annual_returns.get(year))
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
        chosen = st.pills("Columns to filter", display_cols, selection_mode="multi", key="advanced_filter_columns") or []
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
    """
<div class="hero">
  <h1>MarketScope</h1>
  <p>Nasdaq stocks > $100B + ETFs • actual calendar-year returns • analyst consensus • persistent cloud snapshot</p>
  <span class="source-pill">● Nasdaq Stock Screener > $100B + Yahoo Finance • all displayed times: U.S. Eastern</span>
</div>
""",
    unsafe_allow_html=True,
)

snapshot = load_snapshot()
metadata = load_snapshot_metadata()
universe_metadata = load_universe_metadata()
base_symbols = default_universe["Symbol"].astype(str).str.upper().tolist()
snapshot_symbols = snapshot["Symbol"].tolist() if not snapshot.empty else []
extra_symbols = [s for s in st.session_state.extra_symbols if s not in set(base_symbols)]
symbols = list(dict.fromkeys(base_symbols + snapshot_symbols + extra_symbols))
market_base = assemble_market(symbols, snapshot)
market = apply_live_overlay(market_base, st.session_state.live_prices)

# Nasdaq universe membership audit strip. The scheduled 6 PM ET workflow writes
# the refresh timestamp plus exact symbols crossing the >$100B screening boundary.
raw_universe_stamp = universe_metadata.get("refreshed_at_et")
universe_refreshed = "Pending first scheduled refresh"
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

# v5.9.20: compact operational help + organized top-level workspace tabs.
with st.popover("ⓘ PDF Setup"):
    st.markdown("#### Server PDF backup setup")
    if os.getenv("MARKETSCOPE_GITHUB_TOKEN"):
        st.success("MARKETSCOPE_GITHUB_TOKEN is configured on this server.")
    else:
        st.warning("MARKETSCOPE_GITHUB_TOKEN is not configured on this server yet.")
    st.markdown(
        """
**What this secret does**  
It lets MarketScope save generated PDFs and persistent app data back to the configured GitHub repository so they can be recovered after a Render restart or redeploy.

**One-time setup**
1. In GitHub, create a **fine-grained personal access token**.
2. Limit repository access to the MarketScope repository only.
3. Give **Repository permissions → Contents → Read and write**.
4. In Render, open the MarketScope service and go to **Environment**.
5. Add an environment variable named exactly `MARKETSCOPE_GITHUB_TOKEN`.
6. Paste the GitHub token as the value, save, and redeploy.

**Security**  
Never put the token in source code, a PDF, a screenshot, or a chat message. MarketScope only checks whether the secret exists; it never displays the token value here.
        """
    )

market_tab, portfolio_tab, compare_tab, alerts_tab = st.tabs([
    "◈ Market Navigator",
    "◫ Portfolio Simulator",
    "⚖ Stock & ETF Comparison",
    "🔔 Alerts & Help",
])

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
        '</div>',
        unsafe_allow_html=True,
    )

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
                histories = provider.download_daily_history(batch, period="max")
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

def _portfolio_horizon_projection(row: pd.Series, principal: float, period_choice: str, include_ytd: bool) -> dict | None:
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
    years_requested = max(1, min(20, years_requested))
    newest_to_oldest: list[tuple[str, float]] = []
    for year in YEAR_RETURN_COLS:
        pct = pd.to_numeric(pd.Series([row.get(year)]), errors="coerce").iloc[0]
        if pd.isna(pct) or not np.isfinite(pct):
            break
        newest_to_oldest.append((year, float(pct)))
    if len(newest_to_oldest) < years_requested:
        return {"unavailable": True, "period": period_choice, "available_years": len(newest_to_oldest)}
    selected = newest_to_oldest[:years_requested]
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
        "ytd_applied": ytd_applied,
    }


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


def _portfolio_analytics_payload(meta_row: pd.Series, result: dict, income_metrics: dict) -> dict:
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
        "worst_year": stats.get("worst_year"),
        "worst_year_pct": stats.get("worst_year_pct"),
        "best_year": stats.get("best_year"),
        "best_year_pct": stats.get("best_year_pct"),
        "regular_yield_pct": yield_pct,
        "est_annual_dividend": est_dividend,
        "yield_source": str((income_metrics or {}).get("source") or ""),
        "performance": performance,
    }


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

    portfolio_build_tab, portfolio_manage_tab = st.tabs(["◆ Build Simulation", "💾 Saved / Manage"])

    with portfolio_build_tab:
        st.markdown("<div class='investment-title'>PORTFOLIO SPLIT SIMULATOR</div>", unsafe_allow_html=True)
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
        all_portfolio_symbols = market["Symbol"].astype(str).str.upper().drop_duplicates().tolist()
        valid_saved_portfolio = [s for s in st.session_state.portfolio_symbols if s in set(all_portfolio_symbols)]
        if valid_saved_portfolio != st.session_state.portfolio_symbols:
            st.session_state.portfolio_symbols = valid_saved_portfolio
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

        port_controls = st.columns([1.7, 1.35, 1.35, 2.4])
        with port_controls[0]:
            portfolio_period = st.segmented_control(
                "Portfolio period",
                ["YTD", *[f"{i}Y" for i in range(1, 21)]],
                default="YTD",
                key="portfolio_period",
                help="YTD uses only the current saved YTD return. 1Y–20Y compounds completed calendar-year returns.",
            )
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
                help="For 1Y–20Y only, optionally apply the current YTD return after the completed-year history.",
            )
        with port_controls[3]:
            st.caption(
                "Example: enter $200,000, choose several instruments, then use an equal split or custom percentages. "
                "MarketScope calculates each allocation separately and totals the simulated ending value and profit."
            )

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
                        row, allocated, str(portfolio_period or "YTD"), bool(portfolio_include_ytd)
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
                pc1, pc2, pc3, pc4 = st.columns(4)
                pc1.metric("Portfolio invested", f"${portfolio_total:,.2f}")
                pc2.metric("Calculated ending value", f"${total_ending:,.2f}")
                pc3.metric("Calculated profit / loss", f"${total_profit:+,.2f}")
                pc4.metric("Calculated return", f"{total_return:+.2f}%")
                if unresolved_amount > 0:
                    st.warning(
                        f"${unresolved_amount:,.2f} of the starting allocation could not be simulated because the selected period is unavailable for one or more instruments. "
                        "That unresolved amount is not included in the ending-value/profit totals above."
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
                                    f"<div class='portfolio-result-card'><span>{escape(sym)} • {result['weight']:.1f}% • {escape(str(portfolio_period or 'YTD'))}</span>"
                                    f"<b>${result['ending_value']:,.2f}</b>"
                                    f"<small>${result['allocated']:,.2f} start • <span class='{klass}'>Profit {profit:+,.2f} ({result['return_pct']:+.2f}%)</span></small></div>",
                                    unsafe_allow_html=True,
                                )
                    st.markdown("</div>", unsafe_allow_html=True)

                # v5.9.6 - populate the portfolio analytics table immediately after the simulation runs.
                if portfolio_results:
                    portfolio_income_metrics = cached_income_metrics(tuple(str(s).upper() for s in selected_portfolio_symbols))
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
                            _portfolio_analytics_payload(meta_row, result, portfolio_income_metrics.get(sym, {}))
                        )

                    if portfolio_analytics:
                        st.markdown("<div class='portfolio-analytics-title'>PORTFOLIO INFORMATION & PERFORMANCE TABLE</div>", unsafe_allow_html=True)
                        st.caption(
                            "10-year CAGR is calculated from the 10 completed calendar-year returns when all 10 are available. "
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
            market_lookup = market.set_index(market["Symbol"].astype(str).str.upper(), drop=False)
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
                "pdf_layout": "MarketScope Portfolio Split Simulator v5 - required instrument market data on page 1",
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
                    st.markdown(
                        "<div class='simulation-library-card'>"
                        f"<div><span class='simulation-library-name'>{escape(rec_name)}</span>"
                        f"<small>{escape(str(rec.get('created_at_display_et') or ''))} • {escape(str(rec.get('period') or 'YTD'))} • "
                        f"{int(rec.get('instrument_count') or len(rec.get('instruments') or []))} instrument(s)</small></div>"
                        f"<div class='simulation-library-metric'><small>INVESTED</small><b>${float(rec.get('total_invested') or 0):,.2f}</b></div>"
                        f"<div class='simulation-library-metric'><small>ENDING</small><b>${float(rec.get('ending_value') or 0):,.2f}</b></div>"
                        f"<div class='simulation-library-metric'><small>PROFIT / LOSS</small><b class='{profit_class}'>${profit_value:+,.2f}</b></div>"
                        f"<div class='simulation-library-metric'><small>RETURN</small><b class='{profit_class}'>{return_value:+.2f}%</b></div>"
                        "</div>",
                        unsafe_allow_html=True,
                    )
                    action_cols = st.columns([1.35, 1.15, 1.0, 3.7])
                    pdf_record = _enrich_pdf_record_with_current_market(rec, market)
                    record_json = json.dumps(pdf_record, sort_keys=True, separators=(",", ":"))
                    # v5.9.22 forces the first open of an older saved PDF through the new
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
            ["YTD", *[f"{i}Y" for i in range(1, 21)]],
            default=(_query_scalar_early("sim_period", "10Y") if _query_scalar_early("sim_period", "10Y") in ["YTD", *[f"{i}Y" for i in range(1, 21)]] else "10Y"),
            key="investment_period_choice",
            help="Choose YTD only, or compound 1–20 of the most recent completed calendar years.",
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
            help="For 1Y–20Y selections, apply the current YTD return after the completed calendar years. YTD-only always uses YTD by itself.",
        )
        include_current_ytd = True if investment_is_ytd else bool(include_current_ytd_toggle)
    with sim_cols[3]:
        st.caption(
            "Investment years: choose YTD for a current-year-only profit calculation, or 1–20 completed calendar years for historical compounding. "
            "You can also tap any return period/year inside an individual card to calculate profit for that exact period using this dollar amount."
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
            "<small>Every card shows short-horizon + 20 calendar-year returns • tap News for catalysts or Open for yearly charts</small></div>",
            unsafe_allow_html=True,
        )

        # v5.9.13: Card View search retained; card-render execution scope repaired.
        card_local_search = st.text_input(
            "Search stock / ETF",
            key="card_local_search",
            placeholder="Ticker or company / ETF name...",
            help="Filters Card View by symbol, name, stock/ETF type, sector, industry, or analyst rating.",
        )
        if card_local_search and card_local_search.strip():
            _card_query = card_local_search.strip().lower()
            _card_search_columns = ["Symbol", "Name", "Type", "Sector", "Industry", "Analyst Rating"]
            _card_search_mask = pd.Series(False, index=filtered.index)
            for _search_col in _card_search_columns:
                if _search_col in filtered.columns:
                    _card_search_mask |= (
                        filtered[_search_col]
                        .fillna("")
                        .astype(str)
                        .str.lower()
                        .str.contains(_card_query, regex=False, na=False)
                    )
            filtered = filtered.loc[_card_search_mask].copy()
            st.caption(
                f"Card search: {len(filtered):,} match(es) for ‘{card_local_search.strip()}’. "
                "Clear the search box to show all currently-filtered instruments."
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
            years_requested = max(1, min(20, int(years_requested)))
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
            f"<div class='sort-summary'>Sorted by <strong>{escape(st.session_state.card_sort_choice)}</strong> "
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
                    label = f"● {option}" if active else option
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
        visible_stock_symbols = card_rows.loc[
            card_rows["Type"].astype(str).str.upper().eq("STOCK"), "Symbol"
        ].astype(str).tolist()
        missing_target_symbols = []
        for symbol in visible_stock_symbols:
            row = card_rows.loc[card_rows["Symbol"].astype(str).eq(symbol)].iloc[0]
            vals = [pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").iloc[0] for col in PRICE_TARGET_COLS]
            if not any(pd.notna(v) and np.isfinite(v) and float(v) > 0 for v in vals):
                missing_target_symbols.append(symbol)
        if missing_target_symbols:
            visible_targets = cached_price_targets(tuple(missing_target_symbols))
            for symbol, values in visible_targets.items():
                mask = card_rows["Symbol"].astype(str).eq(symbol)
                if not mask.any():
                    continue
                for source_key, col in (("low", "Price Target Low"), ("mean", "Price Target Average"), ("high", "Price Target High")):
                    value = pd.to_numeric(pd.Series([values.get(source_key)]), errors="coerce").iloc[0]
                    if pd.notna(value) and np.isfinite(value) and float(value) > 0:
                        card_rows.loc[mask, col] = float(value)
                card_rows.loc[mask, "Price Target Updated ET"] = format_et()

        # One batched Yahoo request supplies two years of adjusted 1-day closes for
        # every visible card. The result is cached for 30 minutes to keep paging fast.
        visible_chart_histories = cached_card_two_year_histories(
            tuple(card_rows["Symbol"].astype(str).str.upper().tolist())
        )

        def _card_chart_svg(symbol: str) -> str:
            """Compact 2Y / 1D SVG chart designed for the top-right card space."""
            history = visible_chart_histories.get(str(symbol).upper())
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
                f'<span>SELECTED PERIOD • {escape(str(result["period"]))} • ${float(principal):,.2f} invested</span>'
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


        def _set_card_profit_period(symbol: str, metric: str) -> None:
            """Button callback: save the selected return period before the fragment reruns."""
            clean_symbol = str(symbol or "").upper()
            if metric in PERF_COLS and clean_symbol:
                st.session_state[f"card_profit_period_selected_{clean_symbol}"] = metric


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
        def render_card_profit_period_fragment(row_data: dict, principal: float) -> None:
            """Render reliable, card-local period buttons and exact-period profit output.

            Native Streamlit button callbacks update session state *before* the fragment
            reruns. This fixes the previous behavior where a clicked tile could render
            without the new period being applied. Only this fragment reruns, so the
            update remains smooth, updates only this card area, and the user's scroll position stays stable.
            """
            row = pd.Series(row_data)
            symbol = str(row.get("Symbol") or "").upper()
            selected_key = f"card_profit_period_selected_{symbol}"
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
                        st.button(
                            f"{metric}  {format_pct(row.get(metric))}",
                            key=f"profit_tile_{symbol}_{metric}",
                            use_container_width=True,
                            type="primary" if active else "secondary",
                            on_click=_set_card_profit_period,
                            args=(symbol, metric),
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



        def _instrument_card_header_html(row: pd.Series, price: str, cap_display: str) -> str:
            """v5.9.7 card header plus a compact 2Y daily chart in the reserved top-right space."""
            raw_symbol = str(row.get("Symbol") or "")
            symbol = escape(raw_symbol)
            instrument_type = escape(str(row.get("Type") or ""))
            display_name = escape(_card_display_name(row))
            chart_html = _card_chart_svg(raw_symbol)
            sector_html = _stock_sector_html(row)
            if str(row.get("Type") or "").strip().upper() == "ETF":
                sector = str(row.get("Sector") or "ETF / Fund").strip() or "ETF / Fund"
                sector_html = f'<div class="stock-sector">{escape(sector)}</div>'
            parts = [
                f'<div id="{_card_anchor_id(raw_symbol)}" class="instrument-card-head">',
                '<div class="card-header-grid">',
                '<div class="card-header-identity">',
                f'<div class="card-top"><span class="ticker">{symbol}</span></div>',
                f'<div class="company-name">{display_name}</div>',
                sector_html,
                '</div>',
                '<div class="card-header-chart">',
                f'<div class="asset-type-row"><span class="asset-type">{instrument_type}</span></div>',
                chart_html,
                '</div>',
                '</div>',
                f'<div class="card-quote-row"><span class="price-line">{escape(price)}</span><span class="cap-line">Mkt Cap {escape(cap_display)}</span></div>',
                _price_target_html(row),
                '</div>',
            ]
            return ''.join(part for part in parts if part)


        def _instrument_card_html(row: pd.Series, price: str, cap_display: str, rating: str, signal: str) -> str:
            """Compatibility wrapper for the v5.9.7 full-metrics-card builder contract."""
            return _instrument_card_header_html(row, price, cap_display)


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
                    f'<span>{escape(metric)}</span>'
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
            years_requested = max(1, min(20, int(years_requested)))
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
                            _instrument_card_html(row, price, cap_display, rating, signal),
                            unsafe_allow_html=True,
                        )
                        render_card_profit_period_fragment(row.to_dict(), float(investment_amount))
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
            detail_row = market.loc[market["Symbol"].astype(str) == selected].iloc[0].copy()
            if str(detail_row.get("Type") or "").strip().upper() == "STOCK":
                current_targets = [pd.to_numeric(pd.Series([detail_row.get(col)]), errors="coerce").iloc[0] for col in PRICE_TARGET_COLS]
                if not any(pd.notna(v) and np.isfinite(v) and float(v) > 0 for v in current_targets):
                    detail_target = cached_price_targets((selected,)).get(selected, {})
                    for source_key, col in (("low", "Price Target Low"), ("mean", "Price Target Average"), ("high", "Price Target High")):
                        value = pd.to_numeric(pd.Series([detail_target.get(source_key)]), errors="coerce").iloc[0]
                        if pd.notna(value) and np.isfinite(value) and float(value) > 0:
                            detail_row[col] = float(value)
                    if detail_target:
                        detail_row["Price Target Updated ET"] = format_et()
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
            chart_year_options = [str(current_year - offset) for offset in range(0, 21)]
            chart_year = st.segmented_control(
                "Chart year",
                chart_year_options,
                default=str(current_year),
                key=f"chart_year_{selected}",
                help="Choose the current year or any of the prior 20 calendar years. The graph and summary metrics update to that year only.",
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
            st.info("Choose an instrument card to open its full short-horizon and 20-calendar-year performance view.")



    with table_view_tab:
        st.markdown(
            "<div class='table-view-header'><span>MARKET TABLE</span><small>All currently filtered instruments • click any column header to sort interactively</small></div>",
            unsafe_allow_html=True,
        )
        table_df = view_filtered.copy()

        # Add the same investment simulation result currently selected above so the
        # table can be ranked by estimated dollar profit as well as raw market data.
        sim_ending_values = []
        sim_profit_values = []
        sim_return_values = []
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

        table_df["Market Cap ($B)"] = pd.to_numeric(table_df.get("MarketCap"), errors="coerce") / 1_000_000_000
        table_df["Simulation Period"] = str(investment_period_choice)
        table_df["Investment Amount ($)"] = float(investment_amount)
        table_df["Estimated Value ($)"] = sim_ending_values
        table_df["Profit / Loss ($)"] = sim_profit_values
        table_df["Simulation Return %"] = sim_return_values

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
            "Analyst Rating", "Price Target Low", "Price Target Average", "Price Target High", "Avg Target Implied %",
            "Short Buy", "Long Buy", "Fundamental Buy",
            *PERF_COLS,
            "Simulation Period", "Investment Amount ($)", "Estimated Value ($)", "Profit / Loss ($)", "Simulation Return %",
            "Signal Reasons",
        ]
        for _col in TABLE_COLUMNS:
            if _col not in table_df.columns:
                table_df[_col] = pd.NA
        table_df = table_df[TABLE_COLUMNS].copy()

        # Explicit table sorting complements Streamlit's native click-the-header sort.
        table_sort_options = [
            "Symbol", "Name", "Price", "Market Cap ($B)", "Analyst Rating",
            "Price Target Average", "Avg Target Implied %", "Profit / Loss ($)", "Simulation Return %",
            *PERF_COLS,
        ]
        # v5.9.13: Table View search retained; Card View uses the same search behavior.
        # It accepts ticker, company/fund name, type, sector, industry, or analyst rating.
        ts1, ts_search, ts2, ts3 = st.columns([2.1, 2.2, 1.6, 3.1])
        with ts1:
            table_sort_choice = st.selectbox(
                "Sort table by",
                table_sort_options,
                index=table_sort_options.index("Market Cap ($B)"),
                key="table_sort_choice",
            )
        with ts_search:
            table_local_search = st.text_input(
                "Search stock / ETF",
                key="table_local_search",
                placeholder="Ticker or company / ETF name...",
                help="Filters Table View by symbol, name, stock/ETF type, sector, industry, or analyst rating.",
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
                f"Profit columns use ${investment_amount:,.2f} and the currently selected {investment_period_choice} simulator period."
            )

        if table_local_search and table_local_search.strip():
            _table_query = table_local_search.strip().lower()
            _table_search_columns = ["Symbol", "Name", "Type", "Sector", "Industry", "Analyst Rating"]
            _table_search_mask = pd.Series(False, index=table_df.index)
            for _search_col in _table_search_columns:
                if _search_col in table_df.columns:
                    _table_search_mask |= (
                        table_df[_search_col]
                        .fillna("")
                        .astype(str)
                        .str.lower()
                        .str.contains(_table_query, regex=False, na=False)
                    )
            table_df = table_df.loc[_table_search_mask].copy()
            st.caption(f"Table search: {len(table_df):,} match(es) for ‘{table_local_search.strip()}’. Clear the search box to show all filtered instruments.")

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
            "Price Target Low": st.column_config.NumberColumn("Target Low", format="$%.2f"),
            "Price Target Average": st.column_config.NumberColumn("Target Avg", format="$%.2f"),
            "Price Target High": st.column_config.NumberColumn("Target High", format="$%.2f"),
            "Avg Target Implied %": st.column_config.NumberColumn("Avg Target Implied", format="%.2f%%"),
            "Investment Amount ($)": st.column_config.NumberColumn("Investment", format="$%.2f"),
            "Estimated Value ($)": st.column_config.NumberColumn("Est. Value", format="$%.2f"),
            "Profit / Loss ($)": st.column_config.NumberColumn("Profit / Loss", format="$%.2f"),
            "Simulation Return %": st.column_config.NumberColumn("Simulation Return", format="%.2f%%"),
            "Short Buy": st.column_config.CheckboxColumn("Short Buy"),
            "Long Buy": st.column_config.CheckboxColumn("Long Buy"),
            "Fundamental Buy": st.column_config.CheckboxColumn("Fundamental Buy"),
        }
        for _perf_col in PERF_COLS:
            table_column_config[_perf_col] = st.column_config.NumberColumn(_perf_col, format="%.2f%%")

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
            "Previously removed metadata columns (Return Basis, Rating Source, Data As Of, Rating Update ET, Snapshot Update ET, NAV, Exchange, Inception Date) remain intentionally hidden."
        )


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

    # Drop stale symbols while preserving user selection order.
    valid_compare_symbols = [
        symbol for symbol in list(dict.fromkeys(str(x).upper() for x in st.session_state.compare_symbols))
        if symbol in set(all_compare_symbols)
    ]
    if valid_compare_symbols != list(st.session_state.compare_symbols):
        st.session_state.compare_symbols = valid_compare_symbols
    if list(st.session_state.stock_compare_selector) != valid_compare_symbols:
        st.session_state.stock_compare_selector = valid_compare_symbols

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
    )
    selector_symbols = list(dict.fromkeys(str(x).upper() for x in compare_selector))
    if selector_symbols != list(st.session_state.compare_symbols):
        st.session_state.compare_symbols = selector_symbols
        st.session_state.compare_page = 0

    comparison_symbols = [s for s in st.session_state.compare_symbols if s in set(all_compare_symbols)]
    if not comparison_symbols:
        st.info("Add two or more stocks and/or ETFs to build a comparison. You can still compare a single instrument while assembling the set.")
    else:
        comparison_df = all_compare_rows.loc[all_compare_rows["Symbol"].isin(comparison_symbols)].copy()
        comparison_df["_compare_order"] = comparison_df["Symbol"].map({s: i for i, s in enumerate(comparison_symbols)})
        comparison_df = comparison_df.sort_values("_compare_order").drop(columns="_compare_order")
        comparison_logo_urls = cached_logo_urls(tuple(comparison_symbols))

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
                    comparison_card_html = ''.join([
                        '<div class="comparison-instrument-card">',
                        '<div class="comparison-card-identity">',
                        _comparison_logo_html(symbol, comparison_logo_urls.get(symbol, "")),
                        '<div class="comparison-card-id-text">',
                        f'<div class="card-top"><span class="ticker">{escape(symbol)}</span><span class="asset-type">{escape(str(row.get("Type") or ""))}</span></div>',
                        f'<div class="company-name">{escape(_card_display_name(row))}</div>',
                        '</div></div>',
                        _stock_sector_html(row) if str(row.get("Type") or "").strip().upper() == "STOCK" else "",
                        f'<div class="card-quote-row"><span class="price-line">{escape(price)}</span><span class="cap-line">Mkt Cap {escape(cap_display)}</span></div>',
                        _price_target_html(row),
                        f'<div class="performance-grid">{_performance_cells(row, clickable=False)}</div>',
                        _investment_html(row),
                        f'<div class="card-bottom"><span class="rating-pill {_rating_class(rating)}">{escape(rating)}</span><span class="signal-pill">{escape(signal)}</span></div>',
                        '</div>',
                    ])
                    with card_col:
                        st.markdown(comparison_card_html, unsafe_allow_html=True)
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
            comp_table["Simulation Period"] = str(investment_period_choice)
            comp_table["Investment Amount ($)"] = float(investment_amount)
            comp_table["Estimated Value ($)"] = comp_ending
            comp_table["Profit / Loss ($)"] = comp_profit
            comp_table["Simulation Return %"] = comp_sim_return
            comp_table["Logo"] = comp_table["Symbol"].map(lambda x: comparison_logo_urls.get(str(x).upper(), ""))

            comparison_columns = [
                "Logo", "Symbol", "Name", "Sector", "Industry", "Price", "Market Cap ($B)",
                "Analyst Rating", "Price Target Low", "Price Target Average", "Price Target High", "Avg Target Implied %",
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

            st.dataframe(
                comp_table,
                use_container_width=True,
                hide_index=True,
                height=min(840, 86 + max(1, len(comp_table)) * 35),
                column_config=comp_column_config,
                key="instrument_comparison_table",
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
    - **Investment simulator:** choose an investment amount and **YTD or 1–20 completed years**. YTD calculates profit from the current saved YTD return only. The 1Y–20Y choices compound exactly that many most-recent contiguous calendar-year returns; the optional current-YTD toggle can then extend that result through today. Every 1D/1M/3M/6M/YTD/calendar-year tile inside a card is also clickable and shows the dollar ending value and profit for that exact return period.
    - **Card / Table tabs:** Card View preserves the interactive futuristic cards. Table View shows all currently filtered instruments in one dense table with all current performance, rating, target, signal and selected investment-simulation fields. You can use the explicit table sort controls or click any column header to sort interactively.
    - **Unlimited Stock & ETF Comparison:** use the single searchable **Stocks & ETFs to compare** selector in the Comparison tab to add or remove instruments. There is no selection cap. Once selected, MarketScope retrieves the instrument logo from Yahoo/company metadata when available and shows it on Comparison Cards and in the Comparison Table. Cards paginate 12 at a time, while Comparison Table shows the full selected set with all current performance periods, ratings, available stock targets, signals and selected investment-simulation results.
    - **Portfolio split simulator:** enter a total amount (default $200,000), select multiple tracked stocks/ETFs, choose equal split or custom percentages, and select YTD or a 1Y–20Y historical horizon. MarketScope calculates each allocation independently, then totals the simulated ending value and profit. Missing history is identified and excluded rather than fabricated. No deposits, withdrawals, taxes, fees, or future returns are assumed.
    - **News Impact:** the News button performs an on-demand Yahoo Finance news search for that symbol and shows up to three recent (7-day) headlines only when rule-based fundamental language produces a clear positive or negative directional read. Green ▲ means a positive fundamental catalyst; red ▼ means a negative fundamental catalyst. This is context, not a prediction or guarantee. Neutral/ambiguous stories are not forced into an UP/DOWN label.
    - **Live chart:** opening a card loads a Yahoo Finance/yfinance intraday chart for that one instrument and refreshes the chart about every 60 seconds while it remains open. Yahoo/exchange delays can apply, so it is near-real-time rather than an exchange-direct tick feed.
    - **Analyst price targets:** stock cards show Yahoo analyst **Low / Average / High** target prices when available. ETFs remain blank because stock-style analyst price-target ranges are not consistently available for funds. These are analyst estimates, not guaranteed outcomes.
    - **Year chart:** below the live chart, opening a card lets you choose the current year or any of the prior 20 calendar years. The plotted adjusted daily closes and the chart summary update to the selected year only.
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
