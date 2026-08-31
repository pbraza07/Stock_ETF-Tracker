from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class PerformanceResult:
    current_price: Optional[float]
    inception_date: Optional[pd.Timestamp]
    since_inception: Optional[float]
    avg_10y: Optional[float]
    avg_9y: Optional[float]
    avg_8y: Optional[float]
    avg_7y: Optional[float]
    avg_6y: Optional[float]
    avg_5y: Optional[float]
    avg_4y: Optional[float]
    avg_3y: Optional[float]
    avg_2y: Optional[float]
    avg_1y: Optional[float]
    # Kept for backward compatibility with prior MarketScope tests/code.
    perf_1y: Optional[float]
    ytd: Optional[float]
    perf_6m: Optional[float]
    perf_3m: Optional[float]
    perf_1m: Optional[float]
    perf_1d: Optional[float]


@dataclass
class SignalResult:
    short_buy: bool
    long_buy: bool
    fundamental_buy: bool
    short_score: int
    long_score: int
    rsi14: Optional[float]
    sma20: Optional[float]
    sma50: Optional[float]
    sma200: Optional[float]
    macd: Optional[float]
    macd_signal: Optional[float]
    reasons: str


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


def _price_near_target(
    close: pd.Series, target: pd.Timestamp, tolerance_days: int = 10
) -> tuple[Optional[float], Optional[pd.Timestamp]]:
    """Return a trading price close to a calendar anchor without fabricating coverage."""
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


