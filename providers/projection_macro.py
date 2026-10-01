"""Authenticated macro observations with last-successful disk fallback."""
import json
import os
import math
import pandas as pd
from io import StringIO
from macro_data import cached_download


def observations(text, series, api=False):
    if api:
        payload=json.loads(text)
        frame=pd.DataFrame(payload.get('observations', []))
        date_column,value_column='date','value'
    else:
        frame=pd.read_csv(StringIO(text))
        date_column='observation_date' if 'observation_date' in frame else 'DATE'
        value_column=series
    if date_column not in frame or value_column not in frame:
        raise ValueError('Missing macro observations')
    frame=pd.DataFrame({'date':pd.to_datetime(frame[date_column],errors='coerce'),
                        'value':pd.to_numeric(frame[value_column],errors='coerce')}).dropna()
    frame=frame[frame.value.map(math.isfinite)].sort_values('date').drop_duplicates('date',keep='last').tail(36)
    if frame.empty: raise ValueError('No valid macro observations')
    frame['date']=frame.date.dt.strftime('%Y-%m-%d')
    return frame.to_dict('records')


def fetch_one(name, series, timeout=8, cache_dir=None, force=False):
    key=os.getenv('FRED_API_KEY','').strip()
    options=dict(ttl=6*3600,force=force,cache_dir=cache_dir,timeout=(4,timeout),attempts=1)
    result=None
    if key:
        result=cached_download('projection_'+series,'https://api.stlouisfed.org/fred/series/observations',
            lambda text:observations(text,series,True),
            params={'series_id':series,'api_key':key,'file_type':'json','sort_order':'desc','limit':120},**options)
    if result is None or result['status'] not in ('Updated','Cached'):
        previous=result
        result=cached_download('projection_'+series,f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}',
            lambda text:observations(text,series),**options)
        if previous and previous.get('error') and result['status'] not in ('Updated','Cached'):
            result['error']='API: '+previous['error']+'; CSV: '+str(result.get('error'))
    rows=result.get('data') or []
    valid=[r for r in rows if isinstance(r,dict) and r.get('date') and isinstance(r.get('value'),(int,float)) and math.isfinite(r['value'])]
    return name, {'series_id':series,'source':'Federal Reserve Bank of St. Louis FRED',
        'source_url':result['source'],'observation_date':valid[-1]['date'] if valid else None,
        'value':valid[-1]['value'] if valid else None,'observations':valid,
        'retrieved_at':result.get('retrieved_at'),'status':result['status'] if valid else 'Unavailable',
        'error':result.get('error')}


def freshness(payload, expected):
    valid=[v for name,v in payload.items() if name in expected and v.get('observation_date') and isinstance(v.get('value'),(int,float)) and math.isfinite(v['value'])]
    status='UNAVAILABLE' if not valid else ('PARTIAL' if len(valid)<len(expected) else 'AVAILABLE')
    if valid and any(v.get('status')=='Stale cache' for v in valid): status='STALE' if status=='AVAILABLE' else 'PARTIAL / STALE'
    dates=[v['observation_date'] for v in valid]
    return {'status':status,'updated':(min(dates)+' to '+max(dates)) if dates else 'Unavailable',
            'coverage':f'{len(valid)}/{len(expected)} series',
            'retrieved_at':max((v.get('retrieved_at') or '' for v in valid),default='') or 'Unavailable'}
