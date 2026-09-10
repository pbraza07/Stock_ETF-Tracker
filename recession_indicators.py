"""Native FRED charts; monthly observations, never third-party page embeds."""
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
import json
import os
from macro_snapshots import with_snapshot
import pandas as pd
from macro_data import cached_download

SERIES = {
    'USPHCI': {
        'name':'Coincident Economic Activity Index for the United States',
        'units':'Index (2007 = 100)', 'source':'Federal Reserve Bank of Philadelphia',
        'color':'#38BDF8', 'adjustment':'Seasonally adjusted',
        'explanation':'This monthly index combines nonfarm payroll employment, unemployment, manufacturing hours, and wages and salaries. A rising line indicates increasing economic activity; a sustained falling line indicates weakening activity. The level 100 is the 2007 reference level, not a recession threshold. It measures current conditions rather than predicting a recession on its own.',
    },
    'RECPROUSM156N': {
        'name':'Smoothed U.S. Recession Probabilities',
        'adjustment':'Not seasonally adjusted', 'units':'Percent', 'source':'Marcelle Chauvet and Jeremy Piger', 'color':'#A78BFA',
        'explanation':'This monthly series estimates the probability that the U.S. economy was in recession during the observation month. The model uses payroll employment, industrial production, real personal income excluding transfers, and real manufacturing and trade sales. Values closer to 100% indicate stronger modeled recession evidence; values closer to 0% indicate weaker evidence. For example, 0.76 means 0.76%, not 76%. These are smoothed estimates that can be revised using later information, not a forecast of the probability of a future recession or an official recession declaration. The Sahm Rule’s 0.50-percentage-point threshold does not apply.',
    },
}


def parse_fred(text, series):
    frame = pd.read_csv(StringIO(text))
    date_col = 'observation_date' if 'observation_date' in frame else 'DATE'
    if date_col not in frame or series not in frame:
        raise ValueError('FRED response does not contain the requested date/value columns')
    frame = pd.DataFrame({'date':pd.to_datetime(frame[date_col],errors='coerce'), 'value':pd.to_numeric(frame[series],errors='coerce')})
    frame = frame.dropna().drop_duplicates('date',keep='last').sort_values('date')
    frame = frame[frame.value.map(lambda x: float('-inf') < x < float('inf'))]
    if series=='RECPROUSM156N' and not frame.value.between(0,100).all():
        raise ValueError('Recession probability must be between 0 and 100 percent')
    if frame.empty:
        raise ValueError('FRED returned no valid observations')
    frame['date'] = frame.date.dt.strftime('%Y-%m-%d')
    return frame.to_dict('records')


def load_series(series, force=False, cache_dir=None):
    if series not in SERIES:
        raise ValueError('Unknown recession indicator')
    api_key=os.getenv('FRED_API_KEY','').strip()
    if api_key:
        def parse_api(text):
            payload=json.loads(text)
            observations=payload.get('observations')
            if not isinstance(observations,list):raise ValueError('FRED API response missing observations')
            if payload.get('count',len(observations))>len(observations):raise ValueError('Incomplete FRED API response')
            frame=pd.DataFrame(observations)
            if 'realtime_start' in frame:
                frame=frame.sort_values(['date','realtime_start'],kind='stable').drop_duplicates('date',keep='last')
            csv=frame.rename(columns={'date':'observation_date','value':series}).to_csv(index=False)
            return parse_fred(csv,series)
        result=cached_download(series,'https://api.stlouisfed.org/fred/series/observations',parse_api,6*3600,force,cache_dir,
            params={'api_key':api_key,'series_id':series,'file_type':'json','sort_order':'asc','limit':100000,'realtime_start':'1990-07-04','realtime_end':'9999-12-31'})
    else:
        result=cached_download(series,f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}',
            lambda text:parse_fred(text,series),6*3600,force,cache_dir)
    return with_snapshot(series,result) if cache_dir is None else result



