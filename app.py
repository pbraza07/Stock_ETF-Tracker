from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import streamlit as st

from analytics import as_percent, calculate_performance
from persistence import format_et, load_remote_metadata, load_remote_snapshot, now_et, persist_snapshot
from providers import YahooFinanceProvider
from providers.nasdaq import NasdaqScreenerProvider
from universe import is_render_runtime, load_default_universe

BASE_DIR = Path(__file__).resolve().parent
SNAPSHOT_FILE = BASE_DIR / "data" / "market_snapshot.csv"
SNAPSHOT_META_FILE = BASE_DIR / "data" / "snapshot_metadata.json"
PERF_COLS = ["10Y Avg", "5Y Avg", "1Y", "YTD", "6M", "3M", "1M", "1D"]
ALL_RETURN_COLS = ["Since Inception"] + PERF_COLS
RATINGS = ["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell", "Not Rated"]

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


def _normalize_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "Symbol" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["Symbol"] = df["Symbol"].astype(str).str.upper().str.strip()
    numeric = ["MarketCap", "Price", "NAV"] + ALL_RETURN_COLS
    for col in numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["Analyst Rating", "Rating Source", "Rating Updated ET", "Snapshot Updated ET"]:
        if col not in df.columns:
            df[col] = "Not Rated" if col == "Analyst Rating" else "—"
    df["Analyst Rating"] = df["Analyst Rating"].fillna("Not Rated").replace({"": "Not Rated", "nan": "Not Rated"})
    return df.drop_duplicates("Symbol", keep="last")


@st.cache_data(ttl=60, show_spinner=False)
def load_snapshot() -> pd.DataFrame:
    # Fast startup: Render serves the most recently deployed snapshot immediately.
    # GitHub remains the durable source of truth for scheduled/manual refreshes.
    if SNAPSHOT_FILE.exists():
        try:
            local = _normalize_snapshot(pd.read_csv(SNAPSHOT_FILE))
            if not local.empty:
                return local
        except Exception:
            pass
    return _normalize_snapshot(load_remote_snapshot())


@st.cache_data(ttl=60, show_spinner=False)
def load_snapshot_metadata() -> dict:
    try:
        if SNAPSHOT_META_FILE.exists():
            payload = json.loads(SNAPSHOT_META_FILE.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload:
                return payload
    except Exception:
        pass
    return load_remote_metadata()


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
        "10Y Avg": as_percent(perf.avg_10y),
        "5Y Avg": as_percent(perf.avg_5y),
        "1Y": as_percent(perf.perf_1y),
        "YTD": as_percent(perf.ytd),
        "6M": as_percent(perf.perf_6m),
        "3M": as_percent(perf.perf_3m),
        "1M": as_percent(perf.perf_1m),
        "1D": as_percent(perf.perf_1d),
        "Return Basis": "Adjusted market total return" if instrument_type == "ETF" else "Adjusted total return",
        "Inception Date": perf.inception_date.date().isoformat() if perf.inception_date is not None else "—",
        "Exchange": provider_meta.get("exchange") or "",
        "Data As Of": latest_date.date().isoformat(),
        "Snapshot Updated ET": format_et(),
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
    return df


def apply_live_overlay(df: pd.DataFrame, prices: Dict[str, float]) -> pd.DataFrame:
    if df.empty or not prices:
        return df
    out = df.copy()
    today_et = now_et().date().isoformat()
    for idx, row in out.iterrows():
        live = prices.get(row.get("Symbol"))
        old = row.get("Price")
        if live is None or not np.isfinite(live) or live <= 0 or old is None or not np.isfinite(old) or old <= 0:
            continue
        ratio = float(live) / float(old)
        for col in ["Since Inception", "1Y", "YTD", "6M", "3M", "1M"]:
            value = row.get(col)
            if value is not None and pd.notna(value):
                out.at[idx, col] = ((1.0 + float(value) / 100.0) * ratio - 1.0) * 100.0
        for col, years in [("10Y Avg", 10.0), ("5Y Avg", 5.0)]:
            value = row.get(col)
            if value is not None and pd.notna(value):
                factor = (1.0 + float(value) / 100.0) ** years
                if factor > 0:
                    out.at[idx, col] = ((factor * ratio) ** (1.0 / years) - 1.0) * 100.0
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
            "Choose any displayed columns. Numeric columns get min/max filters; "
            "text/categorical columns get value or contains filters. Table headers remain sortable."
        )
        chosen = st.multiselect("Columns to filter", display_cols, key="advanced_filter_columns")
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
                if len(unique) <= 100:
                    values = st.multiselect(f"{col} values", unique, key=f"fcat_{col}")
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
  <p>Stocks & ETFs • multi-horizon returns • Nasdaq analyst consensus • persistent cloud snapshot</p>
  <span class="source-pill">● Nasdaq screener + Yahoo Finance • all displayed times: U.S. Eastern</span>
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

