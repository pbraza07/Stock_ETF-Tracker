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
    calculate_monthly_returns,
    calculate_performance,
    completed_year_labels,
)
from persistence import format_et, now_et
from history_config import (
    ANNUAL_HISTORY_FIRST_YEAR,
    ANNUAL_HISTORY_START,
    annual_history_year_count,
    annual_history_year_labels,
    rolling_completed_year_labels,
)
from providers import YahooFinanceProvider
from universe import load_default_universe

OUT = BASE_DIR / "data" / "market_snapshot.csv"
META_OUT = BASE_DIR / "data" / "snapshot_metadata.json"
MONTHLY_OUT = BASE_DIR / "data" / "monthly_returns_10y.csv"
MONTHLY_FULL_OUT = BASE_DIR / "data" / "monthly_returns_full_history.csv"
# Legacy v5.9.57 compatibility input only.
MONTHLY_25Y_LEGACY_OUT = BASE_DIR / "data" / "monthly_returns_25y.csv"
BATCH_SIZE = max(10, int(os.getenv("MARKETSCOPE_BATCH_SIZE", "80")))
PAUSE_SECONDS = float(os.getenv("MARKETSCOPE_BATCH_PAUSE", "0.35"))
ANNUAL_HISTORY_YEARS = annual_history_year_count(as_of=now_et())
YEAR_RETURN_COLS = annual_history_year_labels(as_of=now_et())
MONTHLY_RANK_YEARS = rolling_completed_year_labels(10, as_of=now_et())
MONTHLY_START_YEAR = min(int(y) for y in MONTHLY_RANK_YEARS)
MONTHLY_END_YEAR = max(int(y) for y in MONTHLY_RANK_YEARS)
MONTHLY_RETURN_COLS = [
    f"{year}-{month:02d}"
    for year in range(MONTHLY_START_YEAR, MONTHLY_END_YEAR + 1)
    for month in range(1, 13)
]
MONTHLY_FULL_START_YEAR = min(int(y) for y in YEAR_RETURN_COLS)
MONTHLY_FULL_END_YEAR = max(int(y) for y in YEAR_RETURN_COLS)
MONTHLY_FULL_RETURN_COLS = [
    f"{year}-{month:02d}"
    for year in range(MONTHLY_FULL_START_YEAR, MONTHLY_FULL_END_YEAR + 1)
    for month in range(1, 13)
]
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


def existing_monthly_frame(path: Path = MONTHLY_OUT) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        if "Symbol" in df.columns:
            df["Symbol"] = df["Symbol"].astype(str).str.upper().str.strip()
            return df.drop_duplicates("Symbol", keep="last")
    except Exception:
        pass
    return pd.DataFrame()


def _basis(instrument_type: str) -> str:
    return "Adjusted market total return" if str(instrument_type).upper() == "ETF" else "Adjusted total return"


def _history_batch(provider: YahooFinanceProvider, batch: list[str]) -> dict:
    """Load the complete dynamic annual-history window automatically.

    An explicit 2000 start is required because the oldest displayed annual return
    (2001 during 2026) needs a genuine prior-year-end price anchor. The provider
    internally uses small Yahoo batches and single-symbol retries for omissions.
    """
    histories = provider.download_daily_history_since(
        batch, start=ANNUAL_HISTORY_START, chunk_size=20
    )
    if len(histories) >= len(batch):
        return histories
    time.sleep(1)
    recovered = dict(histories)
    missing = [symbol for symbol in batch if symbol not in recovered]
    for i in range(0, len(missing), 10):
        recovered.update(
            provider.download_daily_history_since(
                missing[i:i + 10], start=ANNUAL_HISTORY_START, chunk_size=5
            )
        )
        time.sleep(0.25)
    return recovered


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "buy"}


def _numeric_or_na(value):
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(parsed) if pd.notna(parsed) else pd.NA


def _annual_value_or_prior(annual_returns: dict, year: str, prior: dict):
    """Prefer a freshly calculated annual return, but never erase durable history.

    A temporary Yahoo omission must not turn an already verified 2001-2005 value
    back into a blank cell on the next daily refresh.
    """
    fresh = as_percent(annual_returns.get(year))
    parsed_fresh = pd.to_numeric(pd.Series([fresh]), errors="coerce").iloc[0]
    if pd.notna(parsed_fresh):
        return float(parsed_fresh)
    return _numeric_or_na(prior.get(year))


