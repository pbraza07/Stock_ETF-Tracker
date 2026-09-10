"""Native FRED charts; monthly observations, never third-party page embeds."""
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
import pandas as pd
from macro_data import cached_download

SERIES = {
    'USPHCI': {
        'name':'Coincident Economic Activity Index for the United States',
        'units':'Index (2007 = 100)', 'source':'Federal Reserve Bank of Philadelphia',
        'color':'#38BDF8',
        'explanation':'This monthly index combines nonfarm payroll employment, unemployment, manufacturing hours, and wages and salaries. A rising line indicates increasing economic activity; a sustained falling line indicates weakening activity. The level 100 is the 2007 reference level, not a recession threshold. It measures current conditions rather than predicting a recession on its own.',
    },
    'SAHMREALTIME': {
        'name':'Real-time Sahm Rule Recession Indicator',
        'units':'Percentage points', 'source':'Claudia Sahm', 'color':'#A78BFA',
        'explanation':'The Sahm Rule compares the three-month average unemployment rate with the lowest three-month average in the previous 12 months. A reading of 0.50 percentage points or more triggers the rule’s recession signal. The dashed line marks 0.50; a reading below it means the rule is not triggered for that month. This is not a recession probability or an official recession declaration. “Real-time” refers to the unemployment data available in each historical month; the series is updated monthly, not continuously.',
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
    if frame.empty:
        raise ValueError('FRED returned no valid observations')
    frame['date'] = frame.date.dt.strftime('%Y-%m-%d')
    return frame.to_dict('records')


def load_series(series, force=False, cache_dir=None):
    if series not in SERIES:
        raise ValueError('Unknown recession indicator')
    return cached_download(series, f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}',
                           lambda text:parse_fred(text,series), 6*3600, force, cache_dir)


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
        hovertemplate='%{x|%b %Y}<br>%{y:.2f}<extra></extra>'))
    if series=='SAHMREALTIME':
        fig.add_hline(y=.5,line_color='#FB7185',line_dash='dash',annotation_text='Sahm threshold: 0.50 pp',annotation_font_color='#FB7185')
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
            st.warning('FRED data are temporarily unavailable. Use Refresh recession data to retry.')
        else:
            if result['status']=='Stale cache':
                st.warning('The refresh failed. Showing the last valid downloaded observations; these may be outdated.')
            records=result['data'];last=records[-1];date=pd.Timestamp(last['date']).strftime('%b %Y')
            a,b,c=st.columns(3)
            a.metric('Latest observation',f"{last['value']:.2f}"+(' pp' if series=='SAHMREALTIME' else ''))
            b.metric('Observation month',date)
            if series=='SAHMREALTIME':
                c.metric('Sahm threshold', 'Triggered' if last['value']>=.5 else 'Not triggered')
            else:
                lookup={row['date']:row['value'] for row in records}
                prior=lookup.get((pd.Timestamp(last['date'])-pd.DateOffset(months=1)).strftime('%Y-%m-%d'))
                c.metric('Monthly change',f"{(last['value']/prior-1)*100:+.2f}%" if prior else 'Unavailable')
            st.caption(f"{result['status']} · Downloaded {result['retrieved_at']} · Monthly, seasonally adjusted")
            st.plotly_chart(indicator_figure(series,records,years),width='stretch',key=f'fred_{series}')
            with st.expander(f'View {series} observations / download'):
                frame=pd.DataFrame(records).rename(columns={'date':'Observation date','value':spec['units']})
                st.dataframe(frame.iloc[::-1],hide_index=True,width='stretch')
                st.download_button('Download CSV',frame.to_csv(index=False),f'{series}.csv','text/csv',key=f'csv_{series}')
        st.markdown('**How to read this graph:** '+spec['explanation'])
        st.markdown(f"Source: {spec['source']}, retrieved from [FRED — {series}](https://fred.stlouisfed.org/series/{series}).")
    st.caption('Observation dates are not publication dates. USPHCI history can be revised; Sahm uses the real-time series supplied by FRED. These indicators are context, not a combined forecast or guarantee.')
