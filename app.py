from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import streamlit as st

from analytics import as_percent, calculate_performance
from providers import YahooFinanceProvider
from universe import is_render_runtime, load_default_universe

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
PERF_COLS = ["10Y Avg", "5Y Avg", "1Y", "YTD", "6M", "3M", "1M", "1D"]
ALL_RETURN_COLS = ["Since Inception"] + PERF_COLS


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
if "live_refreshed_at" not in st.session_state:
    st.session_state.live_refreshed_at = None
if "session_rows" not in st.session_state:
    st.session_state.session_rows = {}
if "search_results" not in st.session_state:
    st.session_state.search_results = []


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
    numeric = ["MarketCap", "Price", "NAV"] + ALL_RETURN_COLS
    for col in numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.drop_duplicates("Symbol", keep="last")


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
    latest_date = pd.to_datetime(hist.index[-1])
    try:
        latest_date = latest_date.tz_localize(None)
    except TypeError:
        try:
            latest_date = latest_date.tz_convert(None)
        except TypeError:
            pass
    instrument_type = meta.get("Type") or ("ETF" if provider_meta.get("quote_type") in {"ETF", "MUTUALFUND"} else "Stock")
    return {
        "Symbol": symbol,
        "Name": meta.get("Name") or provider_meta.get("name") or symbol,
        "Sector": meta.get("Sector") or provider_meta.get("sector") or "Unknown",
        "Industry": meta.get("Industry") or provider_meta.get("industry") or "Unknown",
        "Type": instrument_type,
        "MarketCap": meta.get("MarketCap", np.nan),
        "Price": perf.current_price,
        "NAV": provider_meta.get("nav_price"),
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
        "Universe Source": meta.get("Source", "Yahoo search / manual add"),
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
        **{c: np.nan for c in ALL_RETURN_COLS},
        "Return Basis": "Adjusted market total return" if instrument_type == "ETF" else "Adjusted total return",
        "Inception Date": "—",
        "Exchange": "",
        "Data As Of": "—",
        "Universe Source": meta.get("Source", ""),
    }


def assemble_market(symbols: List[str], snapshot: pd.DataFrame) -> pd.DataFrame:
    snap = snapshot.set_index("Symbol", drop=False).to_dict(orient="index") if not snapshot.empty else {}
    rows = []
    for symbol in symbols:
        row = st.session_state.session_rows.get(symbol) or snap.get(symbol) or blank_row(symbol)
        rows.append(dict(row))
    df = pd.DataFrame(rows)
    for col in ["MarketCap", "Price", "NAV"] + ALL_RETURN_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def apply_live_overlay(df: pd.DataFrame, prices: Dict[str, float]) -> pd.DataFrame:
    if df.empty or not prices:
        return df
    out = df.copy()
    today = pd.Timestamp.now().date().isoformat()
    for idx, row in out.iterrows():
        symbol = row.get("Symbol")
        live = prices.get(symbol)
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
        # If today's official daily snapshot already contains the day return,
        # preserve it rather than replacing it with live-vs-same-close ~= 0%.
        if str(row.get("Data As Of", "")) != today:
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


