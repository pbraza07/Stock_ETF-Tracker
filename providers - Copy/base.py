from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Iterable, List
import pandas as pd


class MarketDataProvider(ABC):
    """Replaceable market-data provider contract."""

    name: str = "Unknown"

    @abstractmethod
    def download_daily_history(self, symbols: Iterable[str]) -> Dict[str, pd.DataFrame]:
        raise NotImplementedError

    @abstractmethod
    def download_live_prices(self, symbols: Iterable[str]) -> Dict[str, float]:
        raise NotImplementedError

    @abstractmethod
    def get_metadata(self, symbol: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, max_results: int = 8) -> List[dict]:
        raise NotImplementedError
