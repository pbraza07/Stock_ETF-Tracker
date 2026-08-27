from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pandas as pd

from analytics import as_percent, calculate_performance
from persistence import format_et, now_et
from providers import YahooFinanceProvider
from universe import load_default_universe

OUT = BASE_DIR / "data" / "market_snapshot.csv"
META_OUT = BASE_DIR / "data" / "snapshot_metadata.json"
HISTORY_PERIOD = os.getenv("MARKETSCOPE_HISTORY_PERIOD", "10y")
BATCH_SIZE = max(10, int(os.getenv("MARKETSCOPE_BATCH_SIZE", "80")))
PAUSE_SECONDS = float(os.getenv("MARKETSCOPE_BATCH_PAUSE", "0.35"))
PERF_COLS = ["10Y Avg", "5Y Avg", "1Y", "YTD", "6M", "3M", "1M", "1D"]


def existing_frame() -> pd.DataFrame:
    if not OUT.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(OUT)
        if "Symbol" in df.columns:
            df["Symbol"] = df["Symbol"].astype(str).str.upper().str.strip()
            return df.drop_duplicates("Symbol", keep="last")
    except Exception:
        pass
    return pd.DataFrame()


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
    return "Adjusted market total return" if str(instrument_type).upper() == "ETF" else "Adjusted total return"


def _history_batch(provider: YahooFinanceProvider, batch: list[str]) -> dict:
    histories = provider.download_daily_history(batch, period=HISTORY_PERIOD)
    if len(histories) >= max(1, len(batch) // 3):
        return histories
    time.sleep(2)
    recovered = dict(histories)
    for i in range(0, len(batch), 20):
        recovered.update(provider.download_daily_history(batch[i:i + 20], period=HISTORY_PERIOD))
        time.sleep(0.25)
    return recovered


def main() -> None:
    if os.getenv("RENDER", "").strip().lower() == "true" and os.getenv("MARKETSCOPE_FORCE_SNAPSHOT_ON_RENDER", "").strip().lower() != "true":
        print("Render detected: skipping full snapshot generation during deploy. GitHub Actions owns the daily refresh.")
        return

    refresh_started = now_et()
    refresh_display = format_et(refresh_started)
    universe = load_default_universe().copy()
    universe["Symbol"] = universe["Symbol"].astype(str).str.upper().str.strip()
    universe = universe.drop_duplicates("Symbol", keep="first")

    old_df = existing_frame()
    old = old_df.set_index("Symbol", drop=False).to_dict(orient="index") if not old_df.empty else {}

    # Keep manually added instruments permanently. The Nasdaq $100M+ screen and
    # ETF allowlist define the automatic universe, while existing snapshot-only
    # symbols remain tracked across the scheduled daily rebuild.
    universe_symbols = universe["Symbol"].tolist()
    extra_symbols = [s for s in old.keys() if s not in set(universe_symbols)]
    symbols = universe_symbols + extra_symbols
    meta = universe.set_index("Symbol").to_dict(orient="index")
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
            prior = old.get(symbol, {})
            instrument_type = m.get("Type") or prior.get("Type") or "Unknown"
            base_row = {
                "Symbol": symbol,
                "Name": m.get("Name") or prior.get("Name") or symbol,
                "Sector": m.get("Sector") or prior.get("Sector") or "Unknown",
                "Industry": m.get("Industry") or prior.get("Industry") or "Unknown",
                "Type": instrument_type,
                "MarketCap": m.get("MarketCap", prior.get("MarketCap", pd.NA)),
                "Analyst Rating": m.get("Analyst Rating") or prior.get("Analyst Rating") or "Not Rated",
                "Rating Source": m.get("Rating Source") or prior.get("Rating Source") or "",
                "Rating Updated ET": m.get("Rating Updated ET") or prior.get("Rating Updated ET") or "—",
                "Universe Source": m.get("Source") or prior.get("Universe Source") or "Manual persistent symbol",
                "Return Basis": _basis(instrument_type),
                "Snapshot Updated ET": refresh_display,
            }
            hist = histories.get(symbol)
            if hist is None or hist.empty:
                row = dict(prior) if prior else {}
                row.update(base_row)
                if not prior:
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
            inception_date = prior.get("Inception Date", "—")
            if inception_date in (None, "", "nan"):
                inception_date = "—"
            row = dict(base_row)
            row.update({
                "Price": perf.current_price,
                "Since Inception": prior.get("Since Inception", pd.NA),
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

    df = pd.DataFrame([rows[s] for s in symbols if s in rows])
    columns = [
        "Symbol", "Name", "Sector", "Industry", "Type", "MarketCap", "Price", "NAV",
        "Analyst Rating", "Rating Source", "Rating Updated ET",
        "Since Inception", "10Y Avg", "5Y Avg", "1Y", "YTD", "6M", "3M", "1M", "1D",
        "Return Basis", "Inception Date", "Exchange", "Data As Of", "Snapshot Updated ET", "Universe Source",
    ]
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[columns]
    tmp = OUT.with_suffix(".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(OUT)
    populated = int(pd.to_numeric(df["Price"], errors="coerce").notna().sum())
    META_OUT.write_text(json.dumps({
        "updated_at_et": refresh_started.isoformat(),
        "updated_at_display_et": refresh_display,
        "timezone": "America/New_York",
        "source": "Scheduled GitHub Action",
        "updated_instruments": populated,
        "snapshot_rows": int(len(df)),
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Snapshot written: {OUT} ({populated:,}/{len(df):,} symbols populated) at {refresh_display}")


if __name__ == "__main__":
    main()
