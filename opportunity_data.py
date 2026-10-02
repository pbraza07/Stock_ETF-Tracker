"""Retain recent observed fundamentals for live screening during feed outages.

This runs only in the live UI loader, never in point-in-time backtests.
Each recovered field retains its original retrieval date; no estimates are made.
"""
import json
import os
import tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
from planning_assumptions import number

FIELDS=('market_cap','current_price','return_on_invested_capital','return_on_equity',
        'operating_margin','free_cash_flow','revenue_growth','forward_eps_growth',
        'earnings_growth','debt_to_equity','forward_pe')

def retain_observed_fundamentals(context,path=None,now=None):
    now=now or datetime.now(timezone.utc)
    path=Path(path) if path else Path(__file__).parent/'data/quality_fundamentals_cache.json'
    try:cache=json.loads(path.read_text())
    except (OSError,ValueError):cache={}
    if not isinstance(cache,dict):cache={}
    out=dict(context);fund={s:dict(f or {}) for s,f in context.get('fundamentals',{}).items()}
    for symbol in context.get('requested_symbols',[]):fund.setdefault(symbol,{})
    warnings=list(context.get('failures',[]))
    for symbol,values in fund.items():
        saved=cache.get(symbol,{})
        if not isinstance(saved,dict):saved={}
        recovered={}
        for key in FIELDS:
            value=number(values.get(key));record=saved.get(key,{})
            if not isinstance(record,dict):record={}
            if value is not None:
                saved[key]={'value':value,'retrieved_at':values.get('retrieved_at') or context.get('retrieved_at') or now.isoformat()}
                continue
            try:
                stamp=datetime.fromisoformat(record['retrieved_at'])
                valid=stamp.tzinfo is not None and timedelta(0)<=now-stamp<=timedelta(days=7)
            except (KeyError,TypeError,ValueError):valid=False
            if valid and number(record.get('value')) is not None:
                values[key]=record['value'];recovered[key]=record['retrieved_at']
        cache[symbol]=saved
        if recovered:
            values['cached_fields']=recovered
            values['source']=(values.get('source') or 'Live provider')+'; recent observed cache (up to 7 days)'
            warnings.append(symbol+': cached observed fundamentals used; field dates are in the audit.')
    out['fundamentals']=fund;out['failures']=warnings
    temp=None
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,delete=False,encoding='utf-8') as f:
            temp=f.name;json.dump(cache,f,allow_nan=False)
        os.replace(temp,path)
    except (OSError,ValueError,TypeError):
        warnings.append('Observed fundamentals could not be cached; this run still uses available data.')
    finally:
        if temp and os.path.exists(temp):os.unlink(temp)
    return out
