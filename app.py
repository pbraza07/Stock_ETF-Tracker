from __future__ import annotations

import json
import os
from pathlib import Path
from html import escape
from typing import Dict, List

import numpy as np
import pandas as pd
import streamlit as st

from analytics import (
    as_percent,
    calculate_buy_signals,
    calculate_calendar_year_returns,
    calculate_performance,
    completed_year_labels,
)
from persistence import format_et, load_remote_metadata, load_remote_snapshot, now_et, persist_snapshot
from providers import YahooFinanceProvider
from providers.nasdaq import NasdaqScreenerProvider
from universe import is_render_runtime, load_default_universe

BASE_DIR = Path(__file__).resolve().parent
SNAPSHOT_FILE = BASE_DIR / "data" / "market_snapshot.csv"
BOOTSTRAP_SNAPSHOT_FILE = BASE_DIR / "data" / "market_snapshot.bootstrap.csv"
SNAPSHOT_META_FILE = BASE_DIR / "data" / "snapshot_metadata.json"
BOOTSTRAP_META_FILE = BASE_DIR / "data" / "snapshot_metadata.bootstrap.json"
YEAR_RETURN_COLS = completed_year_labels(as_of=now_et(), years=10)
PERF_COLS = ["1D", "1M", "3M", "6M", "YTD", *YEAR_RETURN_COLS]
ALL_RETURN_COLS = ["Since Inception"] + PERF_COLS
SIGNAL_COLS = ["Short Buy", "Long Buy", "Fundamental Buy"]
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
if "persistence_message" not in st.session_state:
    st.session_state.persistence_message = None
if "last_refresh_summary" not in st.session_state:
    st.session_state.last_refresh_summary = None
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = None
if "card_page" not in st.session_state:
    st.session_state.card_page = 0
if "card_sort_choice" not in st.session_state:
    st.session_state.card_sort_choice = "Market Cap"
if "card_sort_ascending" not in st.session_state:
    st.session_state.card_sort_ascending = False


def _normalize_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "Symbol" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["Symbol"] = df["Symbol"].astype(str).str.upper().str.strip()
    # v5.7 intentionally does not map legacy CAGR columns into calendar-year returns.
    # Annual return cells remain blank until a real historical refresh computes
    # each completed calendar year from adjusted year-end closes.
    numeric = ["MarketCap", "Price", "NAV"] + ALL_RETURN_COLS
    for col in numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["Analyst Rating", "Rating Source", "Rating Updated ET", "Snapshot Updated ET"]:
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


@st.cache_data(ttl=60 * 60, show_spinner=False)
def cached_chart_history(symbol: str, period: str) -> pd.DataFrame:
    return provider.download_chart_history(symbol, period)


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_single_metrics(symbol: str) -> dict:
    symbol = str(symbol).strip().upper()
    histories = provider.download_daily_history([symbol], period="max")
    hist = histories.get(symbol)
    if hist is None or hist.empty:
        return {}
    perf = calculate_performance(hist)
    annual_returns = calculate_calendar_year_returns(hist, years=10)
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
    for col in ["MarketCap", "Price", "NAV"] + ALL_RETURN_COLS:
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
            annual_returns = calculate_calendar_year_returns(hist, years=10)
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
base_symbols = default_universe["Symbol"].astype(str).str.upper().tolist()
snapshot_symbols = snapshot["Symbol"].tolist() if not snapshot.empty else []
extra_symbols = [s for s in st.session_state.extra_symbols if s not in set(base_symbols)]
symbols = list(dict.fromkeys(base_symbols + snapshot_symbols + extra_symbols))
market_base = assemble_market(symbols, snapshot)
market = apply_live_overlay(market_base, st.session_state.live_prices)

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

