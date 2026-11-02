"""Dated analyst targets for presentation; never inputs to ranking scores."""
from datetime import datetime, timezone
from pathlib import Path
import json,warnings
import numpy as np
import pandas as pd

TARGET_COLUMNS = ['Target Price Low','Target Price Median','Target Price High',
    'Median Target Upside %','Current Price Minus Low Target','Price As Of',
    'Target Retrieved At','Target Source','Median Target Retrieved At','Target Data Status']
TARGET_HELP = ('Analyst price targets are price estimates, not guaranteed profits or Monte Carlo percentiles. '
    'Median Target Upside % = (median target / current price − 1) × 100. '
    'Current Price Minus Low Target = current price − low target (dollars). '
    'Median is the reported median, never substituted with an average. Missing data stays blank. '
    'Current Price is the latest available app snapshot quote, not necessarily real time. '
    'If an exact quote date is unavailable, Price As Of explicitly labels the snapshot refresh time instead. '
    'If a newer response omits the median, an earlier dated target set may be retained as a whole and flagged. '
    'Quote and target dates can differ; these display columns do not change saved ranking scores or order.')


def _positive(value):
    try:value=float(value)
    except (ValueError,TypeError):return np.nan
    return value if np.isfinite(value) and value>0 else np.nan


def _text(value):
    if value is None or pd.isna(value):return ''
    value=str(value).strip()
    return '' if value.lower() in {'','—','-','none','nan','nat','unavailable','n/a','unknown'} else value


def _time(value):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        text=_text(value).replace(' EST',' -0500').replace(' EDT',' -0400')
        parsed=pd.to_datetime(text,utc=True,errors='coerce')
    return parsed.value if not pd.isna(parsed) else -1


def load_targets(symbols):
    """Reuse persisted observations immediately; refresh in one background batch."""
    from shared_cache import cached
    try:
        bundle=json.loads((Path(__file__).parent/'data/ranking_analyst_targets.json').read_text())
        seed={symbol:row for symbol,row in bundle.get('targets',{}).items() if symbol in symbols}
    except (OSError,ValueError):seed={}
    def fetch():
        from providers.yahoo import YahooFinanceProvider
        result=YahooFinanceProvider().get_price_targets_many(symbols,max_workers=1)
        stamp=datetime.now(timezone.utc).isoformat()
        return {s:dict(v,retrieved_at=stamp) for s,v in result.items() if isinstance(v,dict)}
    try:
        return cached('ranking-analyst-targets-v62',tuple(sorted(set(symbols))),fetch,ttl=3600,
            default=seed,background=True,valid=bool)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Analyst target cache unavailable; preserving ranking')
        return seed


def enrich_targets(table,market=None,targets=None):
    """Return a copy, preserving rank; targets are whole dated source groups."""
    out=table.copy(deep=True)
    if 'Symbol' not in out:return out
    targets=targets or {};lookup={}
    if isinstance(market,pd.DataFrame) and 'Symbol' in market:
        lookup={str(r['Symbol']).strip().upper():r for r in market.to_dict('records')}
    records=[]
    for _,saved in out.iterrows():
        symbol=str(saved['Symbol']).strip().upper();current=lookup.get(symbol,{})
        provider=targets.get(symbol) or {}
        groups=[
            dict(values=[_positive(saved.get(k)) for k in TARGET_COLUMNS[:3]],
                date=saved.get('Target Retrieved At'),source=saved.get('Target Source'),
                median_date=_text(saved.get('Median Target Retrieved At')) or saved.get('Target Retrieved At')),
            dict(values=[_positive(current.get(k)) for k in ('Price Target Low','Price Target Median','Price Target High')],
                date=current.get('Price Target Updated ET'),source=_text(current.get('Price Target Source')) or 'App market snapshot',
                median_date=_text(current.get('Price Target Median Updated ET')) or current.get('Price Target Updated ET')),
            dict(values=[_positive(provider.get(k)) for k in ('low','median','high')],
                date=provider.get('retrieved_at'),source=_text(provider.get('source')) or 'Yahoo Finance analyst consensus',
                median_date=provider.get('retrieved_at'))]
        available=[(i,g) for i,g in enumerate(groups) if any(np.isfinite(v) for v in g['values'])]
        if available:
            median_groups=[pair for pair in available if np.isfinite(pair[1]['values'][1])]
            _,chosen=max(median_groups or available,key=lambda pair:(_time(pair[1]['date']),pair[0]))
            low,median,high=chosen['values']
            source=_text(chosen['source']) or 'Unavailable';target_date=_text(chosen['date']) or 'Unavailable'
            median_date=(_text(chosen['median_date']) or 'Unavailable') if np.isfinite(median) else 'Unavailable'
        else:
            low=median=high=np.nan;source=target_date=median_date='Unavailable'
        price=_positive(current.get('Price'))
        exact=_text(current.get('Data As Of'));refreshed=_text(current.get('Snapshot Updated ET'))
        price_date=exact or ('Snapshot refresh: '+refreshed if refreshed else 'Unavailable')
        if not np.isfinite(price):
            price=_positive(saved.get('Price'));price_date=_text(saved.get('Price As Of')) or 'Saved ranking quote; exact date unavailable'
        status='Median verified' if np.isfinite(median) else 'No verified median in retrieved data; no average substituted'
        if available and np.isfinite(median) and _time(chosen['date'])<max(_time(g['date']) for _,g in available):
            status='Earlier dated analyst set retained; newer response omitted median'
        records.append(dict(zip(['Price',*TARGET_COLUMNS],[price,low,median,high,
            (median/price-1)*100 if np.isfinite(price) and np.isfinite(median) else np.nan,
            price-low if np.isfinite(price) and np.isfinite(low) else np.nan,
            price_date,target_date,source,median_date,status])))
    for col in ['Price',*TARGET_COLUMNS]:out[col]=[r[col] for r in records]
    return out
