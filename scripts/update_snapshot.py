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

from analytics import as_percent, calculate_buy_signals, calculate_performance
from persistence import format_et, now_et
from providers import YahooFinanceProvider
from universe import load_default_universe

OUT = BASE_DIR / "data" / "market_snapshot.csv"
META_OUT = BASE_DIR / "data" / "snapshot_metadata.json"
HISTORY_PERIOD = os.getenv("MARKETSCOPE_HISTORY_PERIOD", "10y")
BATCH_SIZE = max(10, int(os.getenv("MARKETSCOPE_BATCH_SIZE", "80")))
PAUSE_SECONDS = float(os.getenv("MARKETSCOPE_BATCH_PAUSE", "0.35"))
PERF_COLS = ["1D", "1M", "3M", "6M", "YTD", "1Y Avg", "3Y Avg", "5Y Avg", "10Y Avg"]


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


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "buy"}


def main() -> None:
    if (
        os.getenv("RENDER", "").strip().lower() == "true"
        and os.getenv("MARKETSCOPE_FORCE_SNAPSHOT_ON_RENDER", "").strip().lower() != "true"
    ):
        print("Render detected: skipping full snapshot generation during deploy. GitHub Actions owns the daily refresh.")
        return

    refresh_started = now_et()
    refresh_display = format_et(refresh_started)
    universe = load_default_universe().copy()
    universe["Symbol"] = universe["Symbol"].astype(str).str.upper().str.strip()
    universe = universe.drop_duplicates("Symbol", keep="first")

    old_df = existing_frame()
    old = old_df.set_index("Symbol", drop=False).to_dict(orient="index") if not old_df.empty else {}

    # Keep only explicitly manual additions outside the automatic Nasdaq >$100B universe.
    universe_symbols = universe["Symbol"].tolist()
    universe_set = set(universe_symbols)
    extra_symbols: list[str] = []
    for symbol, prior in old.items():
        if symbol in universe_set:
            continue
        source = str(prior.get("Universe Source") or prior.get("Source") or "").lower()
        if "manual" in source:
            extra_symbols.append(symbol)

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
            rating = m.get("Analyst Rating") or prior.get("Analyst Rating") or "Not Rated"
            base_row = {
                "Symbol": symbol,
                "Name": m.get("Name") or prior.get("Name") or symbol,
                "Sector": m.get("Sector") or prior.get("Sector") or "Unknown",
                "Industry": m.get("Industry") or prior.get("Industry") or "Unknown",
                "Type": instrument_type,
                "MarketCap": m.get("MarketCap", prior.get("MarketCap", pd.NA)),
                "Analyst Rating": rating,
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
                        "NAV": pd.NA,
                        "Since Inception": pd.NA,
                        **{c: pd.NA for c in PERF_COLS},
                        "Short Buy": False,
                        "Long Buy": False,
                        "Fundamental Buy": False,
                        "Short Signal New": False,
                        "Long Signal New": False,
                        "Signal Reasons": "",
                        "Signal Updated ET": "",
                        "Short Signal Score": 0,
                        "Long Signal Score": 0,
                    })
                rows[symbol] = row
                continue

            perf = calculate_performance(hist)
            signals = calculate_buy_signals(hist, analyst_rating=rating, instrument_type=instrument_type)
            old_short = _as_bool(prior.get("Short Buy"))
            old_long = _as_bool(prior.get("Long Buy"))

            row = dict(base_row)
            row.update({
                "Price": perf.current_price,
                "NAV": prior.get("NAV", pd.NA),
                "Since Inception": prior.get("Since Inception", pd.NA),
                "1D": as_percent(perf.perf_1d),
                "1M": as_percent(perf.perf_1m),
                "3M": as_percent(perf.perf_3m),
                "6M": as_percent(perf.perf_6m),
                "YTD": as_percent(perf.ytd),
                "1Y Avg": as_percent(perf.avg_1y),
                "3Y Avg": as_percent(perf.avg_3y),
                "5Y Avg": as_percent(perf.avg_5y),
                "10Y Avg": as_percent(perf.avg_10y),
                "Short Buy": signals.short_buy,
                "Long Buy": signals.long_buy,
                "Fundamental Buy": signals.fundamental_buy,
                "Short Signal New": bool(signals.short_buy and not old_short),
                "Long Signal New": bool(signals.long_buy and not old_long),
                "Signal Reasons": signals.reasons,
                "Signal Updated ET": refresh_display,
                "Short Signal Score": signals.short_score,
                "Long Signal Score": signals.long_score,
            })
            rows[symbol] = row
        time.sleep(PAUSE_SECONDS)

    df = pd.DataFrame([rows[s] for s in symbols if s in rows])
    columns = [
        "Symbol", "Name", "Sector", "Industry", "Type", "MarketCap", "Price", "NAV",
        "Analyst Rating", "Rating Source", "Rating Updated ET",
        "1D", "1M", "3M", "6M", "YTD", "1Y Avg", "3Y Avg", "5Y Avg", "10Y Avg",
        "Since Inception", "Short Buy", "Long Buy", "Fundamental Buy",
        "Short Signal New", "Long Signal New", "Signal Reasons", "Signal Updated ET",
        "Short Signal Score", "Long Signal Score", "Return Basis", "Snapshot Updated ET", "Universe Source",
    ]
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[columns]

    tmp = OUT.with_suffix(".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(OUT)
    populated = int(pd.to_numeric(df["Price"], errors="coerce").notna().sum())
    new_alerts = int(
        df["Short Signal New"].fillna(False).astype(bool).sum()
        + df["Long Signal New"].fillna(False).astype(bool).sum()
    )
    META_OUT.write_text(
        json.dumps({
            "updated_at_et": refresh_started.isoformat(),
            "updated_at_display_et": refresh_display,
            "timezone": "America/New_York",
            "source": "Scheduled GitHub Action",
            "updated_instruments": populated,
            "snapshot_rows": int(len(df)),
            "new_buy_signal_events": new_alerts,
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Snapshot written: {OUT} ({populated:,}/{len(df):,} symbols populated) "
        f"with {new_alerts:,} new buy-signal event(s) at {refresh_display}"
    )


if __name__ == "__main__":
    main()
