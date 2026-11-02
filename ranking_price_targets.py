"""Analyst price targets for ranking presentation; never inputs to ranking scores."""
from datetime import datetime, timezone
import numpy as np
import pandas as pd

TARGET_COLUMNS = ["Target Price Low", "Target Price Median", "Target Price High",
                  "Median Target Upside %", "Current Price Minus Low Target",
                  "Price As Of", "Target Retrieved At", "Target Source"]
TARGET_HELP = ("Analyst price targets are price estimates, not guaranteed profits or Monte Carlo percentiles. "
    "Median Target Upside % = (median target / current price − 1) × 100. "
    "Current Price Minus Low Target = current price − low target (dollars). "
    "Median is the reported median, never substituted with an average. Missing data stays blank. "
    "Current Price is the latest available app snapshot quote, not necessarily real time. "
    "Quote and target dates can differ; these display columns do not change saved ranking scores or order.")


def _positive(value):
    try:value=float(value)
    except (ValueError,TypeError):return np.nan
    return value if np.isfinite(value) and value>0 else np.nan


def load_targets(symbols):
    """Single-flight, nonblocking source refresh; no request per table row."""
    from shared_cache import cached
    def fetch():
        from providers.yahoo import YahooFinanceProvider
        result=YahooFinanceProvider().get_price_targets_many(symbols,max_workers=2)
        stamp=datetime.now(timezone.utc).isoformat()
        return {s:dict(v,retrieved_at=stamp) for s,v in result.items() if isinstance(v,dict)}
    try:
        return cached('ranking-analyst-targets',tuple(sorted(set(symbols))),fetch,ttl=3600,
                      default={},background=True,valid=bool)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Analyst target cache unavailable; preserving ranking')
        return {}


def enrich_targets(table,market=None,targets=None):
    """Return a copy, keeping the saved score/rank; target mean is not median."""
    out=table.copy(deep=True)
    if 'Symbol' not in out:return out
    targets=targets or {}
    lookup={}
    if isinstance(market,pd.DataFrame) and 'Symbol' in market:
        for row in market.to_dict('records'):
            lookup[str(row['Symbol']).strip().upper()]=row
    records=[]
    for _,saved in out.iterrows():
        symbol=str(saved['Symbol']).strip().upper()
        current=lookup.get(symbol,{})
        provider=targets.get(symbol) or {}
        # A fresh response is used as a unit; incomplete responses never splice
        # low/median/high values from independently dated analyst snapshots.
        if any(np.isfinite(_positive(provider.get(k))) for k in ('low','median','high')):
            low,median,high=[_positive(provider.get(k)) for k in ('low','median','high')]
            source=provider.get('source','Yahoo Finance analyst consensus')
            target_date=provider.get('retrieved_at','Unavailable')
        elif any(np.isfinite(_positive(current.get(k))) for k in ('Price Target Low','Price Target Median','Price Target High')):
            low,median,high=[_positive(current.get(k)) for k in ('Price Target Low','Price Target Median','Price Target High')]
            source=current.get('Price Target Source','App market snapshot')
            target_date=current.get('Price Target Updated ET','Unavailable')
        else:
            low,median,high=[_positive(saved.get(k)) for k in TARGET_COLUMNS[:3]]
            source=saved.get('Target Source','Unavailable')
            target_date=saved.get('Target Retrieved At','Unavailable')
        price=_positive(current.get('Price'))
        price_date=current.get('Data As Of') or current.get('Snapshot Updated ET') or 'Unavailable'
        if not np.isfinite(price):
            price=_positive(saved.get('Price'));price_date=saved.get('Price As Of','Saved ranking quote')
        records.append(dict(zip(['Price',*TARGET_COLUMNS],[price,low,median,high,
            (median/price-1)*100 if np.isfinite(price) and np.isfinite(median) else np.nan,
            price-low if np.isfinite(price) and np.isfinite(low) else np.nan,
            price_date,target_date,source])))
    for col in ['Price',*TARGET_COLUMNS]:out[col]=[r[col] for r in records]
    return out