with st.sidebar:
    st.subheader("Market controls")
    st.caption("Fast startup uses the last durable snapshot. MarketScope uses Nasdaq stocks strictly above $100B while retaining the 213-ETF CSV universe and manually persisted symbols. The full scheduled refresh runs every day at 6:00 PM America/New_York.")
    if st.button("↻ Reload server snapshot", use_container_width=True):
        load_snapshot.clear()
        load_snapshot_metadata.clear()
        st.session_state.live_prices = {}
        st.rerun()

    if os.getenv("MARKETSCOPE_GITHUB_TOKEN", "").strip():
        st.success("Durable manual-save: configured")
    else:
        st.warning("Manual refresh persistence requires MARKETSCOPE_GITHUB_TOKEN in Render. The daily GitHub Action still persists automatically.")

    st.divider()
    st.subheader("Find any stock or ETF")
    with st.form("symbol_search", clear_on_submit=False):
        search_text = st.text_input("Ticker or company name", placeholder="NVDA, Apple, SPY...")
        do_search = st.form_submit_button("Search", use_container_width=True)
    if do_search and search_text:
        local = local_search(search_text)
        st.session_state.search_results = local if local else provider.search(search_text, max_results=8)
    results = st.session_state.search_results
    if results:
        labels = [f"{r['symbol']} — {r['name']} ({r.get('quote_type','')})" for r in results]
        selected_label = st.selectbox("Matches", labels)
        selected = results[labels.index(selected_label)]
        symbol = selected["symbol"]
        if symbol in set(symbols):
            st.success(f"{symbol} is already tracked.")
        elif st.button("＋ Add, calculate & save", use_container_width=True):
            with st.spinner(f"Loading {symbol} and saving it to the persistent snapshot..."):
                row = cached_single_metrics(symbol)
                if row:
                    st.session_state.extra_symbols.append(symbol)
                    st.session_state.session_rows[symbol] = row
                    _save_extras_to_url()
                    updated = merge_row_into_snapshot(snapshot, row)
                    ok, msg = persist_snapshot(updated, SNAPSHOT_FILE, "Manual symbol add", 1)
                    st.session_state.persistence_message = (ok, msg)
                    load_snapshot.clear()
                    load_snapshot_metadata.clear()
                    st.rerun()
                else:
                    st.warning("No market history was returned for that symbol.")

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
        "Instrument", ["All", "Stocks", "ETFs"], default="All", key="instrument_filter"
    )
with q2:
    cap_filter = st.segmented_control(
        "Stock market cap",
        ["> $100B", "> $200B", "> $500B", "> $1T"],
        default="> $100B",
        key="cap_filter",
        help="The Nasdaq stock universe already starts strictly above $100B. Higher buttons narrow it further. ETFs are not filtered by stock market cap.",
    )

rating_filter = st.pills(
    "Analyst Rating", RATINGS, selection_mode="multi", key="rating_filter"
) or []
signal_filter = st.pills(
    "Buy signals", ["Short-term Buy", "Long-term Buy", "New Signal"], selection_mode="multi", key="signal_filter"
) or []
stock_sector_rows = market.loc[market["Type"].astype(str).str.upper().eq("STOCK")]
sectors = sorted(
    x for x in stock_sector_rows["Sector"].dropna().astype(str).unique().tolist()
    if x and x.lower() not in {"nan", "unknown", "etf / fund", "fund", "etf"}
)
selected_sectors = st.pills(
    "Sector", sectors, selection_mode="multi", key="sector_filter"
) or []
table_search = st.text_input("Search displayed data", placeholder="Symbol, name, sector, industry, rating...")

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
if table_search:
    q = table_search.strip().lower()
    searchable = ["Symbol", "Name", "Sector", "Industry", "Analyst Rating", "Type"]
    mask = pd.Series(False, index=filtered.index)
    for col in searchable:
        if col in filtered.columns:
            mask |= filtered[col].astype(str).str.lower().str.contains(q, regex=False, na=False)
    filtered = filtered[mask]

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
    progress.progress(0.05, text=f"Refreshing Nasdaq analyst ratings for {total:,} instruments...")
    refreshed = refresh_ratings(refreshed, targets)

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
            min(0.74, 0.05 + pct * 0.69),
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
    progress.progress(0.97, text="Returns, signals, prices and ratings refreshed • saving the complete persistent snapshot...")

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

# One-time update timestamps above the table (not repeated as columns).
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

st.markdown("<div class='investment-title'>INVESTMENT SIMULATOR</div>", unsafe_allow_html=True)
sim_cols = st.columns([1.4, 1.4, 3.2])
with sim_cols[0]:
    investment_amount = st.number_input(
        "Investment amount ($)",
        min_value=0.0,
        max_value=1_000_000_000.0,
        value=10_000.0,
        step=1_000.0,
        format="%.2f",
        key="investment_amount",
    )
with sim_cols[1]:
    include_current_ytd = st.toggle(
        "Include current YTD",
        value=True,
        key="include_current_ytd",
        help="When enabled, the current YTD return is applied after the completed calendar-year returns to estimate value today.",
    )
with sim_cols[2]:
    st.caption(
        "The simulator compounds actual year-by-year adjusted returns in chronological order. "
        "It does not use CAGR and does not assume future returns, deposits, taxes, or fees."
    )

# Futuristic card navigator — every card exposes the complete performance ladder.
for col in DISPLAY_COLS:
    if col not in filtered.columns:
        filtered[col] = pd.NA

