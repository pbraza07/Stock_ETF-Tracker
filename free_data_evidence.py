"""Free, cutoff-aware source evidence. Never certifies a complete stock universe."""
import hashlib
import json
import math
import os
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone
import requests

SEC_ROOT='https://data.sec.gov'
FRED_URL='https://api.stlouisfed.org/fred/series/observations'
MACRO={'DGS10':'10-year Treasury yield','T10YIE':'10-year inflation expectation','UNRATE':'Unemployment rate',
       'CPIAUCSL':'Consumer price index','GDPC1':'Real GDP','USPHCI':'Coincident activity',
       'SAHMREALTIME':'Sahm rule','RECPROUSM156N':'Smoothed recession probability','JHGDPBRINDX':'GDP recession indicator'}
TAGS={'Assets','Liabilities','StockholdersEquity','NetIncomeLoss','OperatingIncomeLoss',
      'RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','LongTermDebtCurrent',
      'LongTermDebtNoncurrent','CashAndCashEquivalentsAtCarryingValue','EarningsPerShareDiluted'}
_lock=threading.Lock()
_last=0.

def cutoff_date(value):
    result=date.fromisoformat(str(value)[:10])
    if result>date.today():raise ValueError('Historical cutoff cannot be in the future')
    return result.isoformat()

def request_json(url,params=None):
    global _last
    # Serialize this collector below SEC's aggregate public rate limit; no retry storm.
    with _lock:
        time.sleep(max(0.,.25-(time.monotonic()-_last)))
        _last=time.monotonic()
        response=requests.get(url,params=params,timeout=(4,15),headers={
            'User-Agent':os.getenv('SEC_USER_AGENT','MarketScope research https://github.com/pbraza07/Stock_ETF-Tracker'),
            'Accept':'application/json'})
    response.raise_for_status()
    return response.json()

def sec_facts(payload,cutoff):
    cutoff=cutoff_date(cutoff);latest={}
    for tag,concept in payload.get('facts',{}).get('us-gaap',{}).items():
        if tag not in TAGS:continue
        for unit,observations in concept.get('units',{}).items():
            for r in observations:
                try:
                    # Filing dates lack intraday availability. Next day is conservative.
                    available=(date.fromisoformat(r['filed'])+timedelta(days=1)).isoformat()
                    end=date.fromisoformat(r['end']).isoformat();value=float(r['val'])
                    if available>cutoff or end>cutoff or not math.isfinite(value):continue
                    if r.get('form') not in ('10-K','10-Q','10-K/A','10-Q/A','20-F','20-F/A'):continue
                    row={'concept':tag,'unit':unit,'start':r.get('start'),'observation_date':end,
                         'available_at':available,'filed':r['filed'],'value':value,
                         'accession':r['accn'],'form':r['form'],'source':'SEC EDGAR'}
                    key=(tag,unit,r.get('start'),end)
                    if key not in latest or available>latest[key]['available_at']:latest[key]=row
                except (KeyError,TypeError,ValueError):continue
    return sorted(latest.values(),key=lambda r:(r['observation_date'],r['concept'],r['unit']))

def fred_records(payload,series,cutoff):
    cutoff=cutoff_date(cutoff);rows=[]
    if not isinstance(payload.get('observations'),list):raise ValueError('Missing observations')
    if int(payload.get('count',len(payload['observations'])))>len(payload['observations']):
        raise ValueError('Incomplete vintage response')
    for r in payload['observations']:
        try:
            value=float(r['value'])
            if r['date']>cutoff or not math.isfinite(value):continue
            if r.get('realtime_start',cutoff)>cutoff:continue
            rows.append({'kind':'macro','key':series,'observation_date':r['date'],
                'available_at':cutoff,'value':value,'source':'FRED / ALFRED',
                'availability_basis':'Known at requested vintage; not original publication timestamp',
                'vintage_date':cutoff})
        except (ValueError,TypeError,KeyError):continue
    return rows

