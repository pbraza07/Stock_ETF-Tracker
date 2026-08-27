from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd

from analytics import as_percent, calculate_performance
from providers import YahooFinanceProvider
from universe import load_default_universe

BASE_DIR = Path(__file__).resolve().parents[1]
OUT = BASE_DIR / "data" / "market_snapshot.csv"
HISTORY_PERIOD = os.getenv("MARKETSCOPE_HISTORY_PERIOD", "10y")
BATCH_SIZE = max(10, int(os.getenv("MARKETSCOPE_BATCH_SIZE", "80")))
PAUSE_SECONDS = float(os.getenv("MARKETSCOPE_BATCH_PAUSE", "0.35"))

PERF_COLS = ["10Y Avg", "5Y Avg", "1Y", "YTD", "6M", "3M", "1M", "1D"]


def existing_rows() -> dict:
    if not OUT.exists():
        return {}
    try:
        df = pd.read_csv(OUT)
        if "Symbol" in df.columns:
            df["Symbol"] = df["Symbol"].astype(str).str.upper().str.strip()
            return df.set_index("Symbol", drop=False).to_dict(orient="index")
    except Exception:
        pass
    return {}


def _date_only(value) -> str:
    ts = pd.to_datetime(value)
    try:
        ts = ts.tz_localize(None)
    except TypeError:
        try:
            ts = ts.tz_convert(None)
        except TypeError:
            pass
    return ts.date().isoformat()


def _basis(instrument_type: str) -> str:
    if str(instrument_type).upper() == "ETF":
        return "Adjusted market total return"
    return "Adjusted total return"


def _history_batch(provider: YahooFinanceProvider, batch: list[str]) -> dict:
    histories = provider.download_daily_history(batch, period=HISTORY_PERIOD)
    # If a large Yahoo batch fails, retry once in smaller groups. This is slower
    # but much more resilient on GitHub-hosted IP addresses.
    if len(histories) >= max(1, len(batch) // 3):
        return histories
    time.sleep(2)
    recovered = dict(histories)
    small = 20
    for i in range(0, len(batch), small):
        sub = batch[i:i + small]
        got = provider.download_daily_history(sub, period=HISTORY_PERIOD)
        recovered.update(got)
        time.sleep(0.25)
    return recovered


def main() -> None:
    universe = load_default_universe().copy()
    universe["Symbol"] = universe["Symbol"].astype(str).str.upper().str.strip()
    universe = universe.drop_duplicates("Symbol", keep="first")
    symbols = universe["Symbol"].tolist()
    meta = universe.set_index("Symbol").to_dict(orient="index")
    old = existing_rows()
    provider = YahooFinanceProvider()
    rows: dict[str, dict] = {}

    for start in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[start:start + BATCH_SIZE]
        batch_no = start // BATCH_SIZE + 1
        total_batches = (len(symbols) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"History batch {batch_no}/{total_batches}: {len(batch)} symbols")
        histories = _history_batch(provider, batch)

        for symbol in batch:
            m = meta.get(symbol, {})
            instrument_type = m.get("Type", "Unknown")
            base_row = {
                "Symbol": symbol,
                "Name": m.get("Name", symbol),
                "Sector": m.get("Sector", "Unknown"),
                "Industry": m.get("Industry", "Unknown"),
                "Type": instrument_type,
                "MarketCap": m.get("MarketCap", pd.NA),
                "Universe Source": m.get("Source", ""),
                "Return Basis": _basis(instrument_type),
            }

            hist = histories.get(symbol)
            if hist is None or hist.empty:
                prior = old.get(symbol, {})
                if prior:
                    row = dict(prior)
                    row.update(base_row)
                    rows[symbol] = row
                else:
                    row = dict(base_row)
                    row.update({
                        "Price": pd.NA,
                        "Since Inception": pd.NA,
                        **{c: pd.NA for c in PERF_COLS},
                        "Inception Date": "—",
                        "NAV": pd.NA,
                        "Exchange": "",
                        "Data As Of": "—",
                    })
                    rows[symbol] = row
                continue

            perf = calculate_performance(hist)
            prior = old.get(symbol, {})
            # The scalable universe refresh intentionally downloads 10 years, not
            # MAX history. Never mislabel the start of a bounded 10Y window as the
            # security's actual inception. Preserve a previously verified value only.
            since_inception = prior.get("Since Inception", pd.NA)
            inception_date = prior.get("Inception Date", "—")
            if inception_date in (None, "", "nan"):
                inception_date = "—"

            row = dict(base_row)
            row.update({
                "Price": perf.current_price,
                "Since Inception": since_inception,
                "10Y Avg": as_percent(perf.avg_10y),
                "5Y Avg": as_percent(perf.avg_5y),
                "1Y": as_percent(perf.perf_1y),
                "YTD": as_percent(perf.ytd),
                "6M": as_percent(perf.perf_6m),
                "3M": as_percent(perf.perf_3m),
                "1M": as_percent(perf.perf_1m),
                "1D": as_percent(perf.perf_1d),
                "Inception Date": inception_date,
                "NAV": prior.get("NAV", pd.NA),
                "Exchange": prior.get("Exchange", ""),
                "Data As Of": _date_only(hist.index[-1]),
            })
            rows[symbol] = row
        time.sleep(PAUSE_SECONDS)

    ordered = [rows[s] for s in symbols if s in rows]
    df = pd.DataFrame(ordered)
    columns = [
        "Symbol", "Name", "Sector", "Industry", "Type", "MarketCap", "Price", "NAV",
        "Since Inception", "10Y Avg", "5Y Avg", "1Y", "YTD", "6M", "3M", "1M", "1D",
        "Return Basis", "Inception Date", "Exchange", "Data As Of", "Universe Source",
    ]
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[columns]
    tmp = OUT.with_suffix(".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(OUT)
    populated = int(pd.to_numeric(df["Price"], errors="coerce").notna().sum())
    print(f"Snapshot written: {OUT} ({populated:,}/{len(df):,} symbols populated)")


if __name__ == "__main__":
    main()
