from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from analytics import as_percent, calculate_performance
from providers import YahooFinanceProvider
from universe import is_render_runtime, load_default_universe, load_watchlist, save_watchlist

BASE_DIR = Path(__file__).resolve().parent

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
        # Render Free files are ephemeral, so encode the current list in the URL.
        # Bookmarking the resulting URL restores the same tracker after a restart.
        st.query_params["symbols"] = ",".join(st.session_state.watchlist)


if "watchlist" not in st.session_state:
    st.session_state.watchlist = _symbols_from_url() or load_watchlist()
if "live_prices" not in st.session_state:
    st.session_state.live_prices = {}
if "live_refreshed_at" not in st.session_state:
    st.session_state.live_refreshed_at = None
if "refresh_nonce" not in st.session_state:
    st.session_state.refresh_nonce = 0

# Daily rerun while the app is open. The 24-hour cache below ensures a fresh daily
# history pull while avoiding repeated downloads during normal interaction.
st_autorefresh(interval=24 * 60 * 60 * 1000, key="daily_market_refresh")


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_history(symbols_tuple: tuple[str, ...], refresh_nonce: int) -> Dict[str, pd.DataFrame]:
    return provider.download_daily_history(symbols_tuple)


@st.cache_data(ttl=7 * 24 * 60 * 60, show_spinner=False)
def cached_metadata(symbol: str) -> dict:
    if symbol in default_meta:
        row = default_meta[symbol]
        return {
            "symbol": symbol,
            "name": row.get("Name", symbol),
            "sector": row.get("Sector", "Unknown"),
            "industry": row.get("Industry", "Unknown"),
            "quote_type": row.get("Type", "Unknown").upper(),
            "exchange": "",
            "currency": "USD",
            "exchange_delay_minutes": None,
            "market_state": "Unknown",
        }
    return provider.get_metadata(symbol)


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


def build_market_frame(symbols: List[str], histories: Dict[str, pd.DataFrame], live_prices: Dict[str, float]) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        hist = histories.get(symbol)
        if hist is None or hist.empty:
            continue
        meta = cached_metadata(symbol)
        perf = calculate_performance(hist, live_prices.get(symbol))
        rows.append(
            {
                "Symbol": symbol,
                "Name": meta.get("name") or symbol,
                "Sector": meta.get("sector") or "Unknown",
                "Industry": meta.get("industry") or "Unknown",
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
            }
        )
    return pd.DataFrame(rows)


