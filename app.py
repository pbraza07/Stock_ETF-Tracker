from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import streamlit as st

from analytics import as_percent, calculate_performance
from providers import YahooFinanceProvider
from universe import is_render_runtime, load_default_universe, load_watchlist, save_watchlist

BASE_DIR = Path(__file__).resolve().parent
SNAPSHOT_FILE = BASE_DIR / "data" / "market_snapshot.csv"

st.set_page_config(
    page_title="MarketScope — Stock & ETF Performance",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"<style>{(BASE_DIR / 'styles.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

provider = YahooFinanceProvider()
default_universe = load_default_universe()
default_meta = default_universe.set_index("Symbol").to_dict(orient="index")
IS_RENDER = is_render_runtime()
RETURN_COLS = ["Since Inception", "10Y Avg", "5Y Avg", "1Y", "YTD", "6M", "3M", "1M", "1D"]


def _symbols_from_url() -> List[str]:
    if not IS_RENDER:
        return []
    try:
        raw = st.query_params.get("symbols", "")
    except Exception:
        return []
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    return list(dict.fromkeys(x.strip().upper() for x in str(raw).split(",") if x.strip()))


def persist_watchlist() -> None:
    save_watchlist(st.session_state.watchlist)
    if IS_RENDER:
        st.query_params["symbols"] = ",".join(st.session_state.watchlist)


if "watchlist" not in st.session_state:
    st.session_state.watchlist = _symbols_from_url() or load_watchlist()
if "live_prices" not in st.session_state:
    st.session_state.live_prices = {}
if "live_refreshed_at" not in st.session_state:
    st.session_state.live_refreshed_at = None
if "session_rows" not in st.session_state:
    st.session_state.session_rows = {}


@st.cache_data(ttl=10 * 60, show_spinner=False)
def load_snapshot() -> pd.DataFrame:
    if not SNAPSHOT_FILE.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(SNAPSHOT_FILE)
    except Exception:
        return pd.DataFrame()
    if "Symbol" not in df.columns:
        return pd.DataFrame()
    df["Symbol"] = df["Symbol"].astype(str).str.upper().str.strip()
    for col in ["Price"] + RETURN_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.drop_duplicates("Symbol", keep="last")


@st.cache_data(ttl=60 * 60, show_spinner=False)
def cached_chart_history(symbol: str, period: str) -> pd.DataFrame:
    return provider.download_chart_history(symbol, period)


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_single_metrics(symbol: str) -> dict:
    histories = provider.download_daily_history([symbol], period="max")
    hist = histories.get(symbol)
    if hist is None or hist.empty:
        return {}
    perf = calculate_performance(hist)
    meta = default_meta.get(symbol, {})
    if not meta:
        meta = provider.get_metadata(symbol)
    latest_date = pd.to_datetime(hist.index[-1]).tz_localize(None)
    return {
        "Symbol": symbol,
        "Name": meta.get("Name") or meta.get("name") or symbol,
        "Sector": meta.get("Sector") or meta.get("sector") or "Unknown",
        "Industry": meta.get("Industry") or meta.get("industry") or "Unknown",
        "Type": meta.get("Type") or meta.get("quote_type") or "Unknown",
        "Price": perf.current_price,
        "Since Inception": as_percent(perf.since_inception),
        "10Y Avg": as_percent(perf.avg_10y),
        "5Y Avg": as_percent(perf.avg_5y),
        "1Y": as_percent(perf.perf_1y),
        "YTD": as_percent(perf.ytd),
        "6M": as_percent(perf.perf_6m),
        "3M": as_percent(perf.perf_3m),
        "1M": as_percent(perf.perf_1m),
        "1D": as_percent(perf.perf_1d),
        "Inception Date": perf.inception_date.date().isoformat() if perf.inception_date is not None else "—",
        "Exchange": meta.get("exchange") or "",
        "Data As Of": latest_date.date().isoformat(),
    }


def blank_row(symbol: str) -> dict:
    meta = default_meta.get(symbol, {})
    return {
        "Symbol": symbol,
        "Name": meta.get("Name", symbol),
        "Sector": meta.get("Sector", "Unknown"),
        "Industry": meta.get("Industry", "Unknown"),
        "Type": meta.get("Type", "Unknown"),
        "Price": np.nan,
        **{c: np.nan for c in RETURN_COLS},
        "Inception Date": "—",
        "Exchange": "",
        "Data As Of": "—",
    }


def assemble_market(symbols: List[str], snapshot: pd.DataFrame) -> pd.DataFrame:
    snap = snapshot.set_index("Symbol", drop=False).to_dict(orient="index") if not snapshot.empty else {}
    rows = []
    for symbol in symbols:
        row = st.session_state.session_rows.get(symbol) or snap.get(symbol) or blank_row(symbol)
        rows.append(dict(row))
    return pd.DataFrame(rows)


def apply_live_overlay(df: pd.DataFrame, prices: Dict[str, float]) -> pd.DataFrame:
    if df.empty or not prices:
        return df
    out = df.copy()
    for idx, row in out.iterrows():
        symbol = row.get("Symbol")
        live = prices.get(symbol)
        old = row.get("Price")
        if live is None or not np.isfinite(live) or live <= 0 or old is None or not np.isfinite(old) or old <= 0:
            continue
        ratio = float(live) / float(old)

        # Point-to-point returns can be updated exactly from the snapshot price ratio.
        for col in ["Since Inception", "1Y", "YTD", "6M", "3M", "1M"]:
            value = row.get(col)
            if value is not None and pd.notna(value):
                out.at[idx, col] = ((1.0 + float(value) / 100.0) * ratio - 1.0) * 100.0

        # CAGR columns use their known fixed horizons.
        for col, years in [("10Y Avg", 10.0), ("5Y Avg", 5.0)]:
            value = row.get(col)
            if value is not None and pd.notna(value):
                factor = (1.0 + float(value) / 100.0) ** years
                if factor > 0:
                    out.at[idx, col] = ((factor * ratio) ** (1.0 / years) - 1.0) * 100.0

        out.at[idx, "1D"] = (ratio - 1.0) * 100.0
        out.at[idx, "Price"] = float(live)
    return out


def format_pct(v):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:+.2f}%"