with st.sidebar:
    st.subheader("Market controls")
    st.caption("Fast startup uses the last saved snapshot. The full scheduled refresh runs every day at 6:00 PM America/New_York.")
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
    (st.success if ok else st.warning)(msg)
    st.session_state.persistence_message = None

if st.session_state.last_refresh_summary:
    st.success(st.session_state.last_refresh_summary)
    st.session_state.last_refresh_summary = None

st.info(
    "Analyst Rating: stocks use Nasdaq Stock Screener consensus buckets (Strong Buy / Buy / Hold / Sell / Strong Sell). "
    "Nasdaq's public ETF screener does not expose the same stock-style analyst consensus; ETFs remain Not Rated unless "
    "Nasdaq itself returns a genuine analyst/recommendation field."
)

# Quick filters.
f1, f2, f3, f4, f5 = st.columns([1.1, 1.0, 1.25, 1.25, 1.8])
with f1:
    sectors = sorted(x for x in market["Sector"].dropna().astype(str).unique().tolist() if x and x != "nan")
    selected_sectors = st.multiselect("Sector", sectors, placeholder="All sectors")
with f2:
    instrument_filter = st.selectbox("Instrument", ["All", "Stocks", "ETFs"])
with f3:
    rating_filter = st.multiselect("Analyst Rating", RATINGS, placeholder="All ratings")
with f4:
    cap_filter = st.selectbox("Stock market cap", ["> $100M universe", "> $1B", "> $10B", "> $100B"])
with f5:
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

cap_thresholds = {
    "> $100M universe": 100_000_000,
    "> $1B": 1_000_000_000,
    "> $10B": 10_000_000_000,
    "> $100B": 100_000_000_000,
}
if cap_filter != "> $100M universe":
    threshold = cap_thresholds[cap_filter]
    filtered = filtered[(filtered["Type"].eq("ETF")) | (pd.to_numeric(filtered["MarketCap"], errors="coerce") > threshold)]
if table_search:
    q = table_search.strip().lower()
    searchable = ["Symbol", "Name", "Sector", "Industry", "Analyst Rating", "Rating Source", "Return Basis"]
    mask = pd.Series(False, index=filtered.index)
    for col in searchable:
        if col in filtered.columns:
            mask |= filtered[col].astype(str).str.lower().str.contains(q, regex=False, na=False)
    filtered = filtered[mask]

filtered["Market Cap ($B)"] = pd.to_numeric(filtered["MarketCap"], errors="coerce") / 1_000_000_000
DISPLAY_COLS = [
    "Symbol", "Name", "Type", "Sector", "Industry", "Analyst Rating", "Market Cap ($B)", "Price", "NAV",
    "Since Inception", "10Y Avg", "5Y Avg", "1Y", "YTD", "6M", "3M", "1M", "1D",
    "Return Basis", "Rating Source", "Rating Updated ET", "Data As Of", "Snapshot Updated ET",
]
filtered = apply_dynamic_filters(filtered, DISPLAY_COLS)

valid_prices = pd.to_numeric(market["Price"], errors="coerce").notna()
stock_count = int((default_universe["Type"] == "Stock").sum())
etf_count = int((default_universe["Type"] == "ETF").sum())
rated_count = int(market["Analyst Rating"].isin(["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"]).sum())
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Universe", f"{len(market):,}")
k2.metric("Stocks > $100M", f"{stock_count:,}")
k3.metric("ETFs", f"{etf_count:,}")
k4.metric("Rated", f"{rated_count:,}")
k5.metric("Snapshot populated", f"{int(valid_prices.sum()):,}")
k6.metric("Showing", f"{len(filtered):,}")

