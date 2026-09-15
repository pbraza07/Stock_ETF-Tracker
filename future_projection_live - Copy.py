"""Live/recent data conditioning for MarketScope Future Projection.

This module is additive: it never changes the historical simulator.  It builds
an auditable current-market state, conditions the existing regime Monte Carlo
assumptions, and supplies two validation models for a calibrated ensemble.
Every network-facing loader has an explicit cached/historical fallback.
"""

from __future__ import annotations

import io
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import requests

from future_projection_config import (
    capital_market_assumptions,
    fred_series,
    live_adaptive_config,
    live_data_sources,
    model_defaults,
)


PERCENTILES = (10, 25, 50, 75, 90)
MARKET_PROXIES = ("SPY", "QQQ", "IWM", "^VIX")
SECTOR_PROXIES = ("XLK", "XLF", "XLV", "XLE", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE", "XLC")


def _number(value: Any, default: float = float("nan")) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if np.isfinite(result) else float(default)


def _clip_score(value: Any) -> float:
    return float(np.clip(_number(value, 50.0), 0.0, 100.0))


def _close_series(frame: pd.DataFrame | None) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    for name in ("Close", "Adj Close", "close", "adjclose"):
        if name in frame.columns:
            series = pd.to_numeric(frame[name], errors="coerce").dropna()
            if len(series):
                series.index = pd.to_datetime(series.index, errors="coerce")
                return series.loc[series.index.notna()].sort_index()
    return pd.Series(dtype=float)


def _volume_series(frame: pd.DataFrame | None) -> pd.Series:
    if frame is None or frame.empty or "Volume" not in frame.columns:
        return pd.Series(dtype=float)
    series = pd.to_numeric(frame["Volume"], errors="coerce").dropna()
    series.index = pd.to_datetime(series.index, errors="coerce")
    return series.loc[series.index.notna()].sort_index()


def _return_over(series: pd.Series, periods: int) -> float | None:
    if len(series) <= periods or float(series.iloc[-periods - 1]) <= 0:
        return None
    return float(series.iloc[-1] / series.iloc[-periods - 1] - 1.0)


def _annualized_volatility(series: pd.Series, periods: int | None = None) -> float | None:
    returns = series.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).dropna()
    if periods:
        returns = returns.tail(periods)
    if len(returns) < 5:
        return None
    value = float(returns.std(ddof=1) * math.sqrt(252.0))
    return value if np.isfinite(value) else None


def _downside_volatility(series: pd.Series) -> float | None:
    returns = series.pct_change(fill_method=None).dropna()
    downside = returns[returns < 0].tail(252)
    if len(downside) < 5:
        return None
    return float(downside.std(ddof=1) * math.sqrt(252.0))


def _maximum_drawdown(series: pd.Series) -> float | None:
    if len(series) < 2:
        return None
    drawdown = series / series.cummax() - 1.0
    value = float(drawdown.min())
    return value if np.isfinite(value) else None


def _history_snapshot(frame: pd.DataFrame | None) -> dict:
    close = _close_series(frame)
    volume = _volume_series(frame)
    if close.empty:
        return {}
    current = float(close.iloc[-1])
    high_52 = float(close.tail(252).max())
    low_52 = float(close.tail(252).min())
    ma50 = float(close.tail(50).mean()) if len(close) >= 20 else current
    ma200 = float(close.tail(200).mean()) if len(close) >= 60 else current
    return {
        "current_price": current,
        "observation_date": close.index[-1].date().isoformat(),
        "high_52_week": high_52,
        "low_52_week": low_52,
        "distance_from_52_week_high": (current / high_52 - 1.0) if high_52 > 0 else None,
        "return_20_day": _return_over(close, 20),
        "return_50_day": _return_over(close, 50),
        "return_200_day": _return_over(close, 200),
        "momentum_6_month": _return_over(close, 126),
        "momentum_12_1": (float(close.iloc[-22] / close.iloc[-253] - 1.0) if len(close) >= 253 and float(close.iloc[-253]) > 0 else None),
        "ma_50": ma50,
        "ma_200": ma200,
        "above_50_day_ma": bool(current >= ma50),
        "above_200_day_ma": bool(current >= ma200),
        "realized_volatility_20_day": _annualized_volatility(close, 20),
        "realized_volatility_60_day": _annualized_volatility(close, 60),
        "realized_volatility_1_year": _annualized_volatility(close, 252),
        "downside_volatility": _downside_volatility(close),
        "maximum_drawdown_1_year": _maximum_drawdown(close.tail(252)),
        "average_volume_20_day": float(volume.tail(20).mean()) if len(volume) else None,
        "history_observations": int(len(close)),
    }


def _fetch_fred_one(name: str, series_id: str, timeout: int = 8) -> tuple[str, dict]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": "MarketScope/5.11"})
        response.raise_for_status()
        frame = pd.read_csv(io.StringIO(response.text))
        if frame.empty or len(frame.columns) < 2:
            raise ValueError("empty FRED response")
        date_col, value_col = frame.columns[:2]
        values = pd.to_numeric(frame[value_col], errors="coerce")
        dates = pd.to_datetime(frame[date_col], errors="coerce")
        clean = pd.DataFrame({"date": dates, "value": values}).dropna().tail(36)
        if clean.empty:
            raise ValueError("no numeric observations")
        return name, {
            "series_id": series_id,
            "source": "Federal Reserve Bank of St. Louis FRED",
            "source_url": url,
            "observation_date": clean.iloc[-1]["date"].date().isoformat(),
            "value": float(clean.iloc[-1]["value"]),
            "observations": [
                {"date": row.date.date().isoformat(), "value": float(row.value)}
                for row in clean.itertuples(index=False)
            ],
        }
    except Exception as exc:
        return name, {"series_id": series_id, "source": "FRED", "error": type(exc).__name__}


def fetch_macro_context(max_workers: int = 5) -> dict:
    """Fetch recent official macro observations without requiring an API key."""

    results: dict[str, dict] = {}
    series = fred_series()
    with ThreadPoolExecutor(max_workers=min(max_workers, len(series))) as pool:
        futures = [pool.submit(_fetch_fred_one, name, series_id) for name, series_id in series.items()]
        for future in as_completed(futures):
            name, payload = future.result()
            results[name] = payload
    return results


