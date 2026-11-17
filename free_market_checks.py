"""Optional free Alpha Vantage evidence, bounded quota and immutable forecasts."""
import csv
import hashlib
import io
import json
import math
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
import requests
from performance_store import database, initialize, get, put, key_for

URL='https://www.alphavantage.co/query'

def reserve_request(now=None):
    now=time.time() if now is None else now
    with database() as db:
        initialize(db,'alpha-quota-v1',lambda d:d.execute('CREATE TABLE IF NOT EXISTS alpha_requests (stamp DOUBLE PRECISION NOT NULL)'))
        db.execute('BEGIN' if db.postgres else 'BEGIN IMMEDIATE')
        try:
            if db.postgres:db.execute('SELECT pg_advisory_xact_lock(51166)')
            db.execute('DELETE FROM alpha_requests WHERE stamp < ?',(now-86400,))
            n,last=db.execute('SELECT COUNT(*),MAX(stamp) FROM alpha_requests').fetchone()
            if n>=20:raise ValueError('Free-feed budget used: 20 requests per rolling 24 hours. Cached evidence remains available.')
            if last is not None and now-last<13:raise ValueError('Please wait 13 seconds between free-feed requests.')
            db.execute('INSERT INTO alpha_requests VALUES (?)',(now,));db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK');raise

def fetch(params,parser):
    cachekey=key_for('alpha-free-v1',params);previous=get(cachekey)
    if previous and previous[2]>time.time():return {**previous[0],'cache_status':'Cached'}
    key=os.getenv('ALPHA_VANTAGE_API_KEY','').strip()
    if not key:raise ValueError('Add your free ALPHA_VANTAGE_API_KEY to Render Environment to enable this feed.')
    try:
        reserve_request()
        response=requests.get(URL,params={**params,'apikey':key},timeout=(4,15))
        response.raise_for_status()
        if response.text.lstrip().startswith('{'):
            payload=response.json()
            if any(k in payload for k in ('Information','Note','Error Message')):
                raise ValueError('Provider declined this request or its quota is exhausted. No substitute data used.')
        result={'data':parser(response.text),'retrieved_at':datetime.now(timezone.utc).isoformat(),'cache_status':'Updated'}
        put(cachekey,result,86400);return result
    except (requests.RequestException,ValueError):
        if previous:return {**previous[0],'cache_status':'Stale — refresh failed'}
        raise ValueError('Free-feed request unavailable, rate-limited, or invalid. Check key and try later; existing results are retained.') from None

def parse_listings(text,cutoff,state):
    rows=list(csv.DictReader(io.StringIO(text)))
    required={'symbol','name','exchange','assetType','ipoDate','delistingDate','status'}
    if not rows or not required<=rows[0].keys():raise ValueError('Invalid listing schema')
    result=[]
    for r in rows:
        if r['status'].lower()!=state:continue
        if r['ipoDate'] and r['ipoDate']!='null' and r['ipoDate']>cutoff:continue
        if state=='delisted' and (r['delistingDate'] in ('','null') or r['delistingDate']>cutoff):continue
        result.append(r)
    if not result:raise ValueError('No matching listings')
    return result

def listings(cutoff,state='delisted'):
    cutoff=date.fromisoformat(str(cutoff)).isoformat()
    if not '2010-01-01'<cutoff<=date.today().isoformat():raise ValueError('Listing cutoff must be after January 1, 2010 and no later than today.')
    if state not in ('active','delisted'):raise ValueError('Invalid listing state')
    return fetch({'function':'LISTING_STATUS','date':cutoff,'state':state},lambda t:parse_listings(t,cutoff,state))

def parse_quote(text,symbol):
    q=json.loads(text).get('Global Quote',{})
    value=float(q['05. price']);day=date.fromisoformat(q['07. latest trading day']).isoformat()
    if q['01. symbol']!=symbol or not math.isfinite(value) or value<=0:raise ValueError('Invalid quote')
    return {'symbol':symbol,'value':value,'observation_date':day,'source':'Alpha Vantage','price_basis':'Unadjusted regular-session close'}