updated_display = metadata.get("updated_at_display_et")
if not updated_display and "Snapshot Updated ET" in market.columns:
    vals = [x for x in market["Snapshot Updated ET"].dropna().astype(str).tolist() if x not in {"", "—", "nan"}]
    updated_display = vals[-1] if vals else None
if updated_display:
    st.success(f"Persistent snapshot ready • last refresh: {updated_display} • timezone: U.S. Eastern (America/New_York).")
else:
    st.warning("Persistent snapshot timestamp is not available yet. Run the GitHub Action once.")

# Manual refresh with visible instrument count and percentage.
rc1, rc2, rc3 = st.columns([1.8, 1.7, 3.5])
with rc1:
    refresh_scope = st.selectbox(
        "Manual refresh scope",
        ["Filtered / shown results", "Entire tracked universe"],
        help=(
            "Refreshing the full 4,000+ instrument universe can take longer and can encounter free-source throttling. "
            "The scheduled 6 PM ET job always refreshes the full universe."
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
    prices: Dict[str, float] = {}
    processed = 0
    batch_size = 50

    for start in range(0, total, batch_size):
        batch = targets[start:start + batch_size]
        try:
            got = provider.download_live_prices(batch)
        except Exception:
            got = {}
        prices.update(got)
        processed += len(batch)
        pct = processed / total if total else 1.0
        progress.progress(
            min(0.90, pct * 0.90),
            text=f"Market prices: {processed:,} / {total:,} processed ({pct*100:.1f}%)",
        )
        counter.caption(
            f"Stocks: {target_stocks:,} • ETFs: {target_etfs:,} • prices returned: {len(prices):,} / {processed:,} processed"
        )

    refreshed = apply_live_overlay(market_base, prices)
    progress.progress(0.94, text=f"Price stage complete • refreshing Nasdaq analyst ratings for {total:,} instruments...")
    refreshed = refresh_ratings(refreshed, targets)
    progress.progress(0.97, text="Ratings refreshed • saving the complete persistent snapshot...")

    stamp = format_et()
    refreshed.loc[refreshed["Symbol"].isin(targets), "Snapshot Updated ET"] = stamp
    ok, msg = persist_snapshot(refreshed, SNAPSHOT_FILE, "Manual app refresh", len(prices))
    st.session_state.live_prices = {}
    st.session_state.manual_refreshed_at = now_et()
    st.session_state.persistence_message = (ok, msg)
    st.session_state.last_refresh_summary = (
        f"Manual refresh completed at {format_et(st.session_state.manual_refreshed_at)} • "
        f"{total:,}/{total:,} instruments processed (100%) • {len(prices):,} prices returned • "
        f"Stocks {target_stocks:,} • ETFs {target_etfs:,}."
    )
    load_snapshot.clear()
    load_snapshot_metadata.clear()
    progress.progress(1.0, text=f"Refresh complete: {total:,} / {total:,} processed (100.0%) • {len(prices):,} prices returned")
    counter.caption(f"Completed at {format_et(st.session_state.manual_refreshed_at)} • Stocks: {target_stocks:,} • ETFs: {target_etfs:,}")
    st.rerun()

if st.session_state.manual_refreshed_at:
    st.caption(f"Last manual refresh: {format_et(st.session_state.manual_refreshed_at)}")

# Main sortable table.
for col in DISPLAY_COLS:
    if col not in filtered.columns:
        filtered[col] = pd.NA
styled = (
    filtered[DISPLAY_COLS]
    .style.map(style_return, subset=[c for c in ALL_RETURN_COLS if c in filtered.columns])
    .map(style_rating, subset=["Analyst Rating"])
)
st.dataframe(
    styled,
    use_container_width=True,
    height=680,
    hide_index=True,
    column_config={
        "Symbol": st.column_config.TextColumn("Symbol", pinned="left", width="small"),
        "Name": st.column_config.TextColumn("Name", pinned="left", width="medium"),
        "Analyst Rating": st.column_config.TextColumn("Analyst Rating", width="small"),
        "Market Cap ($B)": st.column_config.NumberColumn("Market Cap ($B)", format="$%.2f"),
        "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
        "NAV": st.column_config.NumberColumn("NAV", format="$%.2f"),
        **{c: st.column_config.NumberColumn(c, format="%+.2f%%") for c in ALL_RETURN_COLS},
        "Data As Of": st.column_config.TextColumn("Data As Of (ET)", width="small"),
    },
)

st.markdown("### Symbol detail")
detail_options = filtered["Symbol"].tolist() if len(filtered) else market["Symbol"].tolist()
if detail_options:
    detail_symbol = st.selectbox("Inspect", detail_options)
    detail_row = market.loc[market["Symbol"] == detail_symbol].iloc[0]
    d1, d2, d3, d4, d5, d6, d7 = st.columns(7)
    d1.metric("Price", f"${detail_row['Price']:,.2f}" if pd.notna(detail_row["Price"]) else "—")
    d2.metric("Rating", str(detail_row.get("Analyst Rating") or "Not Rated"))
    d3.metric("1D", format_pct(detail_row["1D"]))
    d4.metric("YTD", format_pct(detail_row["YTD"]))
    d5.metric("1Y", format_pct(detail_row["1Y"]))
    d6.metric("5Y avg", format_pct(detail_row["5Y Avg"]))
    nav = detail_row.get("NAV")
    d7.metric("NAV", f"${float(nav):,.2f}" if nav is not None and pd.notna(nav) else "—")
    st.caption(
        f"Rating source: {detail_row.get('Rating Source','—')} • rating updated: {detail_row.get('Rating Updated ET','—')} "
        f"• snapshot updated: {detail_row.get('Snapshot Updated ET','—')}"
    )

    chart_period = st.segmented_control("Chart range", ["1M", "6M", "1Y", "5Y", "MAX"], default="1Y")
    if st.button(f"Load {detail_symbol} chart", key=f"chart_{detail_symbol}_{chart_period}"):
        with st.spinner(f"Loading {detail_symbol} chart..."):
            detail_hist = cached_chart_history(detail_symbol, chart_period)
        if detail_hist is not None and not detail_hist.empty and "Close" in detail_hist:
            st.line_chart(
                pd.to_numeric(detail_hist["Close"], errors="coerce").dropna().rename("Adjusted Close"),
                use_container_width=True,
                height=320,
            )
        else:
            st.info("No chart history was returned right now; the persistent snapshot remains available.")

with st.expander("Data methodology, ratings, persistence & schedule"):
    st.markdown(
        """
- **Universe:** Nasdaq Stock Screener rows with market capitalization strictly above **$100 million**, plus the requested ETF allowlist and any manually persisted symbols.
- **Stock analyst rating:** Nasdaq Stock Screener `recommendation` buckets: Strong Buy, Buy, Hold, Sell and Strong Sell.
- **ETF analyst rating:** Nasdaq's public ETF screener does not expose the same stock-style analyst consensus. MarketScope shows **Not Rated** unless the Nasdaq ETF response itself provides a genuine analyst/recommendation field; it does not relabel a fund score or momentum signal as analyst consensus.
- **Rating colors:** Strong Buy/Buy = green; Hold = yellow; Sell/Strong Sell = red; Not Rated = gray.
- **Returns:** Yahoo/yfinance adjusted daily market history. 10Y/5Y are annualized CAGR; 1Y/YTD/6M/3M/1M/1D are point-to-point adjusted total returns. Stocks do not have NAV; ETF NAV is displayed separately when available.
- **Persistent data:** the daily GitHub Action commits `data/default_universe.csv`, `data/market_snapshot.csv`, and `data/snapshot_metadata.json`. Render serves the local snapshot immediately; GitHub is the durable source of truth.
- **Manual persistence:** configure the Render secret `MARKETSCOPE_GITHUB_TOKEN` (fine-grained token, Contents read/write on this repository) so manual refreshes and manually added symbols are committed to the same persistent snapshot.
- **Schedule:** every calendar day at **6:00 PM America/New_York**. All displayed refresh/rating timestamps use U.S. Eastern time.
        """
    )

st.markdown("---")
st.markdown(
    "<div class='small-note'>MarketScope is informational, not investment advice. Analyst consensus is an opinion summary, not a guarantee. Free public data can be delayed, unavailable, or revised. Verify order-critical prices with your broker and ETF NAV with the fund issuer.</div>",
    unsafe_allow_html=True,
)