st.markdown(
    """
    <div class="hero">
      <h1>MarketScope</h1>
      <p>Stocks & ETFs • multi-horizon total returns • sector intelligence • zero paid market-data API keys</p>
      <span class="source-pill">● Fast-start daily snapshot + Yahoo Finance market data</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.info(
    "Return methodology: 10Y Avg, 5Y Avg, 1Y, YTD, 6M, 3M, 1M and 1D use dividend/split-adjusted total-return history. "
    "Stocks do not have NAV. For ETFs, MarketScope does not mislabel market-price history as NAV history; current NAV is shown in Symbol Detail when Yahoo publishes it."
)

snapshot = load_snapshot()
base_symbols = default_universe["Symbol"].tolist()
extra_symbols = [s for s in st.session_state.extra_symbols if s not in set(base_symbols)]
symbols = base_symbols + extra_symbols
market = assemble_market(symbols, snapshot)
market = apply_live_overlay(market, st.session_state.live_prices)

with st.sidebar:
    st.subheader("Market controls")
    st.caption("The app opens from a precomputed CSV. The large stock universe is refreshed from the free Nasdaq stock screener source and market returns are refreshed through Yahoo/yfinance.")

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
        local = local_search(search_text)
        if local:
            st.session_state.search_results = local
        else:
            with st.spinner("Searching Yahoo Finance..."):
                st.session_state.search_results = provider.search(search_text, max_results=8)
    results = st.session_state.search_results
    if results:
        labels = [f"{r['symbol']} — {r['name']} ({r.get('quote_type','')})" for r in results]
        selected_label = st.selectbox("Matches", labels)
        selected = results[labels.index(selected_label)]
        symbol = selected["symbol"]
        if symbol in set(base_symbols):
            st.success(f"{symbol} is already in the market universe.")
        elif st.button("＋ Add outside-universe symbol", use_container_width=True):
            if symbol not in st.session_state.extra_symbols:
                st.session_state.extra_symbols.append(symbol)
                _save_extras_to_url()
            st.rerun()

    if st.session_state.extra_symbols:
        st.divider()
        remove_extras = st.multiselect("Remove manually added symbols", st.session_state.extra_symbols)
        if st.button("Remove selected extras", disabled=not remove_extras, use_container_width=True):
            st.session_state.extra_symbols = [s for s in st.session_state.extra_symbols if s not in remove_extras]
            _save_extras_to_url()
            st.rerun()

# Local filters happen before live-refresh scope selection.
filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([1.1, 1.1, 1.3, 2.0])
with filter_col1:
    sectors = sorted(x for x in market["Sector"].dropna().astype(str).unique().tolist() if x and x != "nan")
    selected_sectors = st.multiselect("Sector", sectors, placeholder="All sectors")
with filter_col2:
    instrument_filter = st.selectbox("Instrument", ["All", "Stocks", "ETFs"])
with filter_col3:
    cap_filter = st.selectbox("Stock market cap", ["> $100M universe", "> $1B", "> $10B", "> $100B"])
with filter_col4:
    table_search = st.text_input("Filter current universe", placeholder="Search symbol, name, sector or industry")

filtered = market.copy()
if selected_sectors:
    filtered = filtered[filtered["Sector"].isin(selected_sectors)]
if instrument_filter == "ETFs":
    filtered = filtered[filtered["Type"].eq("ETF")]
elif instrument_filter == "Stocks":
    filtered = filtered[filtered["Type"].eq("Stock")]

cap_thresholds = {"> $100M universe": 100_000_000, "> $1B": 1_000_000_000, "> $10B": 10_000_000_000, "> $100B": 100_000_000_000}
if cap_filter != "> $100M universe":
    threshold = cap_thresholds[cap_filter]
    # ETF allowlist is not market-cap-filtered; cap filter applies to stocks only.
    filtered = filtered[(filtered["Type"].eq("ETF")) | (pd.to_numeric(filtered["MarketCap"], errors="coerce") > threshold)]
if table_search:
    q = table_search.strip().lower()
    mask = (
        filtered["Symbol"].astype(str).str.lower().str.contains(q, regex=False)
        | filtered["Name"].astype(str).str.lower().str.contains(q, regex=False)
        | filtered["Sector"].astype(str).str.lower().str.contains(q, regex=False)
        | filtered["Industry"].astype(str).str.lower().str.contains(q, regex=False)
    )
    filtered = filtered[mask]

valid_prices = pd.to_numeric(market["Price"], errors="coerce").notna()
stock_count = int((default_universe["Type"] == "Stock").sum())
etf_count = int((default_universe["Type"] == "ETF").sum())
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Universe", f"{len(default_universe):,}")
k2.metric("Stocks > $100M", f"{stock_count:,}")
k3.metric("Requested ETFs", f"{etf_count:,}")
k4.metric("Snapshot populated", f"{int(valid_prices.sum()):,}")
k5.metric("Showing", f"{len(filtered):,}")

valid_dates = market.loc[market["Data As Of"].astype(str) != "—", "Data As Of"].astype(str).tolist() if "Data As Of" in market else []
if valid_dates:
    latest_snapshot = max(valid_dates)
    st.success(f"Daily snapshot loaded • market data through {latest_snapshot}. Sorting and filtering are local and immediate.")
else:
    st.warning("The large-universe snapshot has not been populated yet. Run the GitHub Action 'Refresh MarketScope universe and snapshot' once.")

missing_count = int((~valid_prices).sum())
if missing_count:
    st.warning(f"{missing_count:,} universe rows do not yet have a performance snapshot. This is expected until the first full GitHub Action refresh completes.")

refresh_col1, refresh_col2 = st.columns([1.4, 4.6])
with refresh_col1:
    refresh_live = st.button("⚡ Live refresh shown symbols", type="primary", use_container_width=True, disabled=len(filtered) == 0)
with refresh_col2:
    if len(filtered) > 500:
        st.caption(f"Live refresh would request {len(filtered):,} symbols in batched Yahoo calls and can take longer. Filter to a sector/symbol set for the fastest refresh.")
    else:
        st.caption(f"Live refresh scope: {len(filtered):,} currently shown symbol(s). Daily snapshot remains the fast startup source.")
if refresh_live:
    with st.spinner(f"Refreshing {len(filtered):,} latest Yahoo prices in batches..."):
        got = provider.download_live_prices(filtered["Symbol"].tolist())
        st.session_state.live_prices.update(got)
        st.session_state.live_refreshed_at = datetime.now()
    st.rerun()
if st.session_state.live_refreshed_at:
    st.caption(f"Last live refresh: {st.session_state.live_refreshed_at.strftime('%b %d, %Y %I:%M:%S %p')} local time")

# Add a compact market-cap view in billions for readability while retaining raw MarketCap internally.
table = filtered.copy()
table["Market Cap ($B)"] = pd.to_numeric(table["MarketCap"], errors="coerce") / 1_000_000_000

display_cols = [
    "Symbol", "Name", "Type", "Sector", "Industry", "Market Cap ($B)", "Price",
    "10Y Avg", "5Y Avg", "1Y", "YTD", "6M", "3M", "1M", "1D", "Return Basis",
]
for c in display_cols:
    if c not in table.columns:
        table[c] = pd.NA
styled = table[display_cols].style.map(style_return, subset=PERF_COLS)
st.dataframe(
    styled,
    use_container_width=True,
    height=650,
    hide_index=True,
    column_config={
        "Symbol": st.column_config.TextColumn("Symbol", pinned="left", width="small"),
        "Name": st.column_config.TextColumn("Name", pinned="left", width="medium"),
        "Type": st.column_config.TextColumn("Type", width="small"),
        "Sector": st.column_config.TextColumn("Sector", width="medium"),
        "Industry": st.column_config.TextColumn("Industry", width="medium"),
        "Market Cap ($B)": st.column_config.NumberColumn("Market Cap ($B)", format="$%.2f"),
        "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
        **{c: st.column_config.NumberColumn(c, format="%+.2f%%") for c in PERF_COLS},
        "Return Basis": st.column_config.TextColumn("Return Basis", width="medium"),
    },
)

st.markdown("### Symbol detail")
detail_options = filtered["Symbol"].tolist() if len(filtered) else market["Symbol"].tolist()
if detail_options:
    detail_symbol = st.selectbox("Inspect", detail_options)
    detail_row = market.loc[market["Symbol"] == detail_symbol].iloc[0]

    d1, d2, d3, d4, d5, d6 = st.columns(6)
    d1.metric("Price", f"${detail_row['Price']:,.2f}" if pd.notna(detail_row["Price"]) else "—")
    d2.metric("1D", format_pct(detail_row["1D"]))
    d3.metric("YTD", format_pct(detail_row["YTD"]))
    d4.metric("1Y", format_pct(detail_row["1Y"]))
    d5.metric("5Y avg", format_pct(detail_row["5Y Avg"]))
    nav = detail_row.get("NAV")
    d6.metric("Current NAV", f"${float(nav):,.2f}" if nav is not None and pd.notna(nav) else "—")

    if st.button(f"Load full {detail_symbol} metrics + current NAV", key=f"full_{detail_symbol}"):
        with st.spinner(f"Loading MAX adjusted history and metadata for {detail_symbol} only..."):
            row = cached_single_metrics(detail_symbol)
        if row:
            st.session_state.session_rows[detail_symbol] = row
            st.rerun()
        st.warning("Yahoo did not return full data for this symbol right now.")

    if detail_row.get("Type") == "ETF" and pd.notna(detail_row.get("NAV")) and pd.notna(detail_row.get("Price")):
        premium = (float(detail_row["Price"]) / float(detail_row["NAV"]) - 1.0) * 100.0 if float(detail_row["NAV"]) else np.nan
        st.caption(f"ETF market price vs current NAV: {premium:+.3f}% premium/discount. This is separate from historical market total return.")

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
            st.info("Yahoo did not return chart history for this symbol right now. The saved snapshot remains available.")

with st.expander("Data methodology and scale"):
    st.markdown(
        """
- **Universe:** U.S.-listed stock-screener rows with market capitalization strictly above **$100 million**, refreshed from Nasdaq's free stock screener data, plus the explicit ETF allowlist in `data/etf_allowlist.csv`.
- **Performance:** Yahoo/yfinance daily history with `auto_adjust=True`; returns therefore use adjusted history designed to account for splits and distributions.
- **10Y Avg / 5Y Avg:** annualized CAGR over the available near-full 10-year / 5-year horizon.
- **1Y / YTD / 6M / 3M / 1M / 1D:** point-to-point total return from adjusted history.
- **NAV:** a stock has no NAV. An ETF's current NAV is displayed separately when Yahoo provides `navPrice`. MarketScope does not call market-price history “NAV history.”
- **Startup speed:** the web app reads a committed snapshot CSV. Heavy history requests run in GitHub Actions, not while you wait for the page to open.
        """
    )

st.markdown("---")
st.markdown(
    "<div class='small-note'>MarketScope is an informational dashboard, not investment advice. Free website data can be delayed or rate-limited. Verify order-critical prices with your broker and fund NAV figures with the fund issuer.</div>",
    unsafe_allow_html=True,
)