def _annualized_return(
    current: float,
    base: Optional[float],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> Optional[float]:
    if base is None or base <= 0 or current <= 0:
        return None
    years = (end - start).days / 365.2425
    if years <= 0:
        return None
    return (current / base) ** (1.0 / years) - 1.0


def completed_year_labels(as_of: Optional[pd.Timestamp] = None, years: int = 10) -> list[str]:
    """Return the most recent completed calendar-year labels, newest first.

    Example: during 2026 this returns ["2025", ..., "2016"] for years=10.
    The current partial year is intentionally excluded because YTD is tracked separately.
    """
    end = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.now()
    years = max(1, int(years))
    return [str(end.year - offset) for offset in range(1, years + 1)]


def _year_end_price(close: pd.Series, year: int, tolerance_days: int = 10) -> Optional[float]:
    """Return the final adjusted close for a calendar year when coverage is genuine."""
    if close is None or close.empty:
        return None
    anchor = pd.Timestamp(year=year, month=12, day=31)
    within_year = close.loc[(close.index.year == year) & (close.index <= anchor)]
    if within_year.empty:
        return None
    ts = pd.Timestamp(within_year.index[-1])
    if (anchor - ts).days > tolerance_days:
        return None
    value = float(within_year.iloc[-1])
    return value if np.isfinite(value) and value > 0 else None


def calculate_monthly_returns(
    history: pd.DataFrame,
    start_year: int,
    end_year: int,
) -> dict[str, Optional[float]]:
    """Calculate actual adjusted month-end returns for an inclusive calendar span.

    For month M, return = adjusted close at the final trading day of M divided by
    the adjusted close at the final trading day of the prior calendar month - 1.
    January therefore uses the prior December month-end close as its base. Missing
    or incomplete month-end coverage is returned as None instead of being inferred
    from annual returns.
    """
    close = _normalize_close(history)
    start_year = int(start_year)
    end_year = int(end_year)
    if end_year < start_year:
        start_year, end_year = end_year, start_year

    labels = [
        f"{year}-{month:02d}"
        for year in range(start_year, end_year + 1)
        for month in range(1, 13)
    ]
    if close.empty:
        return {label: None for label in labels}

    # Use the final observed adjusted close in each calendar month. Daily history
    # already excludes non-trading days, so this naturally selects the final
    # trading session of the month.
    monthly_close = close.groupby(close.index.to_period("M")).last().sort_index()
    result: dict[str, Optional[float]] = {}
    for label in labels:
        period = pd.Period(label, freq="M")
        prior = period - 1
        finish = monthly_close.get(period)
        base = monthly_close.get(prior)
        if (
            finish is None or base is None
            or not np.isfinite(finish) or not np.isfinite(base)
            or float(finish) <= 0 or float(base) <= 0
        ):
            result[label] = None
        else:
            result[label] = float(finish / base - 1.0)
    return result


def calculate_calendar_year_returns(
    history: pd.DataFrame,
    years: int = 10,
    as_of: Optional[pd.Timestamp] = None,
) -> dict[str, Optional[float]]:
    """Calculate actual completed calendar-year returns, not CAGR.

    For year Y, return = adjusted close at the end of Y / adjusted close at the
    end of Y-1 - 1. A year is N/A when the instrument lacks a valid prior-year
    anchor (for example, an IPO that began during that year).
    """
    close = _normalize_close(history)
    labels = completed_year_labels(as_of=as_of, years=years)
    if close.empty:
        return {label: None for label in labels}

    result: dict[str, Optional[float]] = {}
    for label in labels:
        year = int(label)
        base = _year_end_price(close, year - 1)
        finish = _year_end_price(close, year)
        result[label] = _total_return(finish, base) if finish is not None else None
    return result


def calculate_performance(
    history: pd.DataFrame,
    live_price: Optional[float] = None,
    as_of: Optional[pd.Timestamp] = None,
) -> PerformanceResult:
    close = _normalize_close(history)
    if close.empty:
        return PerformanceResult(
            current_price=None,
            inception_date=None,
            since_inception=None,
            avg_10y=None,
            avg_9y=None,
            avg_8y=None,
            avg_7y=None,
            avg_6y=None,
            avg_5y=None,
            avg_4y=None,
            avg_3y=None,
            avg_2y=None,
            avg_1y=None,
            perf_1y=None,
            ytd=None,
            perf_6m=None,
            perf_3m=None,
            perf_1m=None,
            perf_1d=None,
        )

    end = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.now().tz_localize(None)
    end = end.tz_localize(None) if getattr(end, "tzinfo", None) else end

    current = (
        float(live_price)
        if live_price is not None and np.isfinite(live_price) and live_price > 0
        else float(close.iloc[-1])
    )
    inception_date = pd.Timestamp(close.index[0])
    inception_price = float(close.iloc[0])

    today = end.normalize()
    has_live = live_price is not None and np.isfinite(live_price) and live_price > 0
    if has_live:
        if close.index[-1].normalize() >= today and len(close) >= 2:
            prev_close = float(close.iloc[-2])
        else:
            prev_close = float(close.iloc[-1])
    else:
        prev_close = float(close.iloc[-2]) if len(close) >= 2 else None

    def period_return(months: int = 0, years: int = 0) -> Optional[float]:
        target = end - pd.DateOffset(months=months, years=years)
        base, _ = _price_near_target(close, target)
        return _total_return(current, base)

    def horizon_cagr(years: int) -> Optional[float]:
        target = end - pd.DateOffset(years=years)
        base, start = _price_near_target(close, target)
        if (
            inception_date <= target + pd.Timedelta(days=10)
            and base is not None
            and start is not None
        ):
            return _annualized_return(current, base, start, end)
        return None

    jan1 = pd.Timestamp(year=end.year, month=1, day=1)
    ytd_base = _price_on_or_before(close, jan1 - pd.Timedelta(days=1))
    if ytd_base is None:
        first_year = close.loc[close.index >= jan1]
        ytd_base = float(first_year.iloc[0]) if not first_year.empty else None

    one_year_total = period_return(years=1)

    return PerformanceResult(
        current_price=current,
        inception_date=inception_date,
        since_inception=_total_return(current, inception_price),
        avg_10y=horizon_cagr(10),
        avg_9y=horizon_cagr(9),
        avg_8y=horizon_cagr(8),
        avg_7y=horizon_cagr(7),
        avg_6y=horizon_cagr(6),
        avg_5y=horizon_cagr(5),
        avg_4y=horizon_cagr(4),
        avg_3y=horizon_cagr(3),
        avg_2y=horizon_cagr(2),
        avg_1y=horizon_cagr(1),
        perf_1y=one_year_total,
        ytd=_total_return(current, ytd_base),
        perf_6m=period_return(months=6),
        perf_3m=period_return(months=3),
        perf_1m=period_return(months=1),
        perf_1d=_total_return(current, prev_close),
    )


def _last_or_none(series: pd.Series) -> Optional[float]:
    if series is None or series.empty:
        return None
    value = series.iloc[-1]
    return float(value) if pd.notna(value) and np.isfinite(value) else None


def _rsi(close: pd.Series, window: int = 14) -> Optional[float]:
    if len(close) < window + 2:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    value = _last_or_none(rsi)
    if value is None and _last_or_none(loss) == 0:
        return 100.0
    return value


def calculate_buy_signals(
    history: pd.DataFrame,
    analyst_rating: str = "Not Rated",
    instrument_type: str = "Stock",
) -> SignalResult:
    """Rule-based informational buy-signal classifier.

    Short horizon is technical only. Long horizon combines long-trend technical
    strength with Nasdaq consensus for stocks; ETFs use technical criteria because
    Nasdaq's public ETF screener generally does not provide stock-style consensus.
    A Nasdaq Strong Buy consensus is also treated as a fundamental/consensus buy
    signal for stocks.
    """
    close = _normalize_close(history)
    if close.empty:
        return SignalResult(False, False, False, 0, 0, None, None, None, None, None, None, "")

    perf = calculate_performance(history)
    price = float(close.iloc[-1])
    sma20 = _last_or_none(close.rolling(20).mean())
    sma50 = _last_or_none(close.rolling(50).mean())
    sma200 = _last_or_none(close.rolling(200).mean())
    rsi14 = _rsi(close, 14)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_series = ema12 - ema26
    signal_series = macd_series.ewm(span=9, adjust=False).mean()
    macd = _last_or_none(macd_series)
    macd_signal = _last_or_none(signal_series)

    short_checks: list[tuple[bool, str]] = [
        (sma20 is not None and price > sma20, "price above 20-day average"),
        (sma20 is not None and sma50 is not None and sma20 > sma50, "20-day average above 50-day average"),
        (macd is not None and macd_signal is not None and macd > macd_signal, "MACD above signal line"),
        (rsi14 is not None and 50 <= rsi14 <= 70, "RSI in bullish 50-70 zone"),
        (perf.perf_1m is not None and perf.perf_1m > 0, "1-month momentum positive"),
        (perf.perf_3m is not None and perf.perf_3m > 0, "3-month momentum positive"),
    ]
    short_score = sum(int(ok) for ok, _ in short_checks)

    rating = str(analyst_rating or "Not Rated").strip().lower()
    rating_is_sell = rating in {"sell", "strong sell"}
    short_buy = short_score >= 5 and not rating_is_sell

    long_checks: list[tuple[bool, str]] = [
        (sma200 is not None and price > sma200, "price above 200-day average"),
        (sma50 is not None and sma200 is not None and sma50 > sma200, "50-day average above 200-day average"),
        (perf.perf_6m is not None and perf.perf_6m > 0, "6-month return positive"),
        (perf.avg_1y is not None and perf.avg_1y > 0, "1-year annualized return positive"),
        (perf.avg_3y is not None and perf.avg_3y > 0, "3-year annualized return positive"),
        (perf.avg_5y is not None and perf.avg_5y > 0, "5-year annualized return positive"),
    ]
    long_score = sum(int(ok) for ok, _ in long_checks)
    long_technical = (
        sma200 is not None
        and sma50 is not None
        and price > sma200
        and sma50 > sma200
        and long_score >= 4
    )

    is_stock = str(instrument_type).strip().lower() == "stock"
    fundamental_buy = is_stock and rating == "strong buy"
    consensus_positive = is_stock and rating in {"strong buy", "buy"}
    if is_stock:
        long_buy = fundamental_buy or (long_technical and consensus_positive)
    else:
        long_buy = long_technical

    reasons: list[str] = []
    if short_buy:
        reasons.append("Short technical: " + "; ".join(reason for ok, reason in short_checks if ok))
    if fundamental_buy:
        reasons.append("Fundamental/consensus: Nasdaq Strong Buy")
    if long_technical:
        reasons.append("Long technical: " + "; ".join(reason for ok, reason in long_checks if ok))
    if is_stock and long_technical and consensus_positive and not fundamental_buy:
        reasons.append("Consensus confirmation: Nasdaq Buy")

    return SignalResult(
        short_buy=bool(short_buy),
        long_buy=bool(long_buy),
        fundamental_buy=bool(fundamental_buy),
        short_score=int(short_score),
        long_score=int(long_score),
        rsi14=rsi14,
        sma20=sma20,
        sma50=sma50,
        sma200=sma200,
        macd=macd,
        macd_signal=macd_signal,
        reasons=" | ".join(reasons),
    )


def as_percent(value: Optional[float]) -> Optional[float]:
    return None if value is None or not np.isfinite(value) else value * 100.0