st.markdown(
    "<div class='navigator-title'><span>MARKET NAVIGATOR</span>"
    "<small>Every card shows 1D/1M/3M/6M/YTD plus 10 completed calendar years • tap Open for chart intelligence</small></div>",
    unsafe_allow_html=True,
)

SORT_OPTIONS = ["Market Cap", *PERF_COLS, "Rating"]
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
if sort_col in filtered.columns:
    if sort_choice == "Rating":
        rank = {"Strong Buy": 5, "Buy": 4, "Hold": 3, "Sell": 2, "Strong Sell": 1, "Not Rated": 0}
        filtered = (
            filtered.assign(_sort=filtered[sort_col].map(rank).fillna(0))
            .sort_values(["_sort", "MarketCap"], ascending=[ascending, False], na_position="last")
            .drop(columns="_sort")
        )
    else:
        filtered = filtered.sort_values(sort_col, ascending=ascending, na_position="last")

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
card_rows = filtered.iloc[page_start:page_start + CARDS_PER_PAGE]

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

def _performance_cells(row: pd.Series) -> str:
    cells = []
    for metric in PERF_COLS:
        cells.append(
            f'<div class="perf-cell"><span>{escape(metric)}</span>'
            f'<b class="{_tone(row.get(metric))}">{escape(format_pct(row.get(metric)))}</b></div>'
        )
    return "".join(cells)

def _investment_projection(row: pd.Series, principal: float, include_ytd: bool) -> dict | None:
    try:
        principal = float(principal)
    except Exception:
        return None
    if not np.isfinite(principal) or principal <= 0:
        return None

    # Use the most recent contiguous run of completed calendar years.
    # This avoids pretending a partial IPO year or a missing year was a full-year return.
    newest_to_oldest: list[tuple[str, float]] = []
    for year in YEAR_RETURN_COLS:
        value = pd.to_numeric(pd.Series([row.get(year)]), errors="coerce").iloc[0]
        if pd.isna(value) or not np.isfinite(value):
            break
        newest_to_oldest.append((year, float(value)))
    if not newest_to_oldest:
        return None

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

def _investment_html(row: pd.Series) -> str:
    result = _investment_projection(row, investment_amount, include_current_ytd)
    if result is None:
        return '<div class="investment-card"><span>Investment simulation</span><b>Needs a completed calendar year</b></div>'
    end_label = f"{now_et().year} YTD" if result["ytd_applied"] else result["end_year"]
    profit = result["profit"]
    profit_class = "pos" if profit > 0 else ("neg" if profit < 0 else "flat")
    return (
        '<div class="investment-card">'
        f'<span>${investment_amount:,.0f} invested • {result["start_year"]} → {end_label}</span>'
        f'<b>${result["ending_value"]:,.2f}</b>'
        f'<small class="{profit_class}">Profit {profit:+,.2f} ({result["total_pct"]:+.2f}%) • {result["completed_years"]} full year(s)</small>'
        '</div>'
    )

rows = list(card_rows.iterrows())
for r0 in range(0, len(rows), 3):
    cols = st.columns(3)
    for c, (_, row) in zip(cols, rows[r0:r0+3]):
        symbol = str(row["Symbol"])
        safe_symbol = escape(symbol)
        price = f"${float(row['Price']):,.2f}" if pd.notna(row.get("Price")) else "—"
        name = str(row.get("Name") or symbol)
        rating = str(row.get("Analyst Rating") or "Not Rated")
        signal = "LONG BUY" if bool(row.get("Long Buy")) else ("SHORT BUY" if bool(row.get("Short Buy")) else "")
        market_cap = pd.to_numeric(pd.Series([row.get("MarketCap")]), errors="coerce").iloc[0]
        cap_display = f"${market_cap / 1_000_000_000:,.0f}B" if pd.notna(market_cap) else "—"
        with c:
            st.markdown(
                f'''<div class="instrument-card full-metrics-card">
                    <div class="card-top"><span class="ticker">{safe_symbol}</span><span class="asset-type">{escape(str(row.get("Type", "")))}</span></div>
                    <div class="company-name">{escape(name)}</div>
                    <div class="card-quote-row"><span class="price-line">{escape(price)}</span><span class="cap-line">Mkt Cap {escape(cap_display)}</span></div>
                    <div class="performance-grid">{_performance_cells(row)}</div>
                    {_investment_html(row)}
                    <div class="card-bottom"><span class="rating-pill {_rating_class(rating)}">{escape(rating)}</span><span class="signal-pill">{escape(signal)}</span></div>
                </div>''',
                unsafe_allow_html=True,
            )
            if st.button(f"Open {symbol}", key=f"open_{symbol}_{page_start}", use_container_width=True):
                st.session_state.selected_symbol = symbol
                st.rerun()

