from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List

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

    def download_chart_history(self, symbol: str, chart_period: str) -> pd.DataFrame:
        period_map = {"1M": "1mo", "6M": "6mo", "1Y": "1y", "5Y": "5y", "MAX": "max"}
        period = period_map.get(chart_period, "1y")
        result = self.download_daily_history([symbol], period=period)
        return result.get(str(symbol).upper(), pd.DataFrame())

    def get_metadata(self, symbol: str) -> dict:
        symbol = str(symbol).strip().upper()
        if not symbol:
            return {}
        try:
            info = yf.Ticker(symbol).get_info() or {}
        except Exception:
            info = {}

        quote_type = str(info.get("quoteType") or "").upper()
        is_fund = quote_type in {"ETF", "MUTUALFUND"}
        name = info.get("longName") or info.get("shortName") or info.get("displayName") or symbol
        sector = info.get("sector") or (info.get("category") if is_fund else "Unknown") or "Unknown"
        industry = info.get("industry") or ("ETF / Fund" if is_fund else "Unknown")

        return {
            "symbol": symbol,
            "name": name,
            "sector": sector,
            "industry": industry,
            "quote_type": quote_type or "UNKNOWN",
            "exchange": info.get("fullExchangeName") or info.get("exchange") or "Unknown",
            "currency": info.get("currency") or "USD",
            "exchange_delay_minutes": info.get("exchangeDataDelayedBy"),
            "market_state": info.get("marketState") or "Unknown",
            "nav_price": info.get("navPrice"),
            "ytd_fund_return": info.get("ytdReturn"),
            "three_year_fund_return": info.get("threeYearAverageReturn"),
            "five_year_fund_return": info.get("fiveYearAverageReturn"),
        }

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