def style_return(v):
    if v is None or pd.isna(v):
        return "color: #94a3b8;"
    if float(v) > 0:
        return "background-color: rgba(22, 163, 74, .28); color: #dcfce7; font-weight: 700;"
    if float(v) < 0:
        return "background-color: rgba(220, 38, 38, .27); color: #fee2e2; font-weight: 700;"
    return "background-color: rgba(100, 116, 139, .18); color: #e2e8f0; font-weight: 700;"


st.markdown(
    """
    <div class="hero">
      <h1>MarketScope</h1>
      <p>Stocks & ETFs • multi-horizon performance • sector intelligence • zero paid market-data API keys</p>
      <span class="source-pill">● Fast-start snapshot + Yahoo Finance live refresh</span>
    </div>
    """,
    unsafe_allow_html=True,
)

snapshot = load_snapshot()
symbols = list(st.session_state.watchlist)
market = assemble_market(symbols, snapshot)
market = apply_live_overlay(market, st.session_state.live_prices)

with st.sidebar:
    st.subheader("Market controls")
    st.caption("The dashboard opens from a precomputed daily snapshot. Yahoo is contacted only for live refresh, search, a new symbol, or a detail chart.")

    if st.button("⚡ Refresh live prices", use_container_width=True, type="primary"):
        with st.spinner("Refreshing latest Yahoo prices..."):
            st.session_state.live_prices = provider.download_live_prices(st.session_state.watchlist)
            st.session_state.live_refreshed_at = datetime.now()
        st.rerun()

    if st.button("↻ Reload daily snapshot", use_container_width=True):
        load_snapshot.clear()
        st.session_state.live_prices = {}
        st.rerun()

    st.divider()
    st.subheader("Find any stock or ETF")
    with st.form("symbol_search", clear_on_submit=False):
        search_text = st.text_input("Ticker or company name", placeholder="NVDA, Apple, SPY...")
        do_search = st.form_submit_button("Search", use_container_width=True)
    if do_search and search_text:
        with st.spinner("Searching Yahoo Finance..."):
            st.session_state.search_results = provider.search(search_text, max_results=8)
    results = st.session_state.get("search_results", [])
    if results:
        labels = [f"{r['symbol']} — {r['name']} ({r.get('quote_type','')})" for r in results]
        selected_label = st.selectbox("Matches", labels)
        selected = results[labels.index(selected_label)]
        if st.button("＋ Add to tracker", use_container_width=True):
            symbol = selected["symbol"]
            if symbol not in st.session_state.watchlist:
                st.session_state.watchlist.append(symbol)
                persist_watchlist()
            st.rerun()

    st.divider()
    if st.button("Reset default tracker", use_container_width=True):
        st.session_state.watchlist = default_universe["Symbol"].astype(str).tolist()
        if IS_RENDER:
            try:
                del st.query_params["symbols"]
            except Exception:
                pass
        else:
            save_watchlist(st.session_state.watchlist)
        st.session_state.live_prices = {}
        st.session_state.session_rows = {}
        st.rerun()

