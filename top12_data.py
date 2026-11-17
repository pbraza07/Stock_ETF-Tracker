"""Reuse durable monthly datasets without per-stock network history downloads."""

from pathlib import Path
import re
import pandas as pd
from persistence import load_remote_csv, now_et
import numpy as np


def load_monthly(symbols, years, remote=True):
    result = {s: {} for s in symbols}
    today = now_et().date()
    current_month = today.strftime('%Y-%m')
    first_year = min((int(y) for y in years if str(y).isdigit()), default=today.year)
    observation_dates = {}
    value_dates = {}
    root = Path(__file__).parent / "data"
    for name in (
        "monthly_returns_10y.csv",
        "monthly_returns_25y.csv",
        "monthly_returns_full_history.csv",
    ):
        path = root / name
        frame = (
            pd.read_csv(path)
            if path.exists()
            else (
                load_remote_csv("data/" + name, timeout=5) if remote else pd.DataFrame()
            )
        )
        if frame.empty or "Symbol" not in frame:
            continue
        labels = [
            c for c in frame if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", str(c))
            and first_year <= int(c[:4]) and c <= current_month
        ]
        for row in frame.to_dict("records"):
            symbol = str(row["Symbol"]).upper().strip()
            if symbol not in result:
                continue
            observation = str(row.get('Monthly Observation Through') or '')
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}', observation) and observation <= today.isoformat():
                observation_dates[symbol] = max(observation_dates.get(symbol, ''), observation)
            else:
                observation = ''
            for label in labels:
                value = pd.to_numeric(row.get(label), errors="coerce")
                if (pd.notna(value) and np.isfinite(value) and value > -100
                        and observation >= value_dates.get((symbol, label), "")):
                    result[symbol][label] = float(value) / 100
                    value_dates[(symbol, label)] = observation
    partial = current_month if any(current_month in h for h in result.values()) else None
    return {"returns": result, "source": "MarketScope durable actual monthly datasets",
            "partial_month": partial, "observation_dates": observation_dates,
            "requested_through": current_month}


def monthly_metadata(monthly):
    histories = monthly.get('returns') or {}
    latest = {s: max(h) for s, h in histories.items() if h}
    through = max(latest.values(), default='Unavailable')
    partial = monthly.get('partial_month')
    dates = monthly.get('observation_dates') or {}
    return {
        'Monthly Data Through': through,
        'Monthly Period Basis': f'{partial} is partial month-to-date' if partial else 'Completed months / latest available saved observations',
        'Monthly Observation Through': max(dates.values(), default='Unavailable — older dataset has no observation date'),
        'Monthly Current Coverage': f"{sum(m == monthly.get('requested_through') for m in latest.values())}/{len(histories)} instruments",
        'Monthly Oldest Instrument Through': min(latest.values(), default='Unavailable'),
        'Monthly Risk Basis': 'Completed monthly returns only; partial MTD excluded from monthly risk calibration',
    }


def extend_with_recent_history(monthly, live):
    """Reuse already retrieved adjusted daily history for current-year months."""
    from analytics import _normalize_close, calculate_monthly_returns
    from copy import deepcopy
    result = deepcopy(monthly or {'returns': {}})
    result.setdefault('returns', {})
    dates = result.setdefault('observation_dates', {})
    today = now_et().date()
    current_month = today.strftime('%Y-%m')
    for symbol, history in ((live or {}).get('histories') or {}).items():
        if symbol not in result['returns'] or history is None or history.empty:
            continue
        close = _normalize_close(history)
        close = close[[d.date() <= today for d in close.index]]
        if close.empty:
            continue
        observed = close.index[-1].date().isoformat()
        if observed < dates.get(symbol, ''):
            continue
        values = calculate_monthly_returns(close.to_frame('Close'), today.year, today.year)
        for label, value in values.items():
            if label <= current_month and value is not None and np.isfinite(value) and value > -1:
                result['returns'][symbol][label] = float(value)
        dates[symbol] = observed
    result['requested_through'] = current_month
    result['partial_month'] = current_month if any(current_month in h for h in result['returns'].values()) else None
    return result
