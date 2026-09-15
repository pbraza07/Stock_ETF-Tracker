from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List
from urllib.parse import urlparse, quote
import time

import numpy as np
import pandas as pd
import yfinance as yf

from .base import MarketDataProvider


class YahooFinanceProvider(MarketDataProvider):
    """Yahoo Finance data via the open-source yfinance client (no API key)."""

    name = "Yahoo Finance (via yfinance)"

    @staticmethod
    def _clean_symbols(symbols: Iterable[str]) -> List[str]:
        return list(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))

    def download_daily_history(self, symbols: Iterable[str], period: str = "max") -> Dict[str, pd.DataFrame]:
        symbols = self._clean_symbols(symbols)
        if not symbols:
            return {}
        try:
            raw = yf.download(
                tickers=symbols,
                period=period,
                interval="1d",
                auto_adjust=True,
                actions=False,
                repair=False,
                group_by="column",
                threads=True,
                progress=False,
                timeout=20,
            )
        except Exception:
            return {}

        result: Dict[str, pd.DataFrame] = {}
        if raw is None or raw.empty:
            return result

        if len(symbols) == 1:
            symbol = symbols[0]
            frame = raw.copy()
            if isinstance(frame.columns, pd.MultiIndex):
                try:
                    frame = frame.xs(symbol, axis=1, level=1, drop_level=True).copy()
                except Exception:
                    pass
            frame.columns = [str(c) for c in frame.columns]
            result[symbol] = frame.dropna(how="all")
            return result

        if isinstance(raw.columns, pd.MultiIndex):
            top = set(map(str, raw.columns.get_level_values(0)))
            for symbol in symbols:
                try:
                    if "Close" in top:
                        frame = raw.xs(symbol, axis=1, level=1, drop_level=True).copy()
                    else:
                        frame = raw.xs(symbol, axis=1, level=0, drop_level=True).copy()
                    frame.columns = [str(c) for c in frame.columns]
                    result[symbol] = frame.dropna(how="all")
                except (KeyError, ValueError):
                    continue
        return result

    def download_daily_history_since(
        self,
        symbols: Iterable[str],
        start: str = "2000-01-01",
        chunk_size: int = 20,
    ) -> Dict[str, pd.DataFrame]:
        """Download long adjusted daily history from an explicit calendar start.

        MarketScope's dynamically growing completed annual-return window needs the prior-year anchor
        for the oldest displayed year. During 2026 that means daily history must
        reach back through calendar 2000 in order to calculate a genuine 2001
        return. Using an explicit start date is more deterministic than relying on
        a provider-specific ``period=max`` response for large multi-ticker batches.

        Requests are intentionally split into small chunks. Any symbols omitted by
        the bulk response are retried one-at-a-time with ``Ticker.history``. No
        synthetic annual values are created when Yahoo lacks genuine price history.
        """
        symbols = self._clean_symbols(symbols)
        if not symbols:
            return {}

        result: Dict[str, pd.DataFrame] = {}
        chunk_size = max(1, int(chunk_size or 20))

        for offset in range(0, len(symbols), chunk_size):
            batch = symbols[offset:offset + chunk_size]
            try:
                raw = yf.download(
                    tickers=batch,
                    start=start,
                    interval="1d",
                    auto_adjust=True,
                    actions=False,
                    repair=False,
                    group_by="column",
                    threads=True,
                    progress=False,
                    timeout=30,
                )
            except Exception:
                raw = pd.DataFrame()

            if raw is not None and not raw.empty:
                if len(batch) == 1:
                    symbol = batch[0]
                    frame = raw.copy()
                    if isinstance(frame.columns, pd.MultiIndex):
                        try:
                            frame = frame.xs(symbol, axis=1, level=1, drop_level=True).copy()
                        except Exception:
                            try:
                                frame.columns = frame.columns.get_level_values(0)
                            except Exception:
                                pass
                    frame.columns = [str(c) for c in frame.columns]
                    frame = frame.dropna(how="all")
                    if not frame.empty:
                        result[symbol] = frame
                elif isinstance(raw.columns, pd.MultiIndex):
                    top = set(map(str, raw.columns.get_level_values(0)))
                    for symbol in batch:
                        try:
                            if "Close" in top:
                                frame = raw.xs(symbol, axis=1, level=1, drop_level=True).copy()
                            else:
                                frame = raw.xs(symbol, axis=1, level=0, drop_level=True).copy()
                            frame.columns = [str(c) for c in frame.columns]
                            frame = frame.dropna(how="all")
                            if not frame.empty:
                                result[symbol] = frame
                        except (KeyError, ValueError):
                            continue

            # Yahoo occasionally omits one symbol from an otherwise successful
            # multi-ticker response. Retry only those missing symbols individually.
            for symbol in batch:
                if symbol in result and not result[symbol].empty:
                    continue
                try:
                    frame = yf.Ticker(symbol).history(
                        start=start,
                        interval="1d",
                        auto_adjust=True,
                        actions=False,
                        repair=False,
                    )
                except Exception:
                    frame = pd.DataFrame()
                if frame is None or frame.empty:
                    continue
                frame = frame.copy()
                if isinstance(frame.columns, pd.MultiIndex):
                    try:
                        frame.columns = frame.columns.get_level_values(0)
                    except Exception:
                        pass
                frame.columns = [str(c) for c in frame.columns]
                frame = frame.dropna(how="all")
                if not frame.empty:
                    result[symbol] = frame

        return result

    def download_live_prices(self, symbols: Iterable[str]) -> Dict[str, float]:
        symbols = self._clean_symbols(symbols)
        if not symbols:
            return {}

        # Use small batches so a single large Yahoo response is less likely to fail.
        prices: Dict[str, float] = {}
        batch_size = 100
        for start in range(0, len(symbols), batch_size):
            batch = symbols[start:start + batch_size]
            for interval in ("1m", "5m"):
                try:
                    raw = yf.download(
                        tickers=batch,
                        period="1d",
                        interval=interval,
                        auto_adjust=True,
                        actions=False,
                        repair=False,
                        group_by="column",
                        threads=True,
                        prepost=False,
                        progress=False,
                        timeout=12,
                    )
                except Exception:
                    raw = pd.DataFrame()
                if raw is None or raw.empty:
                    continue
                if len(batch) == 1:
                    close = raw.get("Close")
                    if isinstance(close, pd.DataFrame):
                        close = close.iloc[:, 0]
                    if close is not None:
                        close = close.dropna()
                        if len(close):
                            prices[batch[0]] = float(close.iloc[-1])
                elif isinstance(raw.columns, pd.MultiIndex):
                    try:
                        close = raw["Close"]
                        for symbol in batch:
                            if symbol in close.columns:
                                series = close[symbol].dropna()
                                if len(series):
                                    prices[symbol] = float(series.iloc[-1])
                    except Exception:
                        pass
                if all(s in prices for s in batch):
                    break
        return prices

    def download_intraday_history(
        self,
        symbol: str,
        period: str = "1d",
        interval: str = "1m",
        prepost: bool = False,
    ) -> pd.DataFrame:
        """Download a single-symbol Yahoo intraday series for the live chart.

        Yahoo intraday availability/delay varies by exchange. This method is
        intentionally single-symbol and is called only for an opened card so
        the main dashboard never performs hundreds of intraday requests.
        """
        symbol = str(symbol).strip().upper()
        if not symbol:
            return pd.DataFrame()
        try:
            raw = yf.download(
                tickers=symbol,
                period=period,
                interval=interval,
                auto_adjust=True,
                actions=False,
                repair=False,
                group_by="column",
                threads=False,
                prepost=prepost,
                progress=False,
                timeout=12,
            )
        except Exception:
            return pd.DataFrame()
        if raw is None or raw.empty:
            return pd.DataFrame()
        frame = raw.copy()
        if isinstance(frame.columns, pd.MultiIndex):
            try:
                frame = frame.xs(symbol, axis=1, level=1, drop_level=True).copy()
            except Exception:
                try:
                    frame.columns = frame.columns.get_level_values(0)
                except Exception:
                    pass
        frame.columns = [str(c) for c in frame.columns]
        return frame.dropna(how="all")

    def download_chart_history(self, symbol: str, chart_period: str) -> pd.DataFrame:
        if str(chart_period).upper() == "MAX":
            result = self.download_daily_history_since([symbol], start="2000-01-01", chunk_size=1)
            return result.get(str(symbol).upper(), pd.DataFrame())
        period_map = {"1M": "1mo", "6M": "6mo", "1Y": "1y", "5Y": "5y"}
        period = period_map.get(chart_period, "1y")
        result = self.download_daily_history([symbol], period=period)
        return result.get(str(symbol).upper(), pd.DataFrame())

    def get_metadata(self, symbol: str) -> dict:
        symbol = str(symbol).strip().upper()
        if not symbol:
            return {}
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.get_info() or {}
        except Exception:
            ticker = None
            info = {}

        quote_type = str(info.get("quoteType") or "").upper()
        is_fund = quote_type in {"ETF", "MUTUALFUND"}
        name = info.get("longName") or info.get("shortName") or info.get("displayName") or symbol
        sector = info.get("sector") or (info.get("category") if is_fund else "Unknown") or "Unknown"
        industry = info.get("industry") or ("ETF / Fund" if is_fund else "Unknown")

        target_low = info.get("targetLowPrice")
        target_mean = info.get("targetMeanPrice")
        target_high = info.get("targetHighPrice")
        target_median = info.get("targetMedianPrice")
        analyst_opinions = info.get("numberOfAnalystOpinions")
        if not is_fund and ticker is not None and not any(
            value is not None for value in (target_low, target_mean, target_high)
        ):
            try:
                targets = ticker.analyst_price_targets or {}
            except Exception:
                targets = {}
            if isinstance(targets, dict):
                target_low = targets.get("low", target_low)
                target_mean = targets.get("mean", target_mean)
                target_high = targets.get("high", target_high)
                target_median = targets.get("median", target_median)

        website = str(info.get("website") or "").strip()
        logo_url = str(info.get("logoUrl") or info.get("logo_url") or "").strip()
        if not logo_url and website:
            try:
                host = (urlparse(website).hostname or "").strip().lower()
            except Exception:
                host = ""
            if host:
                # Yahoo supplies the issuer website metadata; Google favicon is a lightweight
                # display fallback when Yahoo itself does not expose a dedicated logo URL.
                logo_url = f"https://www.google.com/s2/favicons?domain={quote(host)}&sz=128"

        return {
            "symbol": symbol,
            "name": name,
            "sector": sector,
            "industry": industry,
            "quote_type": quote_type or "UNKNOWN",
            "exchange": info.get("fullExchangeName") or info.get("exchange") or "Unknown",
            "website": website,
            "logo_url": logo_url,
            "currency": info.get("currency") or "USD",
            "exchange_delay_minutes": info.get("exchangeDataDelayedBy"),
            "market_state": info.get("marketState") or "Unknown",
            "nav_price": info.get("navPrice"),
            "ytd_fund_return": info.get("ytdReturn"),
            "three_year_fund_return": info.get("threeYearAverageReturn"),
            "five_year_fund_return": info.get("fiveYearAverageReturn"),
            "target_low_price": target_low,
            "target_mean_price": target_mean,
            "target_high_price": target_high,
            "target_median_price": target_median,
            "analyst_opinions": analyst_opinions,
        }

    def get_logo_url(self, symbol: str) -> str:
        """Return a selected instrument logo URL without making the dashboard depend on it.

        Yahoo/yfinance metadata is the primary source. Some Yahoo quote payloads expose
        a logoUrl directly; otherwise the issuer website from Yahoo metadata is converted
        to a small favicon URL. The UI always has a ticker-initial fallback.
        """
        symbol = str(symbol).strip().upper()
        if not symbol:
            return ""
        try:
            search_quotes = yf.Search(symbol, max_results=4, news_count=0, enable_fuzzy_query=False).quotes or []
        except Exception:
            search_quotes = []
        for item in search_quotes:
            if str(item.get("symbol") or "").strip().upper() != symbol:
                continue
            direct = str(item.get("logoUrl") or item.get("logo_url") or "").strip()
            if direct.startswith(("https://", "http://")):
                return direct
        meta = self.get_metadata(symbol)
        resolved = str(meta.get("logo_url") or "").strip()
        if resolved.startswith(("https://", "http://")):
            return resolved

        # Final ticker-addressable image fallback. The UI includes an onerror
        # initials fallback, so a missing asset never produces a broken card.
        # This avoids losing every logo when Yahoo metadata is temporarily
        # rate-limited while still preferring Yahoo/issuer metadata first.
        return f"https://financialmodelingprep.com/image-stock/{quote(symbol)}.png"

    def get_logo_urls_many(self, symbols: Iterable[str], max_workers: int = 6) -> Dict[str, str]:
        symbols = self._clean_symbols(symbols)
        output: Dict[str, str] = {}
        if not symbols:
            return output
        with ThreadPoolExecutor(max_workers=min(max_workers, len(symbols))) as pool:
            futures = {pool.submit(self.get_logo_url, symbol): symbol for symbol in symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    url = str(future.result() or "").strip()
                except Exception:
                    url = ""
                if not url.startswith(("https://", "http://")):
                    url = f"https://financialmodelingprep.com/image-stock/{quote(symbol)}.png"
                output[symbol] = url
        return output

    def get_price_targets(self, symbol: str) -> dict:
        """Return Yahoo analyst low/mean/high price targets for one stock.

        v5.9.66 deliberately keeps each Yahoo retrieval path independent. A failure
        in analyst_price_targets must never disable the get_info fallback.
        """
        symbol = str(symbol).strip().upper()
        if not symbol:
            return {}

        try:
            ticker = yf.Ticker(symbol)
        except Exception:
            ticker = None
        if ticker is None:
            return {}

        def unpack(value):
            # Yahoo/yfinance can expose plain numbers or nested raw/fmt payloads.
            if isinstance(value, dict):
                for key in ("raw", "value", "fmt"):
                    if key in value:
                        candidate = unpack(value.get(key))
                        if candidate is not None:
                            return candidate
                return None
            try:
                number = float(value)
            except (TypeError, ValueError):
                return None
            return number if pd.notna(number) and number > 0 else None

        resolved = {"low": None, "mean": None, "high": None, "median": None}

        def merge(payload):
            if payload is None:
                return
            # Current yfinance API returns a dict with keys:
            # current, low, high, mean, median.
            if isinstance(payload, dict):
                aliases = {
                    "low": ("low", "targetLowPrice", "lowTarget"),
                    "mean": ("mean", "targetMeanPrice", "average", "avg"),
                    "high": ("high", "targetHighPrice", "highTarget"),
                    "median": ("median", "targetMedianPrice"),
                }
                for target_key, keys in aliases.items():
                    if resolved[target_key] is not None:
                        continue
                    for key in keys:
                        if key in payload:
                            value = unpack(payload.get(key))
                            if value is not None:
                                resolved[target_key] = value
                                break
                return

            # Defensive compatibility for Series/DataFrame-shaped responses.
            try:
                if hasattr(payload, "to_dict"):
                    converted = payload.to_dict()
                    if isinstance(converted, dict):
                        # DataFrames can become nested column dictionaries.
                        flat = {}
                        for key, value in converted.items():
                            if isinstance(value, dict) and len(value) == 1:
                                value = next(iter(value.values()))
                            flat[key] = value
                        merge(flat)
            except Exception:
                pass

        # Current public yfinance method. Keep this first because it is narrower
        # and cheaper than full quote-summary info.
        try:
            merge(ticker.get_analyst_price_targets())
        except Exception:
            pass

        # Property fallback for yfinance releases where the method/property paths
        # differ internally.
        if not all(resolved[key] is not None for key in ("low", "mean", "high")):
            try:
                merge(ticker.analyst_price_targets)
            except Exception:
                pass

        # Full Yahoo financialData fallback. Critically, this still runs even when
        # either analyst-target endpoint above threw an exception.
        if not all(resolved[key] is not None for key in ("low", "mean", "high")):
            try:
                info = ticker.get_info() or {}
            except Exception:
                info = {}
            merge(info)

        result = {
            "low": resolved["low"],
            "mean": resolved["mean"],
            "high": resolved["high"],
            "median": resolved["median"],
            "source": "Yahoo Finance analyst consensus",
        }
        return result if any(result[k] is not None for k in ("low", "mean", "high")) else {}


    def get_price_targets_many(self, symbols: Iterable[str], max_workers: int = 4) -> Dict[str, dict]:
        """Fetch analyst target ranges with a low-concurrency pass plus individual retry.

        Render/Yahoo can intermittently omit quote-summary modules when several
        metadata calls run concurrently. A missing symbol is retried once
        sequentially so valid Low / Mean / High targets are much less likely to
        disappear from the durable snapshot or PDF enrichment path.
        """
        symbols = self._clean_symbols(symbols)
        output: Dict[str, dict] = {}
        if not symbols:
            return output
        workers = max(1, min(int(max_workers or 1), 4, len(symbols)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self.get_price_targets, symbol): symbol for symbol in symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    values = future.result()
                except Exception:
                    values = {}
                if values:
                    output[symbol] = values

        missing = [symbol for symbol in symbols if symbol not in output]
        for pass_no in range(2):
            if not missing:
                break
            next_missing = []
            for symbol in missing:
                try:
                    time.sleep(0.18 + 0.12 * pass_no)
                    values = self.get_price_targets(symbol)
                except Exception:
                    values = {}
                if values:
                    output[symbol] = values
                else:
                    next_missing.append(symbol)
            missing = next_missing
        return output


    def get_income_metrics(self, symbol: str) -> dict:
        """Return a trailing/regular cash yield estimate for one stock or ETF.

        The preferred calculation is trailing annual dividend/distribution rate
        divided by current price. If Yahoo does not expose a usable rate, the
        method falls back to the last 365 days of cash dividends/distributions.
        Values are descriptive trailing estimates, not forecasts.
        """
        symbol = str(symbol).strip().upper()
        if not symbol:
            return {}
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.get_info() or {}
        except Exception:
            ticker = None
            info = {}

        def clean_number(value):
            try:
                number = float(value)
                return number if pd.notna(number) else None
            except (TypeError, ValueError):
                return None

        price = clean_number(
            info.get("regularMarketPrice")
            or info.get("currentPrice")
            or info.get("previousClose")
            or info.get("navPrice")
        )
        annual_rate = clean_number(
            info.get("trailingAnnualDividendRate")
            or info.get("dividendRate")
        )
        yield_pct = None
        source = ""

        if annual_rate is not None and annual_rate >= 0 and price is not None and price > 0:
            yield_pct = (annual_rate / price) * 100.0
            source = "Yahoo trailing annual dividend/distribution rate"

        if yield_pct is None and ticker is not None:
            try:
                dividends = ticker.dividends
                if dividends is not None and len(dividends):
                    divs = pd.to_numeric(dividends, errors="coerce").dropna()
                    if len(divs):
                        idx = pd.to_datetime(divs.index)
                        try:
                            now = pd.Timestamp.now(tz=idx.tz) if idx.tz is not None else pd.Timestamp.now()
                        except Exception:
                            now = pd.Timestamp.now()
                        cutoff = now - pd.Timedelta(days=365)
                        trailing = float(divs.loc[idx >= cutoff].sum())
                        if trailing >= 0:
                            annual_rate = trailing
                            if price is None or price <= 0:
                                try:
                                    price = clean_number(ticker.fast_info.get("last_price"))
                                except Exception:
                                    price = None
                            if price is not None and price > 0:
                                yield_pct = (trailing / price) * 100.0
                                source = "Yahoo trailing 365-day cash dividends/distributions"
            except Exception:
                pass

        if yield_pct is None:
            raw_yield = clean_number(
                info.get("trailingAnnualDividendYield")
                or info.get("dividendYield")
                or info.get("yield")
            )
            if raw_yield is not None and raw_yield >= 0:
                # Yahoo fields can be represented as either a fraction or a percent.
                # Small values are conventionally fractions (0.012 = 1.2%).
                yield_pct = raw_yield * 100.0 if raw_yield <= 0.20 else raw_yield
                source = "Yahoo trailing dividend/distribution yield"

        if yield_pct is None or not pd.notna(yield_pct) or yield_pct < 0 or yield_pct > 100:
            return {}
        return {
            "regular_yield_pct": float(yield_pct),
            "trailing_annual_rate": float(annual_rate) if annual_rate is not None and annual_rate >= 0 else None,
            "price": float(price) if price is not None and price > 0 else None,
            "source": source or "Yahoo Finance",
        }

    def get_income_metrics_many(self, symbols: Iterable[str], max_workers: int = 6) -> Dict[str, dict]:
        symbols = self._clean_symbols(symbols)
        output: Dict[str, dict] = {}
        if not symbols:
            return output
        with ThreadPoolExecutor(max_workers=min(max_workers, len(symbols))) as pool:
            futures = {pool.submit(self.get_income_metrics, symbol): symbol for symbol in symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    values = future.result()
                except Exception:
                    values = {}
                output[symbol] = values if isinstance(values, dict) else {}
        return output

    def get_top_holdings(self, symbol: str) -> List[dict]:
        """Return the ETF/mutual-fund top holdings from Yahoo Finance via yfinance.

        Yahoo's funds_data.top_holdings normally exposes up to 10 rows. MarketScope
        shows 10 when available; when Yahoo returns fewer than 10 but at least 5,
        the UI intentionally shows the top 5. If Yahoo exposes fewer than 5 rows,
        those available rows are returned rather than fabricating holdings.
        """
        symbol = str(symbol).strip().upper()
        if not symbol:
            return []
        try:
            ticker = yf.Ticker(symbol)
            funds = ticker.funds_data
            raw = funds.top_holdings
        except Exception:
            return []
        if raw is None:
            return []
        try:
            frame = raw.copy() if isinstance(raw, pd.DataFrame) else pd.DataFrame(raw)
        except Exception:
            return []
        if frame.empty:
            return []

        try:
            frame = frame.reset_index()
        except Exception:
            frame = frame.copy()

        def norm(value) -> str:
            return ''.join(ch for ch in str(value).lower() if ch.isalnum())

        normalized = {norm(col): col for col in frame.columns}

        def find_col(*keys):
            for key in keys:
                if key in normalized:
                    return normalized[key]
            for nkey, original in normalized.items():
                if any(key in nkey for key in keys):
                    return original
            return None

        symbol_col = find_col('symbol', 'ticker')
        name_col = find_col('name', 'holdingname', 'companyname')
        weight_col = find_col('holdingpercent', 'weight', 'percentassets', 'percentasset', 'assetspercent')

        # yfinance commonly stores the holding symbol in the DataFrame index.
        if symbol_col is None and len(frame.columns):
            first = frame.columns[0]
            if norm(first) in {'index', 'level0'}:
                symbol_col = first

        def clean_weight(value):
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return None
            try:
                if isinstance(value, str):
                    stripped = value.strip().replace(',', '')
                    if stripped.endswith('%'):
                        return float(stripped[:-1])
                    number = float(stripped)
                else:
                    number = float(value)
            except (TypeError, ValueError):
                return None
            if pd.isna(number):
                return None
            return number * 100.0 if abs(number) <= 1.0 else number

        rows: List[dict] = []
        for _, row in frame.iterrows():
            holding_symbol = str(row.get(symbol_col, '') if symbol_col is not None else '').strip().upper()
            holding_name = str(row.get(name_col, '') if name_col is not None else '').strip()
            weight_pct = clean_weight(row.get(weight_col)) if weight_col is not None else None
            if not holding_symbol and not holding_name:
                continue
            rows.append({
                'symbol': holding_symbol,
                'name': holding_name or holding_symbol,
                'weight_pct': weight_pct,
            })

        if len(rows) >= 10:
            limit = 10
        elif len(rows) >= 5:
            limit = 5
        else:
            limit = len(rows)
        return rows[:limit]

    def get_metadata_many(self, symbols: Iterable[str], max_workers: int = 8) -> Dict[str, dict]:
        symbols = self._clean_symbols(symbols)
        output: Dict[str, dict] = {}
        if not symbols:
            return output
        with ThreadPoolExecutor(max_workers=min(max_workers, len(symbols))) as pool:
            futures = {pool.submit(self.get_metadata, s): s for s in symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    output[symbol] = future.result()
                except Exception:
                    output[symbol] = {"symbol": symbol, "name": symbol, "sector": "Unknown", "industry": "Unknown"}
        return output

    def get_projection_fundamentals(self, symbol: str) -> dict:
        """Return auditable, bounded inputs for Future Projection conditioning.

        Missing Yahoo fields remain ``None``. The projection layer treats analyst
        data as a secondary signal and never converts a price target into a future
        stock price.
        """

        symbol = str(symbol).strip().upper()
        if not symbol:
            return {}
        retrieved_at = pd.Timestamp.utcnow().isoformat()
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.get_info() or {}
        except Exception:
            ticker = None
            info = {}

        def numeric(key):
            try:
                value = float(info.get(key))
            except (TypeError, ValueError):
                return None
            return value if pd.notna(value) else None

        quote_type = str(info.get("quoteType") or "UNKNOWN").upper()
        is_fund = quote_type in {"ETF", "MUTUALFUND"}
        revision_direction = None
        forward_eps_growth = None
        target_revision_direction = None
        if ticker is not None and not is_fund:
            try:
                revisions = ticker.get_eps_revisions()
                if isinstance(revisions, pd.DataFrame) and not revisions.empty:
                    numeric_values = revisions.select_dtypes(include="number")
                    if not numeric_values.empty:
                        recent = numeric_values.iloc[0].dropna().to_numpy(dtype=float)
                        if recent.size:
                            revision_direction = float(np.clip(np.nanmean(np.sign(recent)), -1.0, 1.0))
            except Exception:
                pass
            try:
                growth = ticker.get_growth_estimates()
                if isinstance(growth, pd.DataFrame) and not growth.empty:
                    candidates = growth.select_dtypes(include="number").to_numpy(dtype=float).ravel()
                    candidates = candidates[np.isfinite(candidates)]
                    if candidates.size:
                        forward_eps_growth = float(np.median(candidates))
            except Exception:
                pass
            try:
                targets = ticker.get_analyst_price_targets() or {}
                mean = float(targets.get("mean")) if targets.get("mean") is not None else None
                current = numeric("currentPrice") or numeric("regularMarketPrice")
                if mean is not None and current and current > 0:
                    # Bounded direction only; never a price forecast.
                    target_revision_direction = float(np.clip(mean / current - 1.0, -0.25, 0.25) / 0.25)
            except Exception:
                pass
        if revision_direction is None:
            revision_direction = target_revision_direction

        return {
            "symbol": symbol,
            "instrument_type": "ETF" if is_fund else "Stock",
            "quote_type": quote_type,
            "current_price": numeric("currentPrice") or numeric("regularMarketPrice") or numeric("previousClose") or numeric("navPrice"),
            "market_cap": numeric("marketCap"),
            "beta": numeric("beta"),
            "trailing_eps": numeric("trailingEps"),
            "forward_eps": numeric("forwardEps"),
            "trailing_pe": numeric("trailingPE"),
            "forward_pe": numeric("forwardPE"),
            "peg_ratio": numeric("pegRatio"),
            "price_to_sales": numeric("priceToSalesTrailing12Months"),
            "price_to_book": numeric("priceToBook"),
            "revenue_growth": numeric("revenueGrowth"),
            "earnings_growth": numeric("earningsGrowth"),
            "earnings_quarterly_growth": numeric("earningsQuarterlyGrowth"),
            "forward_eps_growth": forward_eps_growth,
            "operating_margin": numeric("operatingMargins"),
            "free_cash_flow": numeric("freeCashflow"),
            "debt_to_equity": numeric("debtToEquity"),
            "return_on_equity": numeric("returnOnEquity"),
            "eps_revision_direction": revision_direction,
            "analyst_target_direction": target_revision_direction,
            "sector": info.get("sector"),
            "category": info.get("category"),
            "source": "Yahoo Finance quote-summary and analyst datasets via yfinance",
            "retrieved_at": retrieved_at,
        }

    def get_projection_fundamentals_many(self, symbols: Iterable[str], max_workers: int = 4) -> Dict[str, dict]:
        symbols = self._clean_symbols(symbols)
        if not symbols:
            return {}
        output: Dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=max(1, min(int(max_workers or 1), len(symbols), 6))) as pool:
            futures = {pool.submit(self.get_projection_fundamentals, symbol): symbol for symbol in symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    output[symbol] = future.result() or {}
                except Exception:
                    output[symbol] = {}
        return output


    def get_recent_news(self, symbol: str, company_name: str = "", max_items: int = 8) -> List[dict]:
        """Return recent Yahoo Finance news normalized for on-demand card display.

        Search is used instead of blindly trusting a generic homepage feed. When
        Yahoo provides related tickers, items that do not include the requested
        symbol are discarded. The caller decides how to interpret directional
        impact; this method only retrieves and normalizes source metadata.
        """
        symbol = str(symbol).strip().upper()
        if not symbol:
            return []
        query = f"{symbol} {str(company_name).strip()}".strip()
        try:
            search = yf.Search(
                query,
                max_results=1,
                news_count=max(max_items * 3, 12),
                lists_count=0,
                include_cb=False,
                include_nav_links=False,
                include_research=False,
                enable_fuzzy_query=False,
                recommended=0,
            )
            raw_items = search.news or []
        except Exception:
            return []

        def nested_url(value):
            if isinstance(value, dict):
                return value.get("url") or value.get("href") or ""
            return value or ""

        output: List[dict] = []
        seen: set[str] = set()
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            content = raw.get("content") if isinstance(raw.get("content"), dict) else {}
            title = str(content.get("title") or raw.get("title") or "").strip()
            if not title:
                continue
            related = raw.get("relatedTickers") or content.get("relatedTickers") or []
            finance = content.get("finance") if isinstance(content.get("finance"), dict) else {}
            if not related:
                related = finance.get("stockTickers") or finance.get("tickers") or []
            normalized_related = {
                str(x.get("symbol") if isinstance(x, dict) else x).upper().strip()
                for x in (related or [])
                if x
            }
            if normalized_related and symbol not in normalized_related:
                continue

            provider_data = content.get("provider") if isinstance(content.get("provider"), dict) else {}
            publisher = str(
                provider_data.get("displayName")
                or provider_data.get("name")
                or raw.get("publisher")
                or raw.get("provider")
                or "Yahoo Finance feed"
            ).strip()
            summary = str(
                content.get("summary")
                or content.get("description")
                or raw.get("summary")
                or raw.get("description")
                or ""
            ).strip()
            link = nested_url(content.get("canonicalUrl")) or nested_url(content.get("clickThroughUrl")) or str(raw.get("link") or raw.get("url") or "")
            published = content.get("pubDate") or content.get("displayTime") or raw.get("providerPublishTime") or raw.get("publishedAt") or raw.get("pubDate")
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            output.append({
                "title": title,
                "summary": summary,
                "publisher": publisher,
                "published": published,
                "url": link,
                "related_tickers": sorted(normalized_related),
            })
            if len(output) >= max_items:
                break
        return output

    def search(self, query: str, max_results: int = 8) -> List[dict]:
        query = str(query).strip()
        if not query:
            return []
        try:
            quotes = yf.Search(query, max_results=max_results, news_count=0, enable_fuzzy_query=True).quotes
        except Exception:
            return []

        results: List[dict] = []
        for item in quotes or []:
            quote_type = str(item.get("quoteType") or "").upper()
            if quote_type not in {"EQUITY", "ETF", "MUTUALFUND"}:
                continue
            symbol = item.get("symbol")
            if not symbol:
                continue
            results.append({
                "symbol": str(symbol).upper(),
                "name": item.get("longname") or item.get("shortname") or item.get("name") or symbol,
                "exchange": item.get("exchDisp") or item.get("exchange") or "",
                "quote_type": quote_type,
            })
        return results[:max_results]