# Freshness banner is intentionally before any network work.
valid_dates = market.loc[market["Data As Of"].astype(str) != "—", "Data As Of"].astype(str).tolist() if "Data As Of" in market else []
if valid_dates:
    latest_snapshot = max(valid_dates)
    st.success(f"Daily performance snapshot loaded instantly • market data through {latest_snapshot} • use Live Refresh for the newest available Yahoo quote.")
else:
    st.warning("The repository does not yet contain a populated daily snapshot. Run the GitHub Action 'Update market snapshot' once, or redeploy so the Render build can create it.")

missing = market.loc[market["Price"].isna(), "Symbol"].tolist() if "Price" in market else symbols
if missing:
    st.info(f"{len(missing)} symbol(s) are not in the current snapshot: {', '.join(missing[:8])}{'…' if len(missing) > 8 else ''}")
    if st.button("Load missing symbols now", type="secondary"):
        progress = st.progress(0.0, text="Loading only missing symbols...")
        for i, symbol in enumerate(missing, start=1):
            row = cached_single_metrics(symbol)
            if row:
                st.session_state.session_rows[symbol] = row
            progress.progress(i / len(missing), text=f"Loaded {i}/{len(missing)}")
        progress.empty()
        st.rerun()

# Filters
filter_col1, filter_col2, filter_col3 = st.columns([1.15, 1.15, 2.2])
with filter_col1:
    sectors = sorted(x for x in market["Sector"].dropna().unique().tolist() if x)
    selected_sectors = st.multiselect("Sector", sectors, placeholder="All sectors")
with filter_col2:
    instrument_filter = st.selectbox("Instrument", ["All", "Stocks", "ETFs / Funds"])
with filter_col3:
    table_search = st.text_input("Filter current tracker", placeholder="Search symbol, name, sector or industry")

filtered = market.copy()
if selected_sectors:
    filtered = filtered[filtered["Sector"].isin(selected_sectors)]
if instrument_filter == "ETFs / Funds":
    filtered = filtered[filtered["Industry"].eq("ETF / Fund")]
elif instrument_filter == "Stocks":
    filtered = filtered[~filtered["Industry"].eq("ETF / Fund")]
if table_search:
    q = table_search.strip().lower()
    mask = (
        filtered["Symbol"].astype(str).str.lower().str.contains(q, regex=False)
        | filtered["Name"].astype(str).str.lower().str.contains(q, regex=False)
        | filtered["Sector"].astype(str).str.lower().str.contains(q, regex=False)
        | filtered["Industry"].astype(str).str.lower().str.contains(q, regex=False)
    )
    filtered = filtered[mask]

k1, k2, k3, k4 = st.columns(4)
k1.metric("Tracked", len(market))
k2.metric("Showing", len(filtered))
k3.metric("Positive today", int((filtered["1D"] > 0).sum()) if len(filtered) else 0)
k4.metric("Negative today", int((filtered["1D"] < 0).sum()) if len(filtered) else 0)

if st.session_state.live_refreshed_at:
    st.caption(f"Latest live refresh: {st.session_state.live_refreshed_at.strftime('%b %d, %Y %I:%M:%S %p')} local time")
else:
    st.caption("Startup uses the saved daily snapshot and does not wait for Yahoo Finance.")

