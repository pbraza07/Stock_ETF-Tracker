from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import requests

from persistence import format_et, now_et
from providers.nasdaq import NasdaqScreenerProvider

OUT = BASE_DIR / "data" / "default_universe.csv"
ETF_FILE = BASE_DIR / "data" / "etf_allowlist.csv"
UNIVERSE_STATE = BASE_DIR / "data" / "universe_refresh_state.json"
MIN_MARKET_CAP = 100_000_000_000.0
NASDAQ_URL = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&offset=0&download=true"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/market-activity/stocks/screener",
}


def _parse_market_cap(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().upper().replace("$", "").replace(",", "")
    if not text or text in {"N/A", "NA", "NONE", "--"}:
        return None
    mult = 1.0
    if text.endswith("T"):
        mult, text = 1e12, text[:-1]
    elif text.endswith("B"):
        mult, text = 1e9, text[:-1]
    elif text.endswith("M"):
        mult, text = 1e6, text[:-1]
    elif text.endswith("K"):
        mult, text = 1e3, text[:-1]
    try:
        return float(text) * mult
    except ValueError:
        return None


def _symbol(symbol: str) -> str:
    return str(symbol).strip().upper().replace("/", "-").replace(".", "-")


def _looks_like_non_stock(name: str) -> bool:
    text = f" {str(name).lower()} "
    phrases = [
        " warrant", " warrants", " right ", " rights ", " units", " unit ",
        " notes due ", " note due ", " senior notes", " subordinated notes",
        " preferred stock", " preferred shares", " preferred securities",
    ]
    return any(p in text for p in phrases)


def _normalize_frame(df: pd.DataFrame, source: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    cols = {str(c).strip().lower(): c for c in df.columns}
    sym_col = cols.get("symbol")
    name_col = cols.get("name") or cols.get("security name")
    cap_col = cols.get("marketcap") or cols.get("market cap")
    sector_col = cols.get("sector") or cols.get("industry")
    industry_col = cols.get("industry")
    if not sym_col or not name_col or not cap_col:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["SourceSymbol"] = df[sym_col].astype(str).str.strip().str.upper()
    out["Symbol"] = out["SourceSymbol"].map(_symbol)
    out["Name"] = df[name_col].astype(str).str.strip()
    out["MarketCap"] = df[cap_col].map(_parse_market_cap)
    out["Sector"] = df[sector_col].astype(str).str.strip() if sector_col else "Unknown"
    out["Industry"] = df[industry_col].astype(str).str.strip() if industry_col else "Unknown"
    out["Type"] = "Stock"
    out["Source"] = source
    out = out[out["Symbol"].ne("") & out["MarketCap"].notna()]
    out = out[out["MarketCap"] > MIN_MARKET_CAP]
    out = out[~out["Name"].map(_looks_like_non_stock)]
    return out.drop_duplicates("Symbol", keep="first")


def fetch_nasdaq() -> pd.DataFrame:
    response = requests.get(NASDAQ_URL, headers=HEADERS, timeout=60)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") or {}
    rows = (data.get("table") or {}).get("rows") or data.get("rows") or []
    if not rows:
        raise RuntimeError("Nasdaq screener returned no rows")
    return _normalize_frame(pd.DataFrame(rows), "Nasdaq Stock Screener")


def _map(df: pd.DataFrame) -> dict:
    if df is None or df.empty or "Symbol" not in df.columns:
        return {}
    copy = df.copy()
    copy["Symbol"] = copy["Symbol"].astype(str).str.upper().str.strip()
    return copy.set_index("Symbol", drop=False).to_dict(orient="index")


def add_analyst_ratings(stocks: pd.DataFrame, existing: pd.DataFrame) -> pd.DataFrame:
    old = _map(existing)
    stamp = format_et(now_et())
    rating_refresh_succeeded = False
    try:
        rating_map = NasdaqScreenerProvider(timeout=60).get_stock_rating_map(stocks["Symbol"].tolist())
        rating_refresh_succeeded = True
        print(f"Loaded Nasdaq analyst consensus for {len(rating_map):,} stock symbols")
    except Exception as exc:
        print(f"Nasdaq analyst-rating refresh failed; prior ratings will be preserved where possible: {exc}")
        rating_map = {}

    ratings, sources, updated = [], [], []
    for symbol in stocks["Symbol"]:
        prior = old.get(symbol, {})
        if symbol in rating_map:
            ratings.append(rating_map[symbol])
            sources.append("Nasdaq Stock Screener analyst consensus")
            updated.append(stamp)
        elif rating_refresh_succeeded:
            ratings.append("Not Rated")
            sources.append("Nasdaq Stock Screener — no consensus rating returned")
            updated.append(stamp)
        else:
            prior_rating = str(prior.get("Analyst Rating") or "").strip()
            if prior_rating and prior_rating.lower() not in {"nan", "none"}:
                ratings.append(prior_rating)
                sources.append(prior.get("Rating Source") or "Nasdaq Stock Screener analyst consensus")
                updated.append(prior.get("Rating Updated ET") or "—")
            else:
                ratings.append("Not Rated")
                sources.append("Nasdaq Stock Screener — no consensus rating returned")
                updated.append("—")
    stocks = stocks.copy()
    stocks["Analyst Rating"] = ratings
    stocks["Rating Source"] = sources
    stocks["Rating Updated ET"] = updated
    return stocks


def load_etfs(existing: pd.DataFrame) -> pd.DataFrame:
    symbols = pd.read_csv(ETF_FILE)["Symbol"].astype(str).str.strip().str.upper().drop_duplicates().tolist()
    old = _map(existing)
    provider = NasdaqScreenerProvider(timeout=60)
    try:
        genuine_etf_ratings = provider.get_etf_rating_map(symbols)
    except Exception:
        genuine_etf_ratings = {}
    stamp = format_et(now_et())

    rows = []
    for symbol in symbols:
        meta = old.get(symbol, {})
        if symbol in genuine_etf_ratings:
            rating = genuine_etf_ratings[symbol]
            source = "Nasdaq ETF Screener analyst field"
            rating_updated = stamp
        else:
            prior_rating = str(meta.get("Analyst Rating") or "").strip()
            prior_source = str(meta.get("Rating Source") or "")
            if prior_rating and prior_rating.lower() not in {"nan", "none", "not rated"} and "Nasdaq ETF Screener analyst field" in prior_source:
                rating = prior_rating
                source = prior_source
                rating_updated = meta.get("Rating Updated ET") or "—"
            else:
                rating = "Not Rated"
                source = "Nasdaq ETF Screener — no stock-style analyst consensus"
                rating_updated = "—"
        rows.append({
            "Symbol": symbol,
            "Name": meta.get("Name") or symbol,
            "Sector": meta.get("Sector") or "ETF / Fund",
            "Industry": meta.get("Industry") or "ETF / Fund",
            "Type": "ETF",
            "MarketCap": pd.NA,
            "Analyst Rating": rating,
            "Rating Source": source,
            "Rating Updated ET": rating_updated,
            "Source": "User ETF allowlist",
            "SourceSymbol": symbol,
        })
    return pd.DataFrame(rows)


def main() -> None:
    try:
        existing = pd.read_csv(OUT) if OUT.exists() else pd.DataFrame()
    except Exception:
        existing = pd.DataFrame()

    stocks = fetch_nasdaq()
    print(f"Loaded {len(stocks):,} stocks above $100B directly from Nasdaq Stock Screener")

    prior_stock_symbols = set()
    if not existing.empty and "Symbol" in existing.columns:
        if "Type" in existing.columns:
            prior_mask = existing["Type"].astype(str).str.upper().eq("STOCK")
            prior_stock_symbols = set(existing.loc[prior_mask, "Symbol"].astype(str).str.upper().str.strip())
        else:
            prior_stock_symbols = set(existing["Symbol"].astype(str).str.upper().str.strip())
    current_stock_symbols = set(stocks["Symbol"].astype(str).str.upper().str.strip())
    added_symbols = sorted(current_stock_symbols - prior_stock_symbols)
    removed_symbols = sorted(prior_stock_symbols - current_stock_symbols)
    universe_refresh = now_et()

    stocks = add_analyst_ratings(stocks, existing)
    etfs = load_etfs(existing)
    stocks = stocks[~stocks["Symbol"].isin(set(etfs["Symbol"]))].sort_values("MarketCap", ascending=False, na_position="last")
    etfs = etfs.sort_values("Symbol")
    out = pd.concat([stocks, etfs], ignore_index=True)
    cols = [
        "Symbol", "Name", "Sector", "Industry", "Type", "MarketCap",
        "Analyst Rating", "Rating Source", "Rating Updated ET", "Source", "SourceSymbol",
    ]
    for col in cols:
        if col not in out.columns:
            out[col] = pd.NA
    tmp = OUT.with_suffix(".tmp")
    out[cols].to_csv(tmp, index=False)
    tmp.replace(OUT)
    UNIVERSE_STATE.write_text(
        json.dumps({
            "nasdaq_universe_refreshed_at_et": universe_refresh.isoformat(),
            "nasdaq_universe_refreshed_at_display_et": format_et(universe_refresh),
            "nasdaq_stock_count": int(len(stocks)),
            "nasdaq_stocks_added_count": int(len(added_symbols)),
            "nasdaq_stocks_removed_count": int(len(removed_symbols)),
            "nasdaq_stocks_added": added_symbols,
            "nasdaq_stocks_removed": removed_symbols,
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Universe written: {OUT} ({len(stocks):,} stocks + {len(etfs):,} CSV ETFs = {len(out):,}); "
        f"added {len(added_symbols):,}, removed {len(removed_symbols):,}"
    )


if __name__ == "__main__":
    main()