def collect(kind,identifier,cutoff):
    cutoff=cutoff_date(cutoff);identifier=identifier.strip().upper()
    result={'kind':kind,'identifier':identifier,'cutoff':cutoff,'records':[],
            'retrieved_at':datetime.now(timezone.utc).isoformat(),
            'point_in_time_integrity':'PARTIAL','survivorship_complete':False,
            'probability_validation':'UNVALIDATED',
            'limitations':['No complete historical eligible universe or delisting payouts.',
                          'No historical analyst-estimate archive or independent quote verification.',
                          'Evidence only; does not replace forecast inputs or certify probabilities.']}
    if kind=='Macro vintage':
        if identifier not in MACRO:raise ValueError('Unsupported series')
        key=os.getenv('FRED_API_KEY','').strip()
        if not key:raise ValueError('Configure the free FRED_API_KEY in Render Environment for vintage downloads.')
        payload=request_json(FRED_URL,{'series_id':identifier,'api_key':key,'file_type':'json',
            'realtime_start':cutoff,'realtime_end':cutoff,'observation_end':cutoff,'limit':100000})
        result['records']=fred_records(payload,identifier,cutoff)
        result['source_url']='https://fred.stlouisfed.org/series/'+identifier
    else:
        if not re.fullmatch(r'[A-Z0-9.\-]{1,12}',identifier):raise ValueError('Enter a ticker or SEC CIK.')
        if identifier.isdigit():cik=int(identifier)
        else:
            from shared_cache import cached
            mapping=cached('free-sec-tickers-v1',{},lambda:request_json('https://www.sec.gov/files/company_tickers.json'),ttl=86400,default={})
            matches=[r for r in mapping.values() if str(r.get('ticker','')).upper()==identifier]
            if not matches:raise ValueError('Ticker mapping unavailable. Enter the SEC CIK directly; current ticker lookup is not a historical universe.')
            cik=int(matches[0]['cik_str'])
        url=f'{SEC_ROOT}/api/xbrl/companyfacts/CIK{cik:010d}.json'
        result['records']=sec_facts(request_json(url),cutoff)
        result['source_url']=url;result['cik']=cik
        result['limitations'].append('Standard US-GAAP tags only; units and fiscal durations are preserved, not mixed into derived ratios. Current SEC archive may contain corrections; date filtering alone is not full vintage certification.')
    if not result['records']:raise ValueError('No qualifying observations available at this cutoff; no substitute data used.')
    result['sha256']=hashlib.sha256(json.dumps(result['records'],sort_keys=True).encode()).hexdigest()
    return result


def render_free_evidence(namespace='recession'):
    import streamlit as st
    from shared_cache import cached
    from free_market_checks import render_checks
    render_checks(namespace)
    prefix='free_evidence_'+namespace
    with st.expander('Free historical evidence — FRED vintages & SEC filings'):
        st.caption('Inspect what was knowable at a historical cutoff. Downloads are separate from projection calculations. No paid subscriptions.')
        with st.form(prefix+'_form'):
            kind=st.selectbox('Evidence source',['Macro vintage','Company filings'])
            identifier=st.text_input('FRED series, stock ticker, or SEC CIK',value='DGS10',help='Macro: '+', '.join(MACRO)+'. Company: AAPL or 320193. Select Company filings above.')
            cutoff=st.date_input('Historical cutoff',value=date.today(),max_value=date.today())
            submit=st.form_submit_button('Retrieve historical evidence')
        if submit:
            with st.spinner('Retrieving cutoff-filtered source records…'):
                try:
                    inputs=[kind,identifier.strip().upper(),cutoff.isoformat()]
                    result=cached('free-evidence-v1',inputs,lambda:collect(*inputs),ttl=86400,default=None)
                    if result:st.session_state[prefix+'_result']=result
                    else:st.warning('Source unavailable or no eligible records. Last successful evidence remains below. Check the cutoff, identifier and free FRED key. SEC may limit automated access; use a CIK if ticker lookup fails.')
                except (ValueError,requests.RequestException) as exc:
                    st.warning(str(exc) if isinstance(exc,ValueError) else 'Provider request failed; retained previous evidence.')
        result=st.session_state.get(prefix+'_result')
        if result:
            st.write(f"**{result['identifier']} — known by {result['cutoff']}** · {len(result['records'])} records")
            st.caption('Retrieved '+result['retrieved_at']+' · PARTIAL evidence / probabilities UNVALIDATED')
            st.dataframe(result['records'],hide_index=True,width='stretch')
            st.link_button('Original source',result['source_url'])
            st.download_button('Download dated evidence JSON',json.dumps(result,indent=2),
                f"MarketScope_evidence_{result['identifier']}_{result['cutoff']}.json",'application/json',key=prefix+'_download')
            for limitation in result['limitations']:st.caption(limitation)
        else:st.caption('Complete historical universe, delisting payouts and independent quotes remain unavailable. No calibration uplift is awarded for downloading evidence.')
