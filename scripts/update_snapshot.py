from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from analytics import as_percent, calculate_performance
from providers import YahooFinanceProvider
from universe import load_default_universe

BASE_DIR = Path(__file__).resolve().parents[1]
OUT = BASE_DIR / "data" / "market_snapshot.csv"


def existing_rows() -> dict:
    if not OUT.exists():
        return {}
    try:
        df = pd.read_csv(OUT)
        if "Symbol" in df.columns:
            return df.set_index("Symbol", drop=False).to_dict(orient="index")
    except Exception:
        pass
    return {}


def main() -> None:
    universe = load_default_universe()
    symbols = universe["Symbol"].astype(str).str.upper().tolist()
    meta = universe.set_index("Symbol").to_dict(orient="index")
    old = existing_rows()
    provider = YahooFinanceProvider()
    rows = {}

    batch_size = 12
    for start in range(0, len(symbols), batch_size):
        batch = symbols[start:start + batch_size]
        histories = provider.download_daily_history(batch, period="max")
        if not histories:
            time.sleep(5)
            histories = provider.download_daily_history(batch, period="max")

        for symbol in batch:
            hist = histories.get(symbol)
            if hist is None or hist.empty:
                if symbol in old:
                    rows[symbol] = old[symbol]
                else:
                    m = meta.get(symbol, {})
                    rows[symbol] = {
                        "Symbol": symbol,
                        "Name": m.get("Name", symbol),
                        "Sector": m.get("Sector", "Unknown"),
                        "Industry": m.get("Industry", "Unknown"),
                        "Type": m.get("Type", "Unknown"),
                    }
                continue

            perf = calculate_performance(hist)
            m = meta.get(symbol, {})
            last_date = pd.to_datetime(hist.index[-1])
            try:
                last_date = last_date.tz_localize(None)
            except TypeError:
                try:
                    last_date = last_date.tz_convert(None)
                except TypeError:
                    pass
            rows[symbol] = {
                "Symbol": symbol,
                "Name": m.get("Name", symbol),
                "Sector": m.get("Sector", "Unknown"),
                "Industry": m.get("Industry", "Unknown"),
                "Type": m.get("Type", "Unknown"),
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
                "Exchange": "",
                "Data As Of": last_date.date().isoformat(),
            }
        time.sleep(1)

    ordered = [rows[s] for s in symbols if s in rows]
    df = pd.DataFrame(ordered)
    columns = [
        "Symbol", "Name", "Sector", "Industry", "Type", "Price", "Since Inception",
        "10Y Avg", "5Y Avg", "1Y", "YTD", "6M", "3M", "1M", "1D",
        "Inception Date", "Exchange", "Data As Of"
    ]
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[columns]
    tmp = OUT.with_suffix(".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(OUT)
    populated = int(pd.to_numeric(df["Price"], errors="coerce").notna().sum())
    print(f"Snapshot written: {OUT} ({populated}/{len(df)} symbols populated)")


if __name__ == "__main__":
    main()
