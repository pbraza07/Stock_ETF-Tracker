from __future__ import annotations

from typing import Dict, Iterable, List, Optional

import requests


class NasdaqScreenerProvider:
    """Read Nasdaq's public stock/ETF screener endpoints.

    Stocks use Nasdaq's consensus recommendation buckets. ETFs are only assigned
    an analyst rating when Nasdaq's ETF response itself exposes a genuine analyst
    or recommendation field. Fund/technical scores are never mislabeled as analyst
    consensus.
    """

    STOCK_URL = "https://api.nasdaq.com/api/screener/stocks"
    ETF_URL = "https://api.nasdaq.com/api/screener/etf"
    STOCK_PAGE = "https://www.nasdaq.com/market-activity/stocks/screener"
    RATING_BUCKETS = {
        "strong_buy": "Strong Buy",
        "buy": "Buy",
        "hold": "Hold",
        "sell": "Sell",
        "strong_sell": "Strong Sell",
    }

    def __init__(self, timeout: int = 45):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.nasdaq.com",
            "Referer": self.STOCK_PAGE,
        }

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        return str(symbol or "").strip().upper().replace("/", "-").replace(".", "-")

    @staticmethod
    def normalize_rating(value: object) -> str:
        text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
        text = " ".join(text.split())
        return {
            "strong buy": "Strong Buy",
            "buy": "Buy",
            "outperform": "Buy",
            "out perform": "Buy",
            "overweight": "Buy",
            "hold": "Hold",
            "neutral": "Hold",
            "equal weight": "Hold",
            "market perform": "Hold",
            "sell": "Sell",
            "underperform": "Sell",
            "under perform": "Sell",
            "underweight": "Sell",
            "strong sell": "Strong Sell",
        }.get(text, "Not Rated")

    @staticmethod
    def _rows(payload: dict) -> List[dict]:
        data = payload.get("data") or {}
        table = data.get("table") or {}
        rows = table.get("rows") or data.get("rows") or []
        if not rows and isinstance(data.get("data"), dict):
            rows = (data.get("data") or {}).get("rows") or []
        return rows if isinstance(rows, list) else []

    def _get(self, url: str, params: dict) -> dict:
        response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def get_stock_rating_map(self, symbols: Optional[Iterable[str]] = None) -> Dict[str, str]:
        wanted = None if symbols is None else {self.normalize_symbol(s) for s in symbols if str(s).strip()}
        result: Dict[str, str] = {}
        for filter_value, label in self.RATING_BUCKETS.items():
            payload = self._get(
                self.STOCK_URL,
                {
                    "tableonly": "true",
                    "limit": 10000,
                    "offset": 0,
                    "download": "true",
                    "recommendation": filter_value,
                },
            )
            for row in self._rows(payload):
                symbol = self.normalize_symbol(row.get("symbol"))
                if symbol and (wanted is None or symbol in wanted):
                    result[symbol] = label
        return result

    def get_etf_rating_map(self, symbols: Optional[Iterable[str]] = None) -> Dict[str, str]:
        """Return genuine ETF analyst fields only when Nasdaq exposes them."""
        wanted = None if symbols is None else {self.normalize_symbol(s) for s in symbols if str(s).strip()}
        try:
            payload = self._get(self.ETF_URL, {"download": "true"})
        except Exception:
            return {}
        result: Dict[str, str] = {}
        candidate_keys = (
            "analystRating",
            "analyst_rating",
            "recommendation",
            "recommendationKey",
            "analystConsensus",
        )
        for row in self._rows(payload):
            symbol = self.normalize_symbol(row.get("symbol") or row.get("ticker"))
            if not symbol or (wanted is not None and symbol not in wanted):
                continue
            raw = next((row.get(k) for k in candidate_keys if row.get(k) not in (None, "", "--")), None)
            rating = self.normalize_rating(raw)
            if rating != "Not Rated":
                result[symbol] = rating
        return result