def verify_quote(symbol):
    symbol=symbol.strip().upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,11}',symbol):raise ValueError('Enter a U.S. stock symbol.')
    a=fetch({'function':'GLOBAL_QUOTE','symbol':symbol},lambda t:parse_quote(t,symbol))
    quote=a['data'];day=date.fromisoformat(quote['observation_date'])
    import yfinance as yf
    ticker=yf.Ticker(symbol)
    frame=ticker.history(start=day.isoformat(),end=(day+timedelta(days=1)).isoformat(),auto_adjust=False,actions=True,raise_errors=True)
    meta=ticker.get_history_metadata()
    if meta.get('currency')!='USD' or meta.get('exchangeName') not in ('NMS','NYQ','NGM','NCM','ASE','PCX','BTS'):
        return {**a,'status':'NOT COMPARABLE','reason':'Only verified USD U.S. exchange listings are supported.'}
    exact=frame[[d.date()==day for d in frame.index]]
    if len(exact)!=1:return {**a,'status':'NOT COMPARABLE','reason':'Matching Yahoo trading day unavailable.'}
    value=float(exact.iloc[0]['Close'])
    if not math.isfinite(value) or value<=0:raise ValueError('Yahoo price is invalid')
    from investment_evidence import compare_reported_prices
    first={**quote,'currency':'USD'}
    second={**first,'source':'Yahoo Finance','value':value}
    return {**a,**compare_reported_prices(first,second),'alpha':first,'yahoo':second,
        'checked_at':datetime.now(timezone.utc).isoformat(),
        'meaning':'Cross-provider agreement within 1%; not independent exchange-origin certification or return validation.'}

def forecast_record(result):
    from investment_evidence import clean
    created=datetime.now(timezone.utc)
    records=[]
    start=float(result['inputs']['starting_investment'])
    for strategy,table in result['references'].items():
        final=table.iloc[-1]
        records.append({'strategy':strategy,'horizon_years':result['inputs']['future_years'],
            'ending_balance_percentiles':{f'P{p}':float(final[f'P{p} Ending Balance']) for p in (10,25,50,75,90)},
            'starting_investment':start})
    payload=clean({'recorded_at':created.isoformat(),'model_version':result['audit']['model_version'],
        'inputs':result['inputs'],'settings':result['settings'],'input_evidence':result['audit']['input_evidence'],
        'forecasts':records,'status':'PENDING — no matured realized outcomes',
        'limitations':'Reference includes configured contributions/costs. Outcome evaluator must reproduce these cashflows, dates and strategy. Archived forecasts do not validate past probabilities.'})
    payload['sha256']=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
    return payload

def render_checks(namespace='recession'):
    import streamlit as st
    prefix='free_checks_'+namespace
    with st.expander('Free listing history & cross-provider price checks'):
        configured=bool(os.getenv('ALPHA_VANTAGE_API_KEY','').strip())
        st.caption('Alpha Vantage key: '+('Configured' if configured else 'Not configured — set ALPHA_VANTAGE_API_KEY in Render Environment.'))
        st.caption('End-of-day checks only. Up to 20 requests per rolling 24 hours across this deployment; cached for 24 hours. Coverage is partial. Provider licensing must permit your use.')
        with st.form(prefix):
            operation=st.selectbox('Check',['Compare stock close','Historical delisted listings','Historical active listings'])
            symbol=st.text_input('U.S. ticker',value='AAPL')
            cutoff=st.date_input('Listing cutoff',value=date.today(),min_value=date(2010,1,2),max_value=date.today())
            submit=st.form_submit_button('Run free data check',disabled=not configured)
        if submit:
            try:
                with st.spinner('Checking free sources…'):
                    value=verify_quote(symbol) if operation=='Compare stock close' else listings(cutoff.isoformat(),'delisted' if 'delisted' in operation else 'active')
                    st.session_state[prefix]={'operation':operation,'symbol':symbol,'cutoff':cutoff.isoformat(),'result':value}
            except Exception as exc:
                st.warning(str(exc) if isinstance(exc,ValueError) else 'Provider or storage unavailable; previous result retained.')
        saved=st.session_state.get(prefix)
        if saved:
            st.write(saved['operation']);value=saved['result'];st.caption(value['cache_status']+' · Retrieved '+value['retrieved_at'])
            if isinstance(value['data'],list):
                st.dataframe(value['data'],hide_index=True,width='stretch')
                st.caption('Listing presence is not complete terminal-return coverage. No missing payout is assumed zero or replaced by a survivor.')
            else:st.json(value)
            st.download_button('Download verification evidence',json.dumps(saved,indent=2),'MarketScope_free_verification.json','application/json',key=prefix+'_export')