display_cols = ["Symbol", "Name", "Sector", "Industry", "Price"] + RETURN_COLS
styled = filtered[display_cols].style.map(style_return, subset=RETURN_COLS)
st.dataframe(
    styled,
    use_container_width=True,
    height=620,
    hide_index=True,
    column_config={
        "Symbol": st.column_config.TextColumn("Symbol", pinned="left", width="small"),
        "Name": st.column_config.TextColumn("Name", pinned="left", width="medium"),
        "Sector": st.column_config.TextColumn("Sector", width="medium"),
        "Industry": st.column_config.TextColumn("Industry", width="medium"),
        "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
        "Since Inception": st.column_config.NumberColumn("Since Inception", format="%+.2f%%"),
        "10Y Avg": st.column_config.NumberColumn("10Y Avg", format="%+.2f%%"),
        "5Y Avg": st.column_config.NumberColumn("5Y Avg", format="%+.2f%%"),
        "1Y": st.column_config.NumberColumn("1Y", format="%+.2f%%"),
        "YTD": st.column_config.NumberColumn("YTD", format="%+.2f%%"),
        "6M": st.column_config.NumberColumn("6M", format="%+.2f%%"),
        "3M": st.column_config.NumberColumn("3M", format="%+.2f%%"),
        "1M": st.column_config.NumberColumn("1M", format="%+.2f%%"),
        "1D": st.column_config.NumberColumn("1D", format="%+.2f%%"),
    },
)

st.markdown("### Symbol detail")
detail_options = filtered["Symbol"].tolist() if len(filtered) else market["Symbol"].tolist()
if detail_options:
    detail_symbol = st.selectbox("Inspect", detail_options)
    detail_row = market.loc[market["Symbol"] == detail_symbol].iloc[0]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Price", f"${detail_row['Price']:,.2f}" if pd.notna(detail_row["Price"]) else "—")
    c2.metric("1D", format_pct(detail_row["1D"]))
    c3.metric("YTD", format_pct(detail_row["YTD"]))
    c4.metric("1Y", format_pct(detail_row["1Y"]))
    c5.metric("5Y avg", format_pct(detail_row["5Y Avg"]))

    chart_period = st.segmented_control("Chart range", ["1M", "6M", "1Y", "5Y", "MAX"], default="1Y")
    if st.button(f"Load {detail_symbol} chart", key=f"chart_{detail_symbol}_{chart_period}"):
        st.session_state.chart_request = (detail_symbol, chart_period)

    if st.session_state.get("chart_request") == (detail_symbol, chart_period):
        with st.spinner(f"Loading {detail_symbol} chart only..."):
            detail_hist = cached_chart_history(detail_symbol, chart_period)
        if detail_hist is not None and not detail_hist.empty and "Close" in detail_hist:
            close = pd.to_numeric(detail_hist["Close"], errors="coerce").dropna().rename("Adjusted Close")
            st.line_chart(close, use_container_width=True, height=320)
        else:
            st.info("Yahoo did not return chart history for this symbol right now. The main snapshot remains available.")

with st.expander("Why this version starts faster"):
    st.markdown(
        """
- The main table reads **one small CSV snapshot from the deployed app**, so it appears without downloading decades of history.
- A scheduled **GitHub Action** refreshes the expensive long-history calculations after the market closes.
- **Live Refresh** downloads only the newest intraday prices and mathematically overlays them on the saved metrics.
- Search runs only after you press **Search**, instead of sending a Yahoo request on every keystroke.
- Detail chart history loads for **one selected symbol only**, and only when you ask for it.
- If Yahoo is temporarily rate-limiting Render, the last successful snapshot still loads instead of showing an empty dashboard.
        """
    )

with st.expander("Manage tracker symbols"):
    remove_symbols = st.multiselect("Select symbols to remove", st.session_state.watchlist)
    if st.button("Remove selected", disabled=not remove_symbols):
        st.session_state.watchlist = [s for s in st.session_state.watchlist if s not in remove_symbols]
        persist_watchlist()
        st.session_state.live_prices = {}
        st.rerun()

st.markdown("---")
st.markdown(
    "<div class='small-note'>MarketScope is an informational dashboard, not investment advice. Free website data can be delayed or rate-limited. Verify order-critical prices with your broker.</div>",
    unsafe_allow_html=True,
)