def _monthly_value_or_prior(monthly_returns: dict, label: str, prior: dict):
    fresh = as_percent(monthly_returns.get(label))
    parsed_fresh = pd.to_numeric(pd.Series([fresh]), errors="coerce").iloc[0]
    if pd.notna(parsed_fresh):
        return float(parsed_fresh)
    return _numeric_or_na(prior.get(label))


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
    old_monthly_df = existing_monthly_frame(MONTHLY_OUT)
    old_monthly = old_monthly_df.set_index("Symbol", drop=False).to_dict(orient="index") if not old_monthly_df.empty else {}
    old_monthly_full_df = existing_monthly_frame(MONTHLY_FULL_OUT)
    if old_monthly_full_df.empty:
        old_monthly_full_df = existing_monthly_frame(MONTHLY_25Y_LEGACY_OUT)
    old_monthly_full = (
        old_monthly_full_df.set_index("Symbol", drop=False).to_dict(orient="index")
        if not old_monthly_full_df.empty else {}
    )

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
    monthly_rows: dict[str, dict] = {}
    monthly_full_rows: dict[str, dict] = {}

    for start in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[start:start + BATCH_SIZE]
        batch_no = start // BATCH_SIZE + 1
        total_batches = (len(symbols) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"History batch {batch_no}/{total_batches}: {len(batch)} symbols from {ANNUAL_HISTORY_START}")
        histories = _history_batch(provider, batch)
        # Analyst price targets are fetched only for stock rows. They are stored
        # in the durable daily snapshot so loading the dashboard does not trigger
        # hundreds of Yahoo metadata requests. Existing targets are preserved if
        # Yahoo temporarily throttles or omits coverage.
        stock_batch = [
            symbol for symbol in batch
            if str((meta.get(symbol, {}) or old.get(symbol, {})).get("Type") or "").strip().lower() == "stock"
        ]
        stock_targets = provider.get_price_targets_many(stock_batch, max_workers=3) if stock_batch else {}

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
                "History Verification": prior.get("History Verification", ""),
                "Verification Coverage": prior.get("Verification Coverage", ""),
                "Verified Years": prior.get("Verified Years", pd.NA),
                "Verification Available Years": prior.get("Verification Available Years", pd.NA),
                "Verification Compared Years": prior.get("Verification Compared Years", pd.NA),
                "Verification Discrepancies": prior.get("Verification Discrepancies", pd.NA),
                "Max Verification Diff (pp)": prior.get("Max Verification Diff (pp)", pd.NA),
                "Verification Tolerance (pp)": prior.get("Verification Tolerance (pp)", pd.NA),
                "Verification Exceptions": prior.get("Verification Exceptions", ""),
                "Verification Source": prior.get("Verification Source", ""),
                "Verification Updated ET": prior.get("Verification Updated ET", ""),
            }

            hist = histories.get(symbol)
            if hist is None or hist.empty:
                if symbol in old_monthly:
                    monthly_rows[symbol] = dict(old_monthly[symbol])
                if symbol in old_monthly_full:
                    monthly_full_rows[symbol] = dict(old_monthly_full[symbol])
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
            annual_returns = calculate_calendar_year_returns(hist, years=ANNUAL_HISTORY_YEARS)
            monthly_returns = calculate_monthly_returns(hist, MONTHLY_START_YEAR, MONTHLY_END_YEAR)
            monthly_returns_full = calculate_monthly_returns(
                hist, MONTHLY_FULL_START_YEAR, MONTHLY_FULL_END_YEAR
            )
            monthly_rows[symbol] = {
                "Symbol": symbol,
                "Name": base_row.get("Name") or symbol,
                "Sector": base_row.get("Sector") or "Unknown",
                "Type": base_row.get("Type") or "Unknown",
                **{label: _monthly_value_or_prior(monthly_returns, label, old_monthly.get(symbol, {})) for label in MONTHLY_RETURN_COLS},
                "Monthly Return Method": "Actual adjusted month-end return from Yahoo/yfinance daily history",
                "Annual Reconciliation Source": "Market Table annual returns from the same adjusted daily history",
                "Snapshot Updated ET": refresh_display,
            }
            monthly_full_rows[symbol] = {
                "Symbol": symbol,
                "Name": base_row.get("Name") or symbol,
                "Sector": base_row.get("Sector") or "Unknown",
                "Type": base_row.get("Type") or "Unknown",
                **{
                    label: _monthly_value_or_prior(
                        monthly_returns_full, label, old_monthly_full.get(symbol, {})
                    )
                    for label in MONTHLY_FULL_RETURN_COLS
                },
                "Monthly Return Method": "Actual adjusted month-end return from Yahoo/yfinance daily history",
                "Annual Reconciliation Source": "Market Table annual returns from the same adjusted daily history",
                "Snapshot Updated ET": refresh_display,
            }
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
                **{year: _annual_value_or_prior(annual_returns, year, prior) for year in YEAR_RETURN_COLS},
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
        "History Verification", "Verification Coverage", "Verified Years",
        "Verification Available Years", "Verification Compared Years", "Verification Discrepancies",
        "Max Verification Diff (pp)", "Verification Tolerance (pp)",
        "Verification Exceptions", "Verification Source", "Verification Updated ET",
    ]
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[columns]

    tmp = OUT.with_suffix(".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(OUT)
    monthly_df = pd.DataFrame([monthly_rows[s] for s in symbols if s in monthly_rows])
    monthly_columns = [
        "Symbol", "Name", "Sector", "Type", *MONTHLY_RETURN_COLS,
        "Monthly Return Method", "Annual Reconciliation Source", "Snapshot Updated ET",
    ]
    for col in monthly_columns:
        if col not in monthly_df.columns:
            monthly_df[col] = pd.NA
    monthly_df = monthly_df[monthly_columns]
    monthly_tmp = MONTHLY_OUT.with_suffix(".tmp")
    monthly_df.to_csv(monthly_tmp, index=False)
    monthly_tmp.replace(MONTHLY_OUT)

    monthly_full_df = pd.DataFrame([
        monthly_full_rows[s] for s in symbols if s in monthly_full_rows
    ])
    monthly_full_columns = [
        "Symbol", "Name", "Sector", "Type", *MONTHLY_FULL_RETURN_COLS,
        "Monthly Return Method", "Annual Reconciliation Source", "Snapshot Updated ET",
    ]
    for col in monthly_full_columns:
        if col not in monthly_full_df.columns:
            monthly_full_df[col] = pd.NA
    monthly_full_df = monthly_full_df[monthly_full_columns]
    monthly_full_tmp = MONTHLY_FULL_OUT.with_suffix(".tmp")
    monthly_full_df.to_csv(monthly_full_tmp, index=False)
    monthly_full_tmp.replace(MONTHLY_FULL_OUT)

    populated = int(pd.to_numeric(df["Price"], errors="coerce").notna().sum())
    new_alerts = int(
        df["Short Signal New"].fillna(False).astype(bool).sum()
        + df["Long Signal New"].fillna(False).astype(bool).sum()
    )
    annual_coverage_by_year = {
        year: int(pd.to_numeric(df[year], errors="coerce").notna().sum())
        for year in YEAR_RETURN_COLS
    }
    oldest_annual_year = next(
        (year for year in reversed(YEAR_RETURN_COLS) if annual_coverage_by_year.get(year, 0) > 0),
        None,
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
            "annual_history_year_count": len(YEAR_RETURN_COLS),
            "annual_history_first_year": ANNUAL_HISTORY_FIRST_YEAR,
            "annual_history_latest_completed_year": int(YEAR_RETURN_COLS[0]) if YEAR_RETURN_COLS else None,
            "annual_history_start_requested": ANNUAL_HISTORY_START,
            "annual_history_refresh_mode": "automatic explicit-start adjusted daily history",
            "oldest_annual_year_with_data": oldest_annual_year,
            "annual_coverage_by_year": annual_coverage_by_year,
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Snapshot written: {OUT} ({populated:,}/{len(df):,} symbols populated) "
        f"with {new_alerts:,} new buy-signal event(s) at {refresh_display}; "
        f"actual 10Y monthly returns written for {len(monthly_df):,} symbols to {MONTHLY_OUT.name}; "
        f"actual full-history monthly returns written for {len(monthly_full_df):,} symbols to {MONTHLY_FULL_OUT.name}"
    )


if __name__ == "__main__":
    main()
