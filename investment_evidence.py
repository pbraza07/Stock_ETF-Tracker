"""Versioned calculation evidence; timestamps are not interchangeable."""
import hashlib
import json
from datetime import datetime, timezone
import numpy as np
import pandas as pd

MODEL_VERSION='5.11.64'
PROBABILITY_HELP=(
    'Conditional model estimates, not empirically verified investment odds. '
    'P90 is a high outcome threshold: about 10% of simulated outcomes exceed it. '
    'More simulations reduce sampling noise, not model bias. Compare loss risk and goal success. '
    'Analyst targets are reported opinions, not MarketScope projections. '
    'News arrows describe potential impact, not a validated return forecast.'
)

def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):return [clean(v) for v in value]
    if isinstance(value,np.generic):value=value.item()
    if isinstance(value,float) and not np.isfinite(value):return None
    if isinstance(value,(pd.Timestamp,datetime)):return value.isoformat()
    return value

def snapshot(model,context):
    payload=clean({'version':MODEL_VERSION,'holdings':model.symbols,'categories':model.categories,
        'historical_returns':model.historical_returns.to_dict('records'),
        'fundamentals':context.get('fundamentals',{}),'macro':context.get('macro',{})})
    encoded=json.dumps(payload,sort_keys=True,separators=(',',':'),default=str)
    return {'sha256':hashlib.sha256(encoded.encode()).hexdigest(),'inputs':payload,
        'recorded_at':datetime.now(timezone.utc).isoformat(),
        'point_in_time_integrity':'LIMITED unless externally verified publication vintages supplied',
        'cross_source_verification':'Not independently verified; no second provider is fabricated',
        'timestamp_definitions':'Observation: period measured. Available-at: first public release. Retrieved-at: download; never substitutes for either.'}

def compare_reported_prices(first,second,tolerance=.01):
    """Require matching basis/currency/date before comparing independent quotes."""
    for field in ('currency','observation_date','price_basis'):
        if not first.get(field) or first.get(field)!=second.get(field):
            return {'status':'NOT COMPARABLE','reason':field+' differs or is missing'}
    if not first.get('source') or first.get('source')==second.get('source'):
        return {'status':'NOT INDEPENDENT'}
    a,b=float(first['value']),float(second['value'])
    if not np.isfinite([a,b]).all() or min(a,b)<=0:return {'status':'INVALID'}
    difference=abs(a-b)/a
    return {'status':'MATCH' if difference<=tolerance else 'REVIEW','relative_difference':difference}