st.markdown(
    """
    <div class="hero">
      <h1>MarketScope</h1>
      <p>Stocks & ETFs • multi-horizon performance • sector intelligence • zero paid data API keys</p>
      <span class="source-pill">● Primary source: Yahoo Finance via yfinance</span>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("Market controls")
    st.caption("Your table is sortable by clicking any column header.")
    if IS_RENDER:
        st.caption("☁️ Render mode: watchlist changes are mirrored into this page URL. Bookmark the URL to reopen the same custom tracker.")

    if st.button("⚡ Refresh live prices", use_container_width=True, type="primary"):
        with st.spinner("Refreshing latest intraday prices..."):
            st.session_state.live_prices = provider.download_live_prices(st.session_state.watchlist)
            st.session_state.live_refreshed_at = datetime.now()
        st.rerun()

    if st.button("↻ Force full daily refresh", use_container_width=True):
        st.cache_data.clear()
        st.session_state.refresh_nonce += 1
        st.session_state.live_prices = {}
        st.session_state.live_refreshed_at = None
        st.rerun()

    st.divider()
    st.subheader("Find any stock or ETF")
    search_text = st.text_input("Ticker or company name", placeholder="NVDA, Apple, SPY...")
    if search_text:
        with st.spinner("Searching Yahoo Finance..."):
            results = provider.search(search_text, max_results=8)
        if results:
            labels = [f"{r['symbol']} — {r['name']} ({r.get('quote_type','')})" for r in results]
            selected_label = st.selectbox("Matches", labels)
            selected = results[labels.index(selected_label)]
            if st.button("＋ Add to tracker", use_container_width=True):
                symbol = selected["symbol"]
                if symbol not in st.session_state.watchlist:
                    st.session_state.watchlist.append(symbol)
                    persist_watchlist()
                    st.cache_data.clear()
                st.rerun()
        else:
            st.info("No matching U.S. stock/ETF result was returned.")

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
        st.cache_data.clear()
        st.session_state.live_prices = {}
        st.rerun()

symbols = tuple(st.session_state.watchlist)
with st.spinner("Loading adjusted market history..."):
    histories = cached_history(symbols, st.session_state.refresh_nonce)

market = build_market_frame(list(symbols), histories, st.session_state.live_prices)

if market.empty:
    st.error("No market data was returned. Yahoo Finance may be temporarily rate-limiting requests. Try Refresh again later or reset the default tracker.")
    st.stop()

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
        filtered["Symbol"].str.lower().str.contains(q, regex=False)
        | filtered["Name"].str.lower().str.contains(q, regex=False)
        | filtered["Sector"].str.lower().str.contains(q, regex=False)
        | filtered["Industry"].str.lower().str.contains(q, regex=False)
    )
    filtered = filtered[mask]

# KPI strip
k1, k2, k3, k4 = st.columns(4)
k1.metric("Tracked", len(market))
k2.metric("Showing", len(filtered))
positive_1d = int((filtered["1D"] > 0).sum()) if len(filtered) else 0
negative_1d = int((filtered["1D"] < 0).sum()) if len(filtered) else 0
k3.metric("Positive today", positive_1d)
k4.metric("Negative today", negative_1d)

if st.session_state.live_refreshed_at:
    st.caption(f"Latest manual intraday refresh: {st.session_state.live_refreshed_at.strftime('%b %d, %Y %I:%M:%S %p')} local time")
else:
    st.caption("Performance uses the latest available adjusted daily close. Click **Refresh live prices** to overlay the newest available intraday quote.")

return_cols = ["Since Inception", "10Y Avg", "5Y Avg", "1Y", "YTD", "6M", "3M", "1M", "1D"]
display_cols = ["Symbol", "Name", "Sector", "Industry", "Price"] + return_cols

styled = filtered[display_cols].style
styled = styled.format({"Price": "${:,.2f}", **{c: format_pct for c in return_cols}}, na_rep="—")
for c in return_cols:
    styled = styled.map(style_return, subset=[c])

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
        "Since Inception": st.column_config.NumberColumn("Since Inception", format="%+.2f%%", help="Cumulative adjusted-price return from first available Yahoo Finance history."),
        "10Y Avg": st.column_config.NumberColumn("10Y Avg", format="%+.2f%%", help="Annualized CAGR over approximately 10 years; blank when history is insufficient."),
        "5Y Avg": st.column_config.NumberColumn("5Y Avg", format="%+.2f%%", help="Annualized CAGR over approximately 5 years; blank when history is insufficient."),
        "1Y": st.column_config.NumberColumn("1Y", format="%+.2f%%", help="Adjusted total price return over approximately 1 year."),
        "YTD": st.column_config.NumberColumn("YTD", format="%+.2f%%", help="Adjusted return versus the prior year-end trading close."),
        "6M": st.column_config.NumberColumn("6M", format="%+.2f%%"),
        "3M": st.column_config.NumberColumn("3M", format="%+.2f%%"),
        "1M": st.column_config.NumberColumn("1M", format="%+.2f%%"),
        "1D": st.column_config.NumberColumn("1D", format="%+.2f%%"),
    },
)

st.markdown("### Symbol detail")
detail_symbol = st.selectbox("Inspect", filtered["Symbol"].tolist() if len(filtered) else market["Symbol"].tolist())
detail_row = market.loc[market["Symbol"] == detail_symbol].iloc[0]
detail_hist = histories.get(detail_symbol, pd.DataFrame())

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Price", f"${detail_row['Price']:,.2f}" if pd.notna(detail_row["Price"]) else "—")
c2.metric("1D", format_pct(detail_row["1D"]))
c3.metric("YTD", format_pct(detail_row["YTD"]))
c4.metric("1Y", format_pct(detail_row["1Y"]))
c5.metric("5Y avg", format_pct(detail_row["5Y Avg"]))

if detail_hist is not None and not detail_hist.empty and "Close" in detail_hist:
    chart_period = st.segmented_control("Chart range", ["1M", "6M", "1Y", "5Y", "MAX"], default="1Y")
    close = pd.to_numeric(detail_hist["Close"], errors="coerce").dropna().rename("Adjusted Close")
    now = pd.Timestamp.now().tz_localize(None)
    offsets = {
        "1M": pd.DateOffset(months=1),
        "6M": pd.DateOffset(months=6),
        "1Y": pd.DateOffset(years=1),
        "5Y": pd.DateOffset(years=5),
    }
    if chart_period != "MAX":
        start = now - offsets[chart_period]
        close = close.loc[pd.to_datetime(close.index).tz_localize(None) >= start]
    st.line_chart(close, use_container_width=True, height=320)

    meta = cached_metadata(detail_symbol)
    delay = meta.get("exchange_delay_minutes")
    delay_text = "provider did not report a delay flag" if delay is None else ("real-time flag (0 min delay)" if delay == 0 else f"reported delay: {delay} min")
    st.caption(
        f"{detail_row['Name']} • {detail_row['Sector']} • {detail_row['Industry']} • "
        f"History begins {detail_row['Inception Date']} • {delay_text}."
    )

with st.expander("Methodology & data-quality notes"):
    st.markdown(
        """
- **Source:** Yahoo Finance through the open-source `yfinance` package. No paid API key is required.
- **Adjusted history:** daily prices use `auto_adjust=True` so historical comparisons account for splits and distributions as provided by Yahoo/yfinance.
- **Since Inception:** cumulative adjusted-price return from first available history.
- **10Y Avg / 5Y Avg:** CAGR (annualized compounded return), not a simple arithmetic average.
- **1Y / YTD / 6M / 3M / 1M / 1D:** point-to-point adjusted returns using the nearest available prior trading close.
- **Live Refresh:** overlays the latest available 1-minute intraday observation. Availability and delay depend on the exchange and Yahoo's feed.
- **Daily refresh:** historical data is cached for 24 hours and automatically expires; the app also reruns daily while open.
- No free public website can guarantee zero discrepancies against every brokerage or consolidated exchange feed. Always verify order-critical prices with your broker.
        """
    )

with st.expander("Manage tracker symbols"):
    remove_symbols = st.multiselect("Select symbols to remove", st.session_state.watchlist)
    if st.button("Remove selected", disabled=not remove_symbols):
        st.session_state.watchlist = [s for s in st.session_state.watchlist if s not in remove_symbols]
        persist_watchlist()
        st.cache_data.clear()
        st.session_state.live_prices = {}
        st.rerun()

st.markdown("---")
st.markdown(
    "<div class='small-note'>MarketScope is an informational dashboard, not investment advice. Yahoo Finance availability, delays and terms apply. This build does not require a paid market-data API subscription. GitHub + Render deployment is supported.</div>",
    unsafe_allow_html=True,
)
