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

from analytics import (
    as_percent,
    calculate_buy_signals,
    calculate_calendar_year_returns,
    calculate_performance,
    completed_year_labels,
)
from persistence import format_et, now_et
from providers import YahooFinanceProvider
from universe import load_default_universe

OUT = BASE_DIR / "data" / "market_snapshot.csv"
META_OUT = BASE_DIR / "data" / "snapshot_metadata.json"
HISTORY_PERIOD = os.getenv("MARKETSCOPE_HISTORY_PERIOD", "max")
BATCH_SIZE = max(10, int(os.getenv("MARKETSCOPE_BATCH_SIZE", "80")))
PAUSE_SECONDS = float(os.getenv("MARKETSCOPE_BATCH_PAUSE", "0.35"))
YEAR_RETURN_COLS = completed_year_labels(as_of=now_et(), years=20)
PERF_COLS = ["1D", "1M", "3M", "6M", "YTD", *YEAR_RETURN_COLS]


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
        # Analyst price targets are fetched only for stock rows. They are stored
        # in the durable daily snapshot so loading the dashboard does not trigger
        # hundreds of Yahoo metadata requests. Existing targets are preserved if
        # Yahoo temporarily throttles or omits coverage.
        stock_batch = [
            symbol for symbol in batch
            if str((meta.get(symbol, {}) or old.get(symbol, {})).get("Type") or "").strip().lower() == "stock"
        ]
        stock_targets = provider.get_price_targets_many(stock_batch, max_workers=6) if stock_batch else {}

        for symbol in batch:
            m = meta.get(symbol, {})
            prior = old.get(symbol, {})
            instrument_type = m.get("Type") or prior.get("Type") or "Unknown"
            rating = m.get("Analyst Rating") or prior.get("Analyst Rating") or "Not Rated"
            target_values = stock_targets.get(symbol, {}) if str(instrument_type).strip().lower() == "stock" else {}
            target_high = target_values.get("high")
            target_mean = target_values.get("mean")
            target_low = target_values.get("low")
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
                "Price Target High": target_high if target_high is not None else prior.get("Price Target High", pd.NA),
                "Price Target Average": target_mean if target_mean is not None else prior.get("Price Target Average", pd.NA),
                "Price Target Low": target_low if target_low is not None else prior.get("Price Target Low", pd.NA),
                "Price Target Updated ET": refresh_display if any(v is not None for v in (target_high, target_mean, target_low)) else prior.get("Price Target Updated ET", "—"),
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
                        "Price Target High": pd.NA,
                        "Price Target Average": pd.NA,
                        "Price Target Low": pd.NA,
                        "Price Target Updated ET": "—",
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
            annual_returns = calculate_calendar_year_returns(hist, years=20)
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
                **{year: as_percent(annual_returns.get(year)) for year in YEAR_RETURN_COLS},
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
        "Price Target High", "Price Target Average", "Price Target Low", "Price Target Updated ET",
        "1D", "1M", "3M", "6M", "YTD", *YEAR_RETURN_COLS,
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
