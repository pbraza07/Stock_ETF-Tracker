from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parents[1]
OUT = BASE_DIR / "data" / "default_universe.csv"
ETF_FILE = BASE_DIR / "data" / "etf_allowlist.csv"

MIN_MARKET_CAP = 100_000_000.0
NASDAQ_URL = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&offset=0&download=true"
MIRRORS = [
    "https://raw.githubusercontent.com/zyhe16/top-us-stock-tickers/main/tickers/all.csv",
    "https://raw.githubusercontent.com/rogermaragh/top-us-stock-tickers/main/tickers/all.csv",
    "https://raw.githubusercontent.com/Ate329/top-us-stock-tickers/main/tickers/all.csv",
]
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
    s = str(value).strip().upper().replace("$", "").replace(",", "")
    if not s or s in {"N/A", "NA", "NONE", "--"}:
        return None
    mult = 1.0
    if s.endswith("T"):
        mult, s = 1e12, s[:-1]
    elif s.endswith("B"):
        mult, s = 1e9, s[:-1]
    elif s.endswith("M"):
        mult, s = 1e6, s[:-1]
    elif s.endswith("K"):
        mult, s = 1e3, s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def _yahoo_symbol(symbol: str) -> str:
    """Normalize common share-class notation to Yahoo's ticker convention."""
    s = str(symbol).strip().upper()
    s = s.replace("/", "-").replace(".", "-")
    return s


def _looks_like_non_stock(name: str) -> bool:
    """Drop obvious non-stock securities that can appear in a stock screener feed.

    The rule is intentionally conservative: ADRs, REITs, LPs and ordinary shares remain.
    """
    n = f" {str(name).lower()} "
    phrases = [
        " warrant", " warrants", " right ", " rights ", " units", " unit ",
        " notes due ", " note due ", " senior notes", " subordinated notes",
        " preferred stock", " preferred shares", " preferred securities",
    ]
    return any(p in n for p in phrases)


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
    out["Symbol"] = out["SourceSymbol"].map(_yahoo_symbol)
    out["Name"] = df[name_col].astype(str).str.strip()
    out["MarketCap"] = df[cap_col].map(_parse_market_cap)
    out["Sector"] = df[sector_col].astype(str).str.strip() if sector_col else "Unknown"
    out["Industry"] = df[industry_col].astype(str).str.strip() if industry_col else "Unknown"
    out["Type"] = "Stock"
    out["Source"] = source

    out = out[out["Symbol"].ne("") & out["MarketCap"].notna()]
    out = out[out["MarketCap"] > MIN_MARKET_CAP]
    out = out[~out["Name"].map(_looks_like_non_stock)]
    out = out.drop_duplicates("Symbol", keep="first")
    return out


def fetch_nasdaq() -> pd.DataFrame:
    r = requests.get(NASDAQ_URL, headers=HEADERS, timeout=60)
    r.raise_for_status()
    payload = r.json()
    data = payload.get("data") or {}
    rows = (data.get("table") or {}).get("rows") or data.get("rows") or []
    if not rows:
        raise RuntimeError("Nasdaq screener returned no rows")
    return _normalize_frame(pd.DataFrame(rows), "Nasdaq Stock Screener")


def fetch_mirror() -> pd.DataFrame:
    errors = []
    for url in MIRRORS:
        try:
            r = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=60)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            out = _normalize_frame(df, f"NASDAQ mirror: {url}")
            if not out.empty:
                return out
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("All NASDAQ mirror downloads failed: " + " | ".join(errors))


def load_etfs(existing: pd.DataFrame | None = None) -> pd.DataFrame:
    symbols = pd.read_csv(ETF_FILE)["Symbol"].astype(str).str.strip().str.upper().drop_duplicates().tolist()
    old = {}
    if existing is not None and not existing.empty and "Symbol" in existing.columns:
        old = existing.set_index("Symbol", drop=False).to_dict(orient="index")
    rows = []
    for symbol in symbols:
        meta = old.get(symbol, {})
        rows.append({
            "Symbol": symbol,
            "Name": meta.get("Name") or symbol,
            "Sector": meta.get("Sector") or "ETF / Fund",
            "Industry": meta.get("Industry") or "ETF / Fund",
            "Type": "ETF",
            "MarketCap": pd.NA,
            "Source": "User ETF allowlist",
            "SourceSymbol": symbol,
        })
    return pd.DataFrame(rows)


def main() -> None:
    existing = pd.DataFrame()
    if OUT.exists():
        try:
            existing = pd.read_csv(OUT)
        except Exception:
            pass

    try:
        stocks = fetch_nasdaq()
        print(f"Loaded {len(stocks):,} stocks above $100M from Nasdaq")
    except Exception as primary_exc:
        print(f"Nasdaq direct request failed: {primary_exc}")
        stocks = fetch_mirror()
        print(f"Loaded {len(stocks):,} stocks above $100M from Nasdaq-backed mirror")

    etfs = load_etfs(existing)
    # ETF allowlist wins any symbol collision.
    stocks = stocks[~stocks["Symbol"].isin(set(etfs["Symbol"]))]
    stocks = stocks.sort_values("MarketCap", ascending=False, na_position="last")
    etfs = etfs.sort_values("Symbol")
    out = pd.concat([stocks, etfs], ignore_index=True)

    columns = ["Symbol", "Name", "Sector", "Industry", "Type", "MarketCap", "Source", "SourceSymbol"]
    out = out[columns]
    tmp = OUT.with_suffix(".tmp")
    out.to_csv(tmp, index=False)
    tmp.replace(OUT)
    print(f"Universe written: {OUT} ({len(stocks):,} stocks + {len(etfs):,} requested ETFs = {len(out):,})")


if __name__ == "__main__":
    main()