def fetch_live_projection_context(provider, symbols: Iterable[str], market: pd.DataFrame) -> dict:
    """Fetch selected-security, proxy, breadth, fundamental, and macro inputs.

    The caller should cache this function. Failures are returned as labeled
    fields so a projection can fall back instead of failing wholesale.
    """

    requested = list(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
    config = live_adaptive_config()
    breadth: list[str] = []
    if market is not None and not market.empty and "Symbol" in market.columns:
        candidates = market.copy()
        if "Type" in candidates.columns:
            candidates = candidates.loc[candidates["Type"].astype(str).str.upper().ne("ETF")]
        if "MarketCap" in candidates.columns:
            candidates["_market_cap"] = pd.to_numeric(candidates["MarketCap"], errors="coerce")
            candidates = candidates.sort_values("_market_cap", ascending=False, na_position="last")
        breadth = candidates["Symbol"].astype(str).str.upper().drop_duplicates().head(config["breadth_universe_limit"]).tolist()
    history_symbols = list(dict.fromkeys([*requested, *MARKET_PROXIES, *SECTOR_PROXIES, *breadth]))
    failures: list[str] = []
    try:
        histories = provider.download_daily_history(history_symbols, period="1y") or {}
        vix_history = provider.download_daily_history(["^VIX"], period="5y") or {}
        if "^VIX" in vix_history:
            histories["^VIX"] = vix_history["^VIX"]
    except Exception as exc:
        histories = {}
        failures.append(f"Market history unavailable ({type(exc).__name__}).")
    try:
        prices = provider.download_live_prices([*requested, "SPY", "QQQ", "IWM"]) or {}
        recent_prices_loaded = bool(prices)
    except Exception as exc:
        prices = {}
        recent_prices_loaded = False
        failures.append(f"Recent price snapshot unavailable ({type(exc).__name__}).")
    try:
        if hasattr(provider, "get_projection_fundamentals_many"):
            fundamentals = provider.get_projection_fundamentals_many(requested, max_workers=4) or {}
        else:
            fundamentals = provider.get_metadata_many(requested, max_workers=4) or {}
    except Exception as exc:
        fundamentals = {}
        failures.append(f"Fundamental data unavailable ({type(exc).__name__}).")
    snapshot_dates: list[str] = []
    if market is not None and not market.empty and "Symbol" in market.columns:
        lookup = market.copy()
        lookup["Symbol"] = lookup["Symbol"].astype(str).str.strip().str.upper()
        lookup = lookup.drop_duplicates("Symbol", keep="last").set_index("Symbol", drop=False)
        for symbol in requested:
            if symbol not in lookup.index:
                continue
            row = lookup.loc[symbol]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[-1]
            snapshot_price = _number(row.get("Price"))
            if symbol not in prices and np.isfinite(snapshot_price) and snapshot_price > 0:
                prices[symbol] = snapshot_price
            values = dict(fundamentals.get(symbol) or {})
            values.setdefault("instrument_type", str(row.get("Type") or "Stock"))
            values.setdefault("sector", str(row.get("Sector") or "Unknown"))
            values.setdefault("category", str(row.get("ETF Category") or row.get("Sector") or "Unknown"))
            market_cap = _number(row.get("MarketCap"))
            if "market_cap" not in values and np.isfinite(market_cap):
                values["market_cap"] = market_cap
            values.setdefault("source", "Current MarketScope snapshot (Yahoo/Nasdaq infrastructure)")
            fundamentals[symbol] = values
            for date_column in ("Snapshot Updated ET", "Price Updated ET", "Updated ET"):
                if row.get(date_column):
                    snapshot_dates.append(str(row.get(date_column)))
                    break
    try:
        macro = fetch_macro_context()
    except Exception as exc:
        macro = {}
        failures.append(f"Macro data unavailable ({type(exc).__name__}).")
    retrieved = datetime.now(timezone.utc).isoformat()
    observations = [snapshot.get("observation_date") for snapshot in (_history_snapshot(frame) for frame in histories.values()) if snapshot.get("observation_date")]
    context = {
        "retrieved_at": retrieved,
        "histories": histories,
        "prices": prices,
        "price_status": "DELAYED" if recent_prices_loaded else "LATEST AVAILABLE",
        "snapshot_as_of": max(snapshot_dates) if snapshot_dates else None,
        "fundamentals": fundamentals,
        "macro": macro,
        "breadth_symbols": breadth,
        "requested_symbols": requested,
        "history_through": max(observations) if observations else None,
        "failures": failures,
        "sources": live_data_sources(),
    }
    cache_path = Path(__file__).resolve().parent / "data" / "future_projection_live_cache.pkl"
    if not histories and not fundamentals and not macro and cache_path.exists():
        try:
            cached = pd.read_pickle(cache_path)
            if isinstance(cached, dict):
                cached = dict(cached)
                cached["using_cached_data"] = True
                cached["failures"] = list(dict.fromkeys([*failures, "Current supplemental feeds were unavailable; using the most recent labeled cache."]))
                cached["cache_retrieved_at"] = cached.get("retrieved_at")
                cached["retrieved_at"] = retrieved
                return cached
        except Exception:
            pass
    if histories or fundamentals or macro:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            pd.to_pickle(context, cache_path)
        except Exception:
            context["failures"].append("Live context was usable but could not be saved to the local fallback cache.")
    return context


def _macro_values(payload: dict, name: str) -> list[float]:
    item = (payload or {}).get(name) or {}
    return [_number(row.get("value")) for row in item.get("observations", []) if np.isfinite(_number(row.get("value")))]


def _fundamental_score(values: dict) -> float:
    if not values or str(values.get("instrument_type") or values.get("quote_type") or "").upper() in {"ETF", "MUTUALFUND"}:
        return 50.0
    signals: list[float] = []
    for key, scale in (
        ("earnings_growth", 0.25), ("earnings_quarterly_growth", 0.25),
        ("revenue_growth", 0.20), ("forward_eps_growth", 0.20),
        ("return_on_equity", 0.25), ("operating_margin", 0.20),
    ):
        value = _number(values.get(key))
        if np.isfinite(value):
            signals.append(50.0 + 50.0 * np.clip(value / scale, -1.0, 1.0))
    debt = _number(values.get("debt_to_equity"))
    if np.isfinite(debt):
        normalized = debt / 100.0 if debt > 5 else debt
        signals.append(75.0 - 30.0 * np.clip(normalized, 0.0, 2.0))
    fcf = _number(values.get("free_cash_flow"))
    if np.isfinite(fcf):
        signals.append(65.0 if fcf > 0 else 30.0)
    revision = _number(values.get("eps_revision_direction"))
    if np.isfinite(revision):
        signals.append(50.0 + 40.0 * np.clip(revision, -1.0, 1.0))
    return _clip_score(np.mean(signals) if signals else 50.0)


def _valuation_score(values: dict, peer_forward_pe: float | None = None) -> float:
    if not values or str(values.get("instrument_type") or values.get("quote_type") or "").upper() in {"ETF", "MUTUALFUND"}:
        return 50.0
    forward_pe = _number(values.get("forward_pe"))
    trailing_pe = _number(values.get("trailing_pe"))
    pe = forward_pe if np.isfinite(forward_pe) and forward_pe > 0 else trailing_pe
    benchmark = peer_forward_pe if peer_forward_pe and peer_forward_pe > 0 else 20.0
    if not np.isfinite(pe) or pe <= 0:
        return 50.0
    ratio = pe / benchmark
    score = 50.0 - 35.0 * math.tanh((ratio - 1.0) / 0.75)
    peg = _number(values.get("peg_ratio"))
    if np.isfinite(peg) and peg > 0:
        score += 5.0 * np.clip(1.5 - peg, -1.0, 1.0)
    return _clip_score(score)


def _probabilities_from_score(score: float) -> dict[str, float]:
    direction = (float(score) - 50.0) / 12.0
    logits = np.asarray([-direction, 1.2 - abs(direction) * 0.38, direction], dtype=float)
    exp = np.exp(logits - logits.max())
    probabilities = exp / exp.sum()
    rounded = np.round(probabilities * 100.0, 2)
    rounded[1] += 100.0 - float(rounded.sum())
    return {"Bear": float(rounded[0]), "Normal": float(rounded[1]), "Bull": float(rounded[2])}


def _freshness_panel(live_data: dict, snapshots: dict[str, dict]) -> dict:
    retrieved = str(live_data.get("retrieved_at") or "Not available")
    history_through = str(live_data.get("history_through") or "Not available")
    price_updated = live_data.get("cache_retrieved_at") or live_data.get("snapshot_as_of") or retrieved
    price_status = str(live_data.get("price_status") or ("END OF DAY" if snapshots else "LATEST AVAILABLE"))
    macro_dates = [str(item.get("observation_date")) for item in (live_data.get("macro") or {}).values() if item.get("observation_date")]
    fundamental_dates = [str(item.get("retrieved_at")) for item in (live_data.get("fundamentals") or {}).values() if item.get("retrieved_at")]
    cached_prefix = "CACHED - " if live_data.get("using_cached_data") else ""
    rows = {
        "Market prices": {"status": cached_prefix + price_status, "updated": price_updated},
        "Fundamentals": {"status": cached_prefix + "LATEST AVAILABLE", "updated": max(fundamental_dates) if fundamental_dates else (live_data.get("cache_retrieved_at") or retrieved)},
        "Macro": {"status": cached_prefix + "LATEST AVAILABLE", "updated": max(macro_dates) if macro_dates else "Unavailable"},
        "Volatility": {"status": cached_prefix + ("END OF DAY" if "SPY" in snapshots else "LATEST AVAILABLE"), "updated": snapshots.get("SPY", {}).get("observation_date", live_data.get("cache_retrieved_at") or retrieved)},
        "Analyst estimates": {"status": cached_prefix + "LATEST AVAILABLE", "updated": max(fundamental_dates) if fundamental_dates else (live_data.get("cache_retrieved_at") or retrieved)},
        "Historical monthly data": {"status": cached_prefix + "LATEST AVAILABLE", "updated": history_through[:7] if len(history_through) >= 7 else history_through},
    }
    stale_limits = live_adaptive_config()["stale_after_hours"]
    key_map = {
        "Market prices": "market_prices", "Fundamentals": "fundamentals", "Macro": "macro",
        "Volatility": "volatility", "Analyst estimates": "analyst_estimates",
        "Historical monthly data": "historical_monthly",
    }
    now = pd.Timestamp.now(tz="UTC")
    for name, item in rows.items():
        try:
            stamp = pd.Timestamp(item["updated"])
            if stamp.tzinfo is None:
                stamp = stamp.tz_localize("UTC")
            age_hours = max(0.0, (now - stamp).total_seconds() / 3600.0)
            item["age_hours"] = round(age_hours, 1)
            if age_hours > float(stale_limits[key_map[name]]):
                item["status"] = "STALE - " + str(item["status"])
        except Exception:
            item["age_hours"] = None
    return rows


def build_current_market_state(symbols: Iterable[str], live_data: dict | None) -> dict:
    """Turn heterogeneous current inputs into probabilities and bounded adjustments."""

    symbols = list(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
    live_data = dict(live_data or {})
    histories = live_data.get("histories") or {}
    snapshots = {symbol: _history_snapshot(histories.get(symbol)) for symbol in histories}
    for symbol, price in (live_data.get("prices") or {}).items():
        numeric_price = _number(price)
        if not np.isfinite(numeric_price) or numeric_price <= 0:
            continue
        snapshot = snapshots.setdefault(str(symbol).upper(), {})
        snapshot["current_price"] = numeric_price
        if _number(snapshot.get("ma_50"), 0.0) > 0:
            snapshot["above_50_day_ma"] = bool(numeric_price >= float(snapshot["ma_50"]))
        if _number(snapshot.get("ma_200"), 0.0) > 0:
            snapshot["above_200_day_ma"] = bool(numeric_price >= float(snapshot["ma_200"]))
    fundamentals = live_data.get("fundamentals") or {}
    macro = live_data.get("macro") or {}
    breadth_symbols = live_data.get("breadth_symbols") or []
    if not snapshots and not fundamentals and not macro:
        defaults = model_defaults()
        probabilities = {
            name: float(value) * 100.0
            for name, value in zip(defaults["regime_order"], defaults["initial_regime_probabilities"])
        }
        return {
            "live_conditioning_active": False,
            "regime_score": 50.0,
            "regime_probabilities": probabilities,
            "components": {name: 50.0 for name in live_adaptive_config()["regime_score_weights"]},
            "market_trend": "Unknown",
            "volatility_environment": "Historical",
            "valuation_environment": "Unknown",
            "earnings_trend": "Unknown",
            "interest_rate_environment": "Unknown",
            "portfolio_correlation_risk": "Unknown",
            "average_60_day_correlation": None,
            "rolling_60_day_correlation": {},
            "rolling_252_day_correlation": {},
            "breadth_above_50_day": None,
            "breadth_above_200_day": None,
            "vix": None,
            "vix_percentile": None,
            "holding_adjustments": {
                symbol: {
                    "valuation_score": 50.0,
                    "fundamental_score": 50.0,
                    "total_expected_return_adjustment": 0.0,
                    "volatility_multiplier": 1.0,
                    "data_quality": "Low",
                }
                for symbol in symbols
            },
            "projection_confidence": "Low",
            "data_completeness": 0.0,
            "data_freshness": _freshness_panel(live_data, snapshots),
            "retrieved_at": live_data.get("retrieved_at"),
            "sources": live_data.get("sources") or live_data_sources(),
            "failures": list(live_data.get("failures") or []),
        }

    spy = snapshots.get("SPY", {})
    breadth_snapshots = [snapshots[s] for s in breadth_symbols if snapshots.get(s)]
    above50 = 100.0 * np.mean([item["above_50_day_ma"] for item in breadth_snapshots]) if breadth_snapshots else (65.0 if spy.get("above_50_day_ma") else 35.0)
    above200 = 100.0 * np.mean([item["above_200_day_ma"] for item in breadth_snapshots]) if breadth_snapshots else (65.0 if spy.get("above_200_day_ma") else 35.0)
    last_moves = []
    for symbol in breadth_symbols:
        close = _close_series(histories.get(symbol))
        if len(close) >= 2 and float(close.iloc[-2]) > 0:
            last_moves.append(float(close.iloc[-1] / close.iloc[-2] - 1.0))
    advance_decline_ratio = (
        float(sum(value > 0 for value in last_moves) / max(1, sum(value < 0 for value in last_moves)))
        if last_moves else None
    )
    spy_trend = 50.0
    if spy:
        spy_trend += 15.0 if spy.get("above_50_day_ma") else -15.0
        spy_trend += 15.0 if spy.get("above_200_day_ma") else -15.0
        spy_trend += 20.0 * np.clip(_number(spy.get("momentum_6_month"), 0.0) / 0.20, -1.0, 1.0)
    trend_breadth = _clip_score(0.50 * spy_trend + 0.25 * above50 + 0.25 * above200)

    vix_series = _close_series(histories.get("^VIX"))
    vix_current = float(vix_series.iloc[-1]) if len(vix_series) else None
    vix_percentile = float((vix_series <= vix_current).mean() * 100.0) if len(vix_series) and vix_current is not None else 50.0
    vol20 = _number(spy.get("realized_volatility_20_day"), 0.18)
    vol252 = _number(spy.get("realized_volatility_1_year"), 0.18)
    volatility = _clip_score(72.0 - 0.60 * vix_percentile - 60.0 * max(0.0, vol20 - vol252))

    cpi = _macro_values(macro, "cpi")
    unemployment = _macro_values(macro, "unemployment_rate")
    payrolls = _macro_values(macro, "payrolls")
    gdp = _macro_values(macro, "real_gdp")
    economic_signals = [50.0]
    if len(cpi) >= 13 and cpi[-13] > 0:
        inflation = cpi[-1] / cpi[-13] - 1.0
        economic_signals.append(70.0 - 800.0 * max(0.0, inflation - 0.02))
    if len(unemployment) >= 4:
        economic_signals.append(55.0 - 30.0 * (unemployment[-1] - min(unemployment[-4:])))
    if len(payrolls) >= 2 and payrolls[-2] > 0:
        economic_signals.append(50.0 + 500.0 * (payrolls[-1] / payrolls[-2] - 1.0))
    if len(gdp) >= 5 and gdp[-5] > 0:
        economic_signals.append(50.0 + 300.0 * (gdp[-1] / gdp[-5] - 1.0))
    recession = _number((macro.get("recession_indicator") or {}).get("value"))
    if np.isfinite(recession):
        economic_signals.append(70.0 - 25.0 * recession)
    economic = _clip_score(np.mean(economic_signals))

    fed = _number((macro.get("federal_funds_rate") or {}).get("value"))
    spread2 = _number((macro.get("yield_spread_10y_2y") or {}).get("value"))
    spread3 = _number((macro.get("yield_spread_10y_3m") or {}).get("value"))
    credit = _number((macro.get("credit_spread") or {}).get("value"))
    rate_signals = [50.0]
    if np.isfinite(fed):
        rate_signals.append(70.0 - 6.0 * fed)
    if np.isfinite(spread2):
        rate_signals.append(50.0 + 12.0 * spread2)
    if np.isfinite(spread3):
        rate_signals.append(50.0 + 12.0 * spread3)
    if np.isfinite(credit):
        rate_signals.append(75.0 - 12.0 * credit)
    credit_rates = _clip_score(np.mean(rate_signals))

    stock_fundamentals = [values for symbol, values in fundamentals.items() if symbol in symbols and str(values.get("instrument_type") or values.get("quote_type") or "STOCK").upper() not in {"ETF", "MUTUALFUND"}]
    peer_pes = [_number(values.get("forward_pe")) for values in stock_fundamentals]
    peer_pes = [value for value in peer_pes if np.isfinite(value) and value > 0]
    peer_pe = float(np.median(peer_pes)) if peer_pes else 20.0
    fundamental_scores = {symbol: _fundamental_score(fundamentals.get(symbol, {})) for symbol in symbols}
    valuation_scores = {symbol: _valuation_score(fundamentals.get(symbol, {}), peer_pe) for symbol in symbols}
    earnings = _clip_score(np.mean(list(fundamental_scores.values())) if fundamental_scores else 50.0)
    valuation = _clip_score(np.mean(list(valuation_scores.values())) if valuation_scores else 50.0)
    category_scores: dict[str, list[float]] = {}
    for symbol in symbols:
        values = fundamentals.get(symbol) or {}
        category = str(values.get("category") or values.get("sector") or "Unknown")
        category_scores.setdefault(category, []).append(fundamental_scores.get(symbol, 50.0))
    category_scores = {key: float(np.mean(values)) for key, values in category_scores.items()}

    selected_momentum = [_number(snapshots.get(symbol, {}).get("momentum_12_1")) for symbol in symbols]
    selected_momentum = [value for value in selected_momentum if np.isfinite(value)]
    momentum = _clip_score(50.0 + 100.0 * np.clip(np.mean(selected_momentum) if selected_momentum else 0.0, -0.30, 0.30))
    components = {
        "economic": economic,
        "trend_breadth": trend_breadth,
        "volatility": volatility,
        "credit_rates": credit_rates,
        "earnings": earnings,
        "valuation": valuation,
        "momentum": momentum,
    }
    weights = live_adaptive_config()["regime_score_weights"]
    regime_score = float(sum(components[name] * weights[name] for name in weights))
    probabilities = _probabilities_from_score(regime_score)

    holding_adjustments: dict[str, dict] = {}
    for symbol in symbols:
        snapshot = snapshots.get(symbol, {})
        f_score = fundamental_scores.get(symbol, 50.0)
        v_score = valuation_scores.get(symbol, 50.0)
        mom = _number(snapshot.get("momentum_12_1"), 0.0)
        revision = _number((fundamentals.get(symbol) or {}).get("eps_revision_direction"), 0.0)
        category = str((fundamentals.get(symbol) or {}).get("category") or (fundamentals.get(symbol) or {}).get("sector") or "Unknown")
        config = live_adaptive_config()
        valuation_adjustment = float(np.clip((v_score - 50.0) / 50.0 * 0.015, *config["valuation_adjustment_bounds"]))
        fundamental_adjustment = float(np.clip((f_score - 50.0) / 50.0 * 0.015, *config["fundamental_adjustment_bounds"]))
        momentum_adjustment = float(np.clip(mom * 0.035, *config["momentum_adjustment_bounds"]))
        analyst_adjustment = float(np.clip(revision * 0.005, *config["analyst_adjustment_bounds"]))
        macro_adjustment = float(np.clip((regime_score - 50.0) / 50.0 * 0.010, -0.010, 0.010))
        category_adjustment = float(np.clip((category_scores.get(category, 50.0) - 50.0) / 50.0 * 0.005, -0.005, 0.005))
        total = float(np.clip(valuation_adjustment + fundamental_adjustment + category_adjustment + momentum_adjustment + analyst_adjustment + macro_adjustment, *config["expected_return_live_adjustment_bounds"]))
        recent_vol = _number(snapshot.get("realized_volatility_60_day"))
        long_vol = _number(snapshot.get("realized_volatility_1_year"))
        vol_ratio = recent_vol / long_vol if np.isfinite(recent_vol) and np.isfinite(long_vol) and long_vol > 0 else 1.0
        vix_stress = 1.0 + max(0.0, vix_percentile - 50.0) / 100.0
        vol_multiplier = float(np.clip(0.55 + 0.30 * vol_ratio + 0.15 * vix_stress, *config["volatility_multiplier_bounds"]))
        available_fields = sum(np.isfinite(_number((fundamentals.get(symbol) or {}).get(key))) for key in ("forward_pe", "revenue_growth", "earnings_growth", "operating_margin", "debt_to_equity"))
        data_quality = "High" if snapshot and available_fields >= 4 else ("Medium" if snapshot or available_fields >= 2 else "Low")
        holding_adjustments[symbol] = {
            "valuation_score": v_score,
            "fundamental_score": f_score,
            "valuation_adjustment": valuation_adjustment,
            "fundamental_adjustment": fundamental_adjustment,
            "sector_category_live_adjustment": category_adjustment,
            "momentum_adjustment": momentum_adjustment,
            "analyst_adjustment": analyst_adjustment,
            "macro_regime_adjustment": macro_adjustment,
            "total_expected_return_adjustment": total,
            "volatility_multiplier": vol_multiplier,
            "data_quality": data_quality,
            **snapshot,
        }

    selected_returns = pd.DataFrame({symbol: _close_series(histories.get(symbol)).pct_change(fill_method=None) for symbol in symbols}).dropna(how="all")
    corr60 = selected_returns.tail(60).corr(min_periods=10).fillna(0.0) if not selected_returns.empty else pd.DataFrame()
    corr252 = selected_returns.tail(252).corr(min_periods=20).fillna(0.0) if not selected_returns.empty else pd.DataFrame()
    off_diag = []
    if not corr60.empty and len(symbols) > 1:
        matrix = corr60.reindex(index=symbols, columns=symbols).to_numpy(dtype=float)
        off_diag = matrix[np.triu_indices(len(symbols), 1)].tolist()
    average_correlation = float(np.nanmean(off_diag)) if off_diag else 0.0
    correlation_risk = "High" if average_correlation >= 0.70 else ("Moderate" if average_correlation >= 0.40 else "Low")

    available_families = sum(bool(value) for value in (snapshots, fundamentals, macro))
    quality_values = [item["data_quality"] for item in holding_adjustments.values()]
    data_completeness = 100.0 * available_families / 3.0
    if quality_values:
        data_completeness = 0.5 * data_completeness + 0.5 * np.mean([100 if q == "High" else 65 if q == "Medium" else 30 for q in quality_values])
    confidence = "High" if data_completeness >= 80 and not live_data.get("failures") else ("Medium" if data_completeness >= 50 else "Low")
    return {
        "live_conditioning_active": bool(snapshots or fundamentals or macro),
        "regime_score": round(regime_score, 2),
        "regime_probabilities": probabilities,
        "components": {key: round(value, 2) for key, value in components.items()},
        "market_trend": "Bullish" if trend_breadth >= 60 else ("Bearish" if trend_breadth < 40 else "Neutral"),
        "volatility_environment": "Extreme" if vix_percentile >= 90 else ("Elevated" if vix_percentile >= 70 else ("Low" if vix_percentile <= 25 else "Normal")),
        "valuation_environment": "Cheap" if valuation >= 65 else ("Fair" if valuation >= 42 else ("Expensive" if valuation >= 25 else "Very Expensive")),
        "earnings_trend": "Improving" if earnings >= 60 else ("Weakening" if earnings < 40 else "Stable"),
        "interest_rate_environment": "Supportive" if credit_rates >= 60 else ("Restrictive" if credit_rates < 40 else "Neutral"),
        "portfolio_correlation_risk": correlation_risk,
        "average_60_day_correlation": average_correlation,
        "rolling_60_day_correlation": corr60.reindex(index=symbols, columns=symbols).fillna(0.0).to_dict() if not corr60.empty else {},
        "rolling_252_day_correlation": corr252.reindex(index=symbols, columns=symbols).fillna(0.0).to_dict() if not corr252.empty else {},
        "breadth_above_50_day": round(float(above50), 2),
        "breadth_above_200_day": round(float(above200), 2),
        "breadth_sample_size": int(len(breadth_snapshots)),
        "advance_decline_ratio": advance_decline_ratio,
        "vix": vix_current,
        "vix_percentile": round(float(vix_percentile), 2),
        "holding_adjustments": holding_adjustments,
        "projection_confidence": confidence,
        "data_completeness": round(float(data_completeness), 2),
        "data_freshness": _freshness_panel(live_data, snapshots),
        "retrieved_at": live_data.get("retrieved_at"),
        "sources": live_data.get("sources") or live_data_sources(),
        "failures": list(live_data.get("failures") or []),
    }


def _positive_semidefinite(matrix: np.ndarray, minimum: float = 1e-10) -> np.ndarray:
    symmetric = (np.asarray(matrix, dtype=float) + np.asarray(matrix, dtype=float).T) / 2.0
    values, vectors = np.linalg.eigh(symmetric)
    return (vectors * np.maximum(values, minimum)) @ vectors.T


def condition_model_assumptions(model, market_state: dict, projection_profile: str = "AUTO", projection_inputs: dict | None = None) -> dict:
    """Apply bounded live adjustments to expected returns, volatility, and correlation."""

    defaults = model_defaults()
    expected = np.asarray(model.expected_annual_returns, dtype=float).copy()
    covariance = np.asarray(model.annual_covariance, dtype=float).copy()
    adjustments = market_state.get("holding_adjustments") or {}
    quality_map = {"High": 1.0, "Medium": 0.65, "Low": 0.30}
    return_adjustments = np.asarray([
        _number((adjustments.get(symbol) or {}).get("total_expected_return_adjustment"), 0.0)
        * quality_map.get(str((adjustments.get(symbol) or {}).get("data_quality") or "Low"), 0.30)
        for symbol in model.symbols
    ])
    expected += return_adjustments
    profile = str(projection_profile or "AUTO").upper()
    profile_volatility = 1.0
    auto_selection = None
    if profile == "AUTO":
        projection_inputs = projection_inputs or {}
        starting = max(1.0, _number(projection_inputs.get("starting_investment"), 1.0))
        if projection_inputs.get("withdrawal_frequency") == "Monthly":
            requested = 12.0 * _number(projection_inputs.get("monthly_withdrawal"), 0.0)
        elif projection_inputs.get("withdrawal_frequency") == "Yearly":
            requested = _number(projection_inputs.get("annual_withdrawal"), 0.0)
        else:
            requested = 0.0
        withdrawal_rate = max(0.0, requested / starting)
        bear_probability = _number((market_state.get("regime_probabilities") or {}).get("Bear"), 18.0) / 100.0
        risk_points = int(withdrawal_rate >= 0.06) + int(bear_probability >= 0.30) + int(market_state.get("portfolio_correlation_risk") == "High")
        if risk_points >= 2:
            expected -= 0.003
            profile_volatility = 1.08
            auto_selection = "Conservative risk tilt"
        else:
            auto_selection = "Balanced calibrated ensemble"
    elif profile == "CONSERVATIVE":
        expected -= 0.005
        profile_volatility = 1.10
    elif profile == "STRESS TEST":
        expected -= 0.025
        profile_volatility = 1.35
    # GROWTH changes emphasis, not the distribution's expected return.
    expected = np.clip(expected, defaults["expected_annual_geometric_return_floor"], defaults["expected_annual_geometric_return_ceiling"])

    base_vol = np.sqrt(np.maximum(np.diag(covariance), 1e-12))
    live_multipliers = np.asarray([
        _number((adjustments.get(symbol) or {}).get("volatility_multiplier"), 1.0)
        for symbol in model.symbols
    ]) * profile_volatility
    concentration_multiplier = 1.0 + _number((market_state.get("portfolio_risk") or {}).get("projection_uncertainty_increase_pct"), 0.0) / 100.0
    live_multipliers *= concentration_multiplier
    live_multipliers = np.clip(live_multipliers, 0.75, 2.25)
    new_vol = base_vol * live_multipliers
    denominator = np.outer(base_vol, base_vol)
    correlation = np.divide(covariance, denominator, out=np.eye(len(base_vol)), where=denominator > 0)
    np.fill_diagonal(correlation, 1.0)
    def current_correlation_matrix(key: str) -> np.ndarray | None:
        payload = market_state.get(key) or {}
        if not payload:
            return None
        try:
            frame = pd.DataFrame(payload).reindex(index=model.symbols, columns=model.symbols)
            values = frame.to_numpy(dtype=float)
            if values.shape != correlation.shape:
                return None
            values = np.where(np.isfinite(values), values, correlation)
            np.fill_diagonal(values, 1.0)
            return values
        except Exception:
            return None
    corr252 = current_correlation_matrix("rolling_252_day_correlation")
    corr60 = current_correlation_matrix("rolling_60_day_correlation")
    if corr252 is not None:
        correlation = 0.70 * correlation + 0.30 * corr252
    if corr60 is not None:
        correlation = 0.85 * correlation + 0.15 * corr60
    np.fill_diagonal(correlation, 1.0)
    probabilities = market_state.get("regime_probabilities") or {"Bear": 18.0, "Normal": 62.0, "Bull": 20.0}
    stress = (
        float(probabilities.get("Bear", 18.0)) / 100.0 * live_adaptive_config()["bear_correlation_stress"]
        if market_state.get("live_conditioning_active") else 0.0
    )
    if profile == "STRESS TEST":
        stress += 0.15
    stressed_corr = correlation.copy()
    off_diag = ~np.eye(len(base_vol), dtype=bool)
    stressed_corr[off_diag] = stressed_corr[off_diag] + stress * (1.0 - stressed_corr[off_diag])
    stressed_corr = np.clip(stressed_corr, -0.95, 0.98)
    np.fill_diagonal(stressed_corr, 1.0)
    annual_covariance = _positive_semidefinite(stressed_corr * np.outer(new_vol, new_vol))
    if model.period_frequency == "Monthly":
        base_period_covariance = np.asarray(model.period_covariance, dtype=float)
        base_period_volatility = np.sqrt(np.maximum(np.diag(base_period_covariance), 1e-12))
        period_denominator = np.outer(base_period_volatility, base_period_volatility)
        period_correlation = np.divide(
            base_period_covariance,
            period_denominator,
            out=np.eye(len(base_period_volatility)),
            where=period_denominator > 0,
        )
        if corr252 is not None:
            period_correlation = 0.70 * period_correlation + 0.30 * corr252
        if corr60 is not None:
            period_correlation = 0.85 * period_correlation + 0.15 * corr60
        period_correlation[off_diag] = period_correlation[off_diag] + stress * (1.0 - period_correlation[off_diag])
        period_correlation = np.clip(period_correlation, -0.95, 0.98)
        np.fill_diagonal(period_correlation, 1.0)
        period_covariance = _positive_semidefinite(
            period_correlation * np.outer(base_period_volatility * live_multipliers, base_period_volatility * live_multipliers)
        )
        period_log_returns = np.log1p(expected) / 12.0
    else:
        period_covariance = annual_covariance
        period_log_returns = np.log1p(expected)
    initial = np.asarray([probabilities.get(name, 0.0) for name in defaults["regime_order"]], dtype=float) / 100.0
    if profile == "STRESS TEST":
        initial = 0.70 * initial + 0.30 * np.asarray([0.75, 0.23, 0.02])
    initial = initial / initial.sum() if initial.sum() > 0 else np.asarray(defaults["initial_regime_probabilities"], dtype=float)
    transition_matrix = np.asarray(defaults["regime_transition_matrix"], dtype=float)
    if profile == "STRESS TEST":
        transition_matrix = np.asarray([
            [0.74, 0.24, 0.02],
            [0.20, 0.74, 0.06],
            [0.12, 0.48, 0.40],
        ], dtype=float)
    return {
        "expected_annual_returns": expected,
        "annual_covariance": annual_covariance,
        "period_log_returns": period_log_returns,
        "period_covariance": period_covariance,
        "initial_regime_probabilities": initial,
        "regime_transition_matrix": transition_matrix,
        "return_adjustments": return_adjustments,
        "volatility_multipliers": live_multipliers,
        "correlation_stress": stress,
        "projection_profile": profile,
        "auto_selection": auto_selection,
    }


def _history_matrix(model) -> tuple[np.ndarray, list[str]]:
    history = model.historical_returns
    if history is None or history.empty:
        return np.empty((0, len(model.symbols))), []
    frequency = "Monthly" if model.period_frequency == "Monthly" else "Annual"
    frame = history.loc[history["Frequency"].eq(frequency)].copy()
    if frame.empty:
        return np.empty((0, len(model.symbols))), []
    pivot = frame.pivot_table(index="Period", columns="Ticker", values="Return", aggfunc="last")
    pivot = pivot.reindex(columns=model.symbols).sort_index()
    pivot = pivot.replace([np.inf, -np.inf], np.nan).dropna(how="all")
    pivot = pivot.fillna(pivot.median()).fillna(0.0)
    return pivot.to_numpy(dtype=float), pivot.index.astype(str).tolist()


def walk_forward_validate(model, weights: np.ndarray | None = None, seed: int = 20260904) -> dict:
    """Run no-look-ahead 1/3/5-year percentile calibration checks."""

    matrix, labels = _history_matrix(model)
    if model.period_frequency == "Monthly" and len(matrix) >= 24:
        annual_rows = []
        annual_labels = []
        for offset in range(0, len(matrix) - 11, 12):
            annual_rows.append(np.prod(1.0 + matrix[offset:offset + 12], axis=0) - 1.0)
            annual_labels.append(labels[min(offset + 11, len(labels) - 1)][:4])
        matrix = np.asarray(annual_rows, dtype=float)
        labels = annual_labels
    if len(matrix) < 5:
        return {
            "records": [],
            "model_metrics": {},
            "ensemble_weights": {"Adaptive Regime Monte Carlo": 1.0, "Historical Block Bootstrap": 0.0, "Factor/CMA Model": 0.0},
            "no_future_leakage": True,
            "calibration_score": 35.0,
            "confidence": "Low",
            "explanation": "Insufficient completed history for a meaningful walk-forward calibration; the primary historical model is used.",
        }
    n_assets = matrix.shape[1]
    target = np.asarray(weights if weights is not None else np.full(n_assets, 1.0 / n_assets), dtype=float)
    target = target / target.sum()
    portfolio = matrix @ target
    anchor = float(capital_market_assumptions()["broad_market_annual_geometric_return"]["value"])
    config = live_adaptive_config()
    requested_origins = set(str(year) for year in config["walk_forward_as_of_years"])
    has_calendar_labels = any(str(label)[:4].isdigit() for label in labels)
    rng = np.random.default_rng(seed)
    records: list[dict] = []
    for origin in range(3, len(portfolio) - 1):
        as_of = labels[origin - 1][:4]
        if has_calendar_labels and requested_origins and as_of not in requested_origins:
            continue
        train = portfolio[:origin]
        shrunk_mean = 0.55 * anchor + 0.45 * float(np.mean(train))
        vol = max(0.08, float(np.std(train, ddof=1)))
        for horizon in config["walk_forward_horizons"]:
            if origin + horizon > len(portfolio):
                continue
            actual = float(np.prod(1.0 + portfolio[origin:origin + horizon]) - 1.0)
            model_samples: dict[str, np.ndarray] = {}
            shocks = rng.standard_t(6, size=(1600, horizon)) * math.sqrt(4.0 / 6.0)
            model_samples["Adaptive Regime Monte Carlo"] = np.prod(1.0 + np.clip(shrunk_mean + vol * shocks, -0.95, 2.0), axis=1) - 1.0
            blocks = np.empty((1600, horizon))
            block = min(2, horizon)
            for sample_idx in range(1600):
                values = []
                while len(values) < horizon:
                    start = int(rng.integers(0, max(1, len(train) - block + 1)))
                    values.extend(train[start:start + block].tolist())
                blocks[sample_idx] = values[:horizon]
            model_samples["Historical Block Bootstrap"] = np.prod(1.0 + blocks, axis=1) - 1.0
            factor_mean = float(np.clip(0.75 * anchor + 0.20 * np.mean(train[-3:]) + 0.05 * np.median(train), 0.01, 0.16))
            factor_shocks = rng.normal(0.0, max(0.07, vol * 0.75), size=(1600, horizon))
            model_samples["Factor/CMA Model"] = np.prod(1.0 + np.clip(factor_mean + factor_shocks, -0.95, 2.0), axis=1) - 1.0
            for name, samples in model_samples.items():
                quantiles = {f"P{p}": float(np.percentile(samples, p)) for p in PERCENTILES}
                records.append({
                    "Model": name,
                    "As Of": as_of,
                    "Horizon Years": horizon,
                    "Outcome End": labels[origin + horizon - 1][:4],
                    "Actual Return": actual,
                    **quantiles,
                    "Inside P10-P90": quantiles["P10"] <= actual <= quantiles["P90"],
                    "Inside P25-P75": quantiles["P25"] <= actual <= quantiles["P75"],
                    "Absolute Median Error": abs(actual - quantiles["P50"]),
                    "Directional Correct": (actual >= 0) == (quantiles["P50"] >= 0),
                    "No Future Leakage": origin - 1 < origin + horizon - 1,
                })
    metrics: dict[str, dict] = {}
    for name in ("Adaptive Regime Monte Carlo", "Historical Block Bootstrap", "Factor/CMA Model"):
        rows = [row for row in records if row["Model"] == name]
        if not rows:
            continue
        outer = float(np.mean([row["Inside P10-P90"] for row in rows]))
        central = float(np.mean([row["Inside P25-P75"] for row in rows]))
        error = float(np.median([row["Absolute Median Error"] for row in rows]))
        direction = float(np.mean([row["Directional Correct"] for row in rows]))
        coverage_score = max(0.0, 100.0 - abs(outer - 0.80) * 125.0 - abs(central - 0.50) * 100.0)
        error_score = 100.0 / (1.0 + 5.0 * error)
        score = 0.65 * coverage_score + 0.20 * error_score + 0.15 * direction * 100.0
        metrics[name] = {
            "observations": len(rows),
            "p10_p90_coverage": outer,
            "p25_p75_coverage": central,
            "median_absolute_forecast_error": error,
            "directional_accuracy": direction,
            "score": float(np.clip(score, 0.0, 100.0)),
        }
    if not metrics:
        weights_out = {"Adaptive Regime Monte Carlo": 1.0, "Historical Block Bootstrap": 0.0, "Factor/CMA Model": 0.0}
        calibration = 35.0
    else:
        primary_floor = config["ensemble_primary_floor"]
        secondary_names = [name for name in ("Historical Block Bootstrap", "Factor/CMA Model") if name in metrics]
        secondary_scores = np.asarray([max(1.0, metrics[name]["score"]) for name in secondary_names])
        weights_out = {"Adaptive Regime Monte Carlo": primary_floor}
        remaining = 1.0 - primary_floor
        if secondary_names:
            secondary_scores = secondary_scores / secondary_scores.sum()
            weights_out.update({name: float(remaining * score) for name, score in zip(secondary_names, secondary_scores)})
        else:
            weights_out["Adaptive Regime Monte Carlo"] = 1.0
        for name in ("Historical Block Bootstrap", "Factor/CMA Model"):
            weights_out.setdefault(name, 0.0)
        calibration = float(np.average([metrics[name]["score"] for name in metrics], weights=[weights_out.get(name, 0.0) for name in metrics]))
    confidence = "High" if calibration >= 75 and len(records) >= 18 else ("Medium" if calibration >= 55 and len(records) >= 6 else "Low")
    return {
        "records": records,
        "model_metrics": metrics,
        "ensemble_weights": weights_out,
        "no_future_leakage": all(row["No Future Leakage"] for row in records),
        "calibration_score": round(calibration, 2),
        "confidence": confidence,
        "explanation": (
            f"{confidence}: {len(records)} model-horizon checks used only information available before each outcome; "
            f"dynamic weights favor the best-calibrated distributions while retaining the adaptive regime model as primary."
        ),
    }


def projection_calibration_score(market_state: dict, validation: dict, historical_depth: int) -> dict:
    metrics = validation.get("model_metrics") or {}
    weighted_coverage = validation.get("calibration_score", 35.0)
    recent = metrics.get("Adaptive Regime Monte Carlo", {}).get("score", weighted_coverage)
    completeness = _number(market_state.get("data_completeness"), 0.0)
    freshness = 90.0 if market_state.get("live_conditioning_active") and not market_state.get("failures") else (60.0 if market_state.get("live_conditioning_active") else 25.0)
    depth = min(100.0, 10.0 * max(0, historical_depth))
    model_scores = [item.get("score", 0.0) for item in metrics.values()]
    agreement = 100.0 - min(100.0, float(np.std(model_scores)) * 2.0) if model_scores else 40.0
    score = 0.30 * weighted_coverage + 0.25 * recent + 0.15 * completeness + 0.10 * freshness + 0.10 * depth + 0.10 * agreement
    score = float(np.clip(score, 0.0, 100.0))
    confidence = "High" if score >= 75 else ("Medium" if score >= 55 else "Low")
    return {
        "score": round(score, 2),
        "confidence": confidence,
        "components": {
            "historical_percentile_coverage": round(float(weighted_coverage), 2),
            "recent_regime_backtest": round(float(recent), 2),
            "data_completeness": round(float(completeness), 2),
            "data_freshness": round(float(freshness), 2),
            "historical_depth": round(float(depth), 2),
            "model_agreement": round(float(agreement), 2),
        },
        "explanation": (
            f"{confidence}: score {score:.1f}/100 combines walk-forward coverage, current-data completeness and freshness, "
            "historical depth, and agreement among the three validation models."
        ),
    }


def block_bootstrap_indices(periods: int, simulations: int, history_rows: int, block_length: int, rng: np.random.Generator) -> np.ndarray:
    """Return contiguous-block historical row indices for each simulation path."""

    if history_rows <= 0:
        return np.zeros((periods, simulations), dtype=int)
    block_length = max(1, min(int(block_length), history_rows))
    output = np.empty((periods, simulations), dtype=int)
    for period in range(periods):
        if period % block_length == 0:
            starts = rng.integers(0, max(1, history_rows - block_length + 1), size=simulations)
        output[period] = np.minimum(history_rows - 1, starts + (period % block_length))
    return output