def indicator_figure(series, records, years=10):
    import plotly.graph_objects as go
    frame=pd.DataFrame(records)
    frame['date']=pd.to_datetime(frame.date)
    if years:
        frame=frame[frame.date >= frame.date.max()-pd.DateOffset(years=years)]
    frame=frame.set_index('date').asfreq('MS').reset_index()
    spec=SERIES[series]
    fig=go.Figure(go.Scatter(x=frame.date,y=frame.value,mode='lines',name=spec['name'],
        line={'color':spec['color'],'width':2.5},connectgaps=False,
        hovertemplate='%{x|%b %Y}<br>%{y:.2f}'+('%' if series=='RECPROUSM156N' else '')+'<extra></extra>'))
    if series=='RECPROUSM156N':
        fig.update_yaxes(range=[0,100],ticksuffix='%')
    fig.update_layout(template='plotly_dark',paper_bgcolor='#06101A',plot_bgcolor='#091825',
        font={'family':'Arial, sans-serif','color':'#E2E8F0'},height=380,
        margin={'l':15,'r':20,'t':35,'b':30},showlegend=False,hovermode='x unified',
        xaxis={'title':'Observation month','gridcolor':'#20394A'},
        yaxis={'title':spec['units'],'gridcolor':'#20394A','zerolinecolor':'#345168'})
    return fig


def render_recession_indicators():
    import streamlit as st
    st.subheader('Recession Indicators — United States')
    st.caption('Monthly economic evidence from FRED. Charts are built from downloaded observations in MarketScope.')
    refresh=st.button('Refresh recession data',key='refresh_recession_data')
    window=st.selectbox('Chart history',['10 years','5 years','20 years','All history'],key='recession_history_window')
    years={'10 years':10,'5 years':5,'20 years':20,'All history':None}[window]
    with st.spinner('Loading FRED observations…'):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=dict(zip(SERIES,pool.map(lambda key:load_series(key,refresh),SERIES)))
    for series,spec in SERIES.items():
        result=results[series]
        st.markdown(f"### {spec['name']} ({series})")
        if result['status']=='Unavailable':
            st.warning('No valid FRED download or saved snapshot is available. See Connection details below.')
        else:
            if result['status']=='Stale cache':
                st.warning('The refresh failed. Showing the last valid downloaded observations; these may be outdated.')
            records=result['data'];last=records[-1];date=pd.Timestamp(last['date']).strftime('%b %Y')
            a,b,c=st.columns(3)
            a.metric('Latest observation',f"{last['value']:.2f}"+('%' if series=='RECPROUSM156N' else ''))
            b.metric('Observation month',date)
            if series=='RECPROUSM156N':
                c.metric('Estimate type', 'Smoothed probability')
            else:
                lookup={row['date']:row['value'] for row in records}
                prior=lookup.get((pd.Timestamp(last['date'])-pd.DateOffset(months=1)).strftime('%Y-%m-%d'))
                c.metric('Monthly change',f"{(last['value']/prior-1)*100:+.2f}%" if prior else 'Unavailable')
            st.caption(f"{result['status']} · Downloaded {result['retrieved_at']} · Monthly · {spec['adjustment']}")
            st.plotly_chart(indicator_figure(series,records,years),width='stretch',key=f'fred_{series}')
            with st.expander(f'View {series} observations / download'):
                frame=pd.DataFrame(records).rename(columns={'date':'Observation date','value':spec['units']})
                st.dataframe(frame.iloc[::-1],hide_index=True,width='stretch')
                st.download_button('Download CSV',frame.to_csv(index=False),f'{series}.csv','text/csv',key=f'csv_{series}')
        if result.get('error'):
            with st.expander(f'Connection details — {series}',expanded=result['status']=='Unavailable'):
                st.write('Latest attempt: '+result['error'])
                st.write('FRED API key configured: '+('Yes' if os.getenv('FRED_API_KEY') else 'No'))
                st.markdown('For reliable collection, set `FRED_API_KEY` in Render Environment and the GitHub repository Actions secrets, then run **Refresh macro snapshots** in GitHub Actions. Get your key from [FRED](https://fred.stlouisfed.org/docs/api/api_key.html). Do not paste keys into chat.')
        st.markdown('**How to read this graph:** '+spec['explanation'])
        st.markdown(f"Source: {spec['source']}, retrieved from [FRED — {series}](https://fred.stlouisfed.org/series/{series}).")
    st.caption('Observation dates are not publication dates. Both histories can be revised. API real-time dates select data vintages, not the chart’s observation start. When several vintages exist for a month, the latest available value is displayed. These indicators are context, not a combined forecast or guarantee.')
