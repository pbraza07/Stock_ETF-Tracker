from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class PerformanceResult:
    current_price: Optional[float]
    inception_date: Optional[pd.Timestamp]
    since_inception: Optional[float]
    avg_10y: Optional[float]
    avg_5y: Optional[float]
    perf_1y: Optional[float]
    ytd: Optional[float]
    perf_6m: Optional[float]
    perf_3m: Optional[float]
    perf_1m: Optional[float]
    perf_1d: Optional[float]


def _normalize_close(history: pd.DataFrame) -> pd.Series:
    if history is None or history.empty or "Close" not in history.columns:
        return pd.Series(dtype="float64")
    close = pd.to_numeric(history["Close"], errors="coerce").dropna().copy()
    if close.empty:
        return close
    idx = pd.to_datetime(close.index)
    try:
        idx = idx.tz_localize(None)
    except TypeError:
        try:
            idx = idx.tz_convert(None)
        except TypeError:
            pass
    close.index = idx
    close = close[~close.index.duplicated(keep="last")].sort_index()
    return close


def _price_on_or_before(close: pd.Series, target: pd.Timestamp) -> Optional[float]:
    eligible = close.loc[close.index <= target]
    if eligible.empty:
        return None
    return float(eligible.iloc[-1])


def _price_near_target(close: pd.Series, target: pd.Timestamp, tolerance_days: int = 10) -> tuple[Optional[float], Optional[pd.Timestamp]]:
    """Return a trading price close to a calendar anchor without fabricating coverage.

    Prefer the last trading day on/before the anchor. If a bounded history download
    begins just after the anchor, accept the first trading day after it only when it
    is within the stated tolerance.
    """
    before = close.loc[close.index <= target]
    if not before.empty:
        ts = pd.Timestamp(before.index[-1])
        return float(before.iloc[-1]), ts
    after = close.loc[close.index > target]
    if not after.empty:
        ts = pd.Timestamp(after.index[0])
        if (ts - target).days <= tolerance_days:
            return float(after.iloc[0]), ts
    return None, None


def _total_return(current: float, base: Optional[float]) -> Optional[float]:
    if base is None or not np.isfinite(base) or base <= 0 or not np.isfinite(current):
        return None
    return (current / base) - 1.0


def _annualized_return(current: float, base: Optional[float], start: pd.Timestamp, end: pd.Timestamp) -> Optional[float]:
    if base is None or base <= 0 or current <= 0:
        return None
    years = (end - start).days / 365.2425
    if years <= 0:
        return None
    return (current / base) ** (1.0 / years) - 1.0


def calculate_performance(history: pd.DataFrame, live_price: Optional[float] = None, as_of: Optional[pd.Timestamp] = None) -> PerformanceResult:
    close = _normalize_close(history)
    if close.empty:
        return PerformanceResult(None, None, None, None, None, None, None, None, None, None, None)

    end = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.now().tz_localize(None)
    end = end.tz_localize(None) if getattr(end, "tzinfo", None) else end

    current = float(live_price) if live_price is not None and np.isfinite(live_price) and live_price > 0 else float(close.iloc[-1])
    inception_date = pd.Timestamp(close.index[0])
    inception_price = float(close.iloc[0])

    # Previous trading close logic depends on whether an intraday/live price is being overlaid.
    today = end.normalize()
    has_live = live_price is not None and np.isfinite(live_price) and live_price > 0
    if has_live:
        # If Yahoo's daily history already contains today's evolving bar, compare live to yesterday.
        # Otherwise compare live to the latest completed daily close.
        if close.index[-1].normalize() >= today and len(close) >= 2:
            prev_close = float(close.iloc[-2])
        else:
            prev_close = float(close.iloc[-1])
    else:
        # With daily-only data, latest close vs the preceding trading close is the latest 1D return.
        prev_close = float(close.iloc[-2]) if len(close) >= 2 else None

    def period_return(months: int = 0, years: int = 0) -> Optional[float]:
        target = end - pd.DateOffset(months=months, years=years)
        base, _ = _price_near_target(close, target)
        return _total_return(current, base)

    # Standard YTD comparison is against the final trading close before Jan 1.
    jan1 = pd.Timestamp(year=end.year, month=1, day=1)
    ytd_base = _price_on_or_before(close, jan1 - pd.Timedelta(days=1))
    if ytd_base is None:
        first_year = close.loc[close.index >= jan1]
        ytd_base = float(first_year.iloc[0]) if not first_year.empty else None

    ten_target = end - pd.DateOffset(years=10)
    five_target = end - pd.DateOffset(years=5)
    ten_base, ten_start = _price_near_target(close, ten_target)
    five_base, five_start = _price_near_target(close, five_target)

    # Require near-full horizon coverage before displaying CAGR.
    avg_10y = None
    if inception_date <= ten_target + pd.Timedelta(days=10) and ten_base is not None and ten_start is not None:
        avg_10y = _annualized_return(current, ten_base, ten_start, end)

    avg_5y = None
    if inception_date <= five_target + pd.Timedelta(days=10) and five_base is not None and five_start is not None:
        avg_5y = _annualized_return(current, five_base, five_start, end)

    return PerformanceResult(
        current_price=current,
        inception_date=inception_date,
        since_inception=_total_return(current, inception_price),
        avg_10y=avg_10y,
        avg_5y=avg_5y,
        perf_1y=period_return(years=1),
        ytd=_total_return(current, ytd_base),
        perf_6m=period_return(months=6),
        perf_3m=period_return(months=3),
        perf_1m=period_return(months=1),
        perf_1d=_total_return(current, prev_close),
    )


def as_percent(value: Optional[float]) -> Optional[float]:
    return None if value is None or not np.isfinite(value) else value * 100.0