selected = st.session_state.selected_symbol
if selected and selected in set(market["Symbol"].astype(str)):
    detail_row = market.loc[market["Symbol"].astype(str) == selected].iloc[0]
    detail_price = f"${float(detail_row['Price']):,.2f}" if pd.notna(detail_row.get("Price")) else "—"
    st.markdown(f"<div class='detail-header'><div><span class='detail-kicker'>INSTRUMENT INTELLIGENCE</span><h2>{selected}</h2><p>{detail_row.get('Name','')}</p></div><div class='detail-price'>{detail_price}</div></div>", unsafe_allow_html=True)
    top = st.columns(4)
    top[0].metric("Analyst Rating", str(detail_row.get("Analyst Rating") or "Not Rated"))
    top[1].metric("Sector", str(detail_row.get("Sector") or "—"))
    top[2].metric("Short Signal", "BUY" if bool(detail_row.get("Short Buy")) else "—")
    top[3].metric("Long Signal", "BUY" if bool(detail_row.get("Long Buy")) else "—")

    st.markdown("#### Performance matrix")
    metric_cols = st.columns(5)
    for i, col in enumerate(PERF_COLS):
        metric_cols[i % 5].metric(col, format_pct(detail_row.get(col)))

    st.markdown("#### Investment result")
    detail_projection = _investment_projection(detail_row, investment_amount, include_current_ytd)
    if detail_projection:
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Starting investment", f"${investment_amount:,.2f}")
        d2.metric("Estimated value", f"${detail_projection['ending_value']:,.2f}")
        d3.metric("Profit / loss", f"${detail_projection['profit']:+,.2f}")
        d4.metric("Total return", f"{detail_projection['total_pct']:+.2f}%")
        end_label = f"{now_et().year} YTD" if detail_projection["ytd_applied"] else detail_projection["end_year"]
        st.caption(
            f"Actual adjusted annual returns compounded from {detail_projection['start_year']} through {detail_projection['end_year']}"
            + (f", then {now_et().year} YTD" if detail_projection["ytd_applied"] else "")
            + f" • {detail_projection['completed_years']} completed calendar year(s)."
        )
    else:
        st.info("A completed calendar-year return is required before the investment simulator can calculate this instrument.")

    chart_period = st.segmented_control("Chart range", ["1M", "6M", "1Y", "5Y", "MAX"], default="1Y", key=f"range_{selected}")
    if st.button(f"Load {selected} chart", key=f"chart_{selected}_{chart_period}"):
        with st.spinner(f"Loading {selected} chart..."):
            detail_hist = cached_chart_history(selected, chart_period)
        if detail_hist is not None and not detail_hist.empty and "Close" in detail_hist:
            st.line_chart(pd.to_numeric(detail_hist["Close"], errors="coerce").dropna().rename("Adjusted Close"), use_container_width=True, height=340)
        else:
            st.info("No chart history was returned right now; the persistent snapshot remains available.")
else:
    st.info("Choose an instrument card to open its full short-horizon and 10-calendar-year performance view.")

with st.expander("Data methodology, ratings, persistence & schedule"):
    st.markdown(
        """
- **Universe:** Nasdaq Stock Screener rows with market capitalization strictly above **$100 billion**, plus the 213-ETF CSV allowlist and any manually persisted symbols.
- **Stock analyst rating:** Nasdaq Stock Screener `recommendation` buckets: Strong Buy, Buy, Hold, Sell and Strong Sell.
- **ETF analyst rating:** Nasdaq's public ETF screener does not expose the same stock-style analyst consensus. MarketScope shows **Not Rated** unless the Nasdaq ETF response itself provides a genuine analyst/recommendation field; it does not relabel a fund score or momentum signal as analyst consensus.
- **Rating colors:** Strong Buy/Buy = green; Hold = yellow; Sell/Strong Sell = red; Not Rated = gray.
- **Returns:** Yahoo/yfinance adjusted daily market history. 1D/1M/3M/6M/YTD are point-to-point adjusted returns. The ten year-labeled fields are **actual completed calendar-year returns**, calculated from the adjusted close at the end of the prior year to the adjusted close at the end of that year. They are not CAGR. Stocks do not have NAV. ETF NAV is not shown in the cards; ETF returns use adjusted market history.
- **Investment simulator:** the dollar amount compounds sequentially through the actual completed annual returns available for each instrument. By default the current YTD return is then applied to estimate a current value. No deposits, withdrawals, taxes, fees, or future returns are assumed.
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
