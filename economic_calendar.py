"""Collect Investing.com events and render a native MarketScope calendar."""
from datetime import datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from macro_data import cached_download

ET = ZoneInfo('America/New_York')


def calendar_url():
    return 'https://sslecal2.investing.com/?'+urlencode({
        'columns':'exc_flags,exc_currency,exc_importance,exc_actual,exc_forecast,exc_previous',
        'importance':'3','countries':'5','calType':'week','timeZone':'8','lang':'1'})


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__();self.rows=[];self.row=None;self.cell=None;self.valid_table=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs);classes=attrs.get('class','').split()
        if tag=='table' and 'ecoCalTable' in classes:self.valid_table=True
        if tag=='tr':
            self.row={'id':attrs.get('id',''),'timestamp':attrs.get('event_timestamp'),'country':'','importance':0,'cells':{}} if attrs.get('id','').startswith('eventRowId_') else None
        if self.row is None:return
        if tag=='td':
            key=next((x for x in ('time','flagCur','sentiment','event','act','fore','prev') if x in classes),None)
            self.cell={'key':key,'text':[],'classes':classes}
        if tag=='span' and 'flagCur'==((self.cell or {}).get('key')):
            self.row['country']=attrs.get('title',self.row['country'])
        if tag=='i' and (self.cell or {}).get('key')=='sentiment' and 'grayFullBullishIcon' in classes:
            self.row['importance']+=1
    def handle_data(self,data):
        if self.row is not None and self.cell is not None:self.cell['text'].append(data)
    def handle_endtag(self,tag):
        if tag=='td' and self.row is not None and self.cell is not None:
            cell=self.cell;cell['text']=' '.join(''.join(cell['text']).split())
            self.row['cells'][cell['key']]=cell;self.cell=None
        if tag=='tr' and self.row is not None:
            self.rows.append(self.row);self.row=None;self.cell=None


def parse_calendar(text):
    parser=CalendarParser();parser.feed(text)
    if not parser.valid_table:raise ValueError('Investing.com calendar markup unavailable')
    events=[]
    for row in parser.rows:
        if row['country']!='United States' or row['importance']!=3:continue
        cells=row['cells'];name=cells.get('event',{}).get('text','')
        if not row['timestamp'] or not name:raise ValueError('High-importance event is missing its date or name')
        # Provider timestamps are UTC; display dates/times are converted with DST.
        stamp=datetime.fromisoformat(row['timestamp']).replace(tzinfo=timezone.utc)
        actual=cells.get('act',{})
        events.append({'id':row['id'],'timestamp':stamp.isoformat(),'country':'United States','importance':3,
            'event':name,'actual':actual.get('text',''),'forecast':cells.get('fore',{}).get('text',''),
            'previous':cells.get('prev',{}).get('text',''),
            'impact':'positive' if 'greenFont' in actual.get('classes',[]) else 'negative' if 'redFont' in actual.get('classes',[]) else 'neutral',
            'time_label':cells.get('time',{}).get('text','')})
    return sorted({event['id']:event for event in events}.values(),key=lambda event:event['timestamp'])


def week_events(events,now=None):
    now=now or datetime.now(ET)
    today=now.astimezone(ET).date();start=today-timedelta(days=today.weekday());end=start+timedelta(days=7)
    selected=[event for event in events if event.get('country')=='United States' and event.get('importance')==3
              and start<=datetime.fromisoformat(event['timestamp']).astimezone(ET).date()<end]
    return selected,start,end-timedelta(days=1)


def calendar_table(events):
    html=['<style>.ms-economic{overflow-x:auto;border:1px solid #27465A;border-radius:12px;background:#091825}.ms-economic table{border-collapse:collapse;width:100%;min-width:760px;font-family:inherit;color:#E2E8F0}.ms-economic th{background:#0C2530;color:#68D7FF;font-size:12px;text-align:left}.ms-economic th,.ms-economic td{padding:12px;border-bottom:1px solid #20394A}.ms-economic tr:nth-child(even){background:#0C1C2B}.ms-economic .positive{color:#4ADE80}.ms-economic .negative{color:#FB7185}.ms-economic .neutral{color:#E2E8F0}.ms-economic .stars{color:#FBBF24;white-space:nowrap}</style><div class="ms-economic"><table><thead><tr>']
    html.extend(f'<th>{name}</th>' for name in ['Date','Announcement (ET)','U.S. event','Importance','Actual','Forecast','Previous'])
    html.append('</tr></thead><tbody>')
    for event in events:
        stamp=datetime.fromisoformat(event['timestamp']).astimezone(ET)
        label=event.get('time_label','').lower()
        time='Tentative / all day' if 'tentative' in label or 'all day' in label else stamp.strftime('%I:%M %p %Z')
        values=[stamp.strftime('%a, %b %d, %Y'),time,event['event'],'★★★',event['actual'] or '—',event['forecast'] or '—',event['previous'] or '—']
        html.append('<tr>')
        for i,value in enumerate(values):
            cls='stars' if i==3 else event.get('impact','neutral') if i==4 else 'neutral'
            if cls not in ('stars','positive','negative','neutral'):cls='neutral'
            html.append(f'<td class="{cls}">{escape(str(value))}</td>')
        html.append('</tr>')
    html.append('</tbody></table></div>')
    return ''.join(html)


def render_economic_calendar():
    import streamlit as st
    st.subheader('This week’s U.S. economic calendar — ★★★ high importance')
    refresh=st.button('Refresh economic calendar',key='refresh_economic_calendar')
    result=cached_download('investing_us_week',calendar_url(),parse_calendar,300,refresh)
    events,start,end=week_events(result['data'])
    st.caption(f'{start:%b %d} – {end:%b %d, %Y} · United States only · Announcement times: Eastern Time (automatic daylight-saving adjustment)')
    if result['status']=='Unavailable':
        st.warning('Investing.com event data are temporarily unavailable. Refresh to retry; no events have been invented.')
    else:
        if result['status']=='Stale cache':st.warning('Refresh failed. Showing cached events for this week; announcement times or results may have changed.')
        st.caption(f"{result['status']} · Downloaded {result['retrieved_at']}")
        if events:st.markdown(calendar_table(events),unsafe_allow_html=True)
        else:st.info('No U.S. three-star events for this week are present in the downloaded data.')
    st.markdown('Source: [Investing.com Economic Calendar](https://www.investing.com/economic-calendar/). Three stars indicate high expected market impact. Actual/Forecast/Previous values retain their source units; actual-value colors follow the provider’s assessment, not simply whether a number is positive or negative.')
