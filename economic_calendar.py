"""Investing.com iframe dashboard; legacy collectors retained for compatibility."""
import os
import streamlit as st
import json
from macro_snapshots import with_snapshot
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
        'importance':'3', 'countries':'5', 'calType':'week', 'timeZone':'8', 'lang':'1',
        'features':'timezone', 'ecoDayBackground':'#E5E7EB','defaultFont':'#111827',
        'innerBorderColor':'#CBD5E1','borderColor':'#CBD5E1','ecoDayFontColor':'#111827'})


def calendar_embed():
    # The provider controls the cross-origin document. Filter the whole iframe,
    # including its white body/rows, instead of changing only header/text colors.
    from html import escape
    return '<style>html,body{margin:0;background:#06101A}iframe{width:100%;height:520px;border:0;filter:invert(.94) hue-rotate(180deg);color-scheme:light}</style><iframe title="United States high-importance economic calendar" src="'+escape(calendar_url(),quote=True)+'"></iframe>'



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


def parse_trading_economics(text):
    payload=json.loads(text)
    if not isinstance(payload,list):raise ValueError('Expected a calendar event array')
    events=[]
    for row in payload:
        if row.get('Country')!='United States' or int(row.get('Importance') or 0)!=3:continue
        stamp=datetime.fromisoformat(row['Date'].replace('Z','+00:00'))
        if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
        events.append({'id':str(row.get('CalendarId') or row.get('CalendarID') or row['Event']+row['Date']),
            'timestamp':stamp.isoformat(),'country':'United States','importance':3,'event':str(row['Event']),
            'actual':str(row.get('Actual') or ''),'forecast':str(row.get('Forecast') or ''),'previous':str(row.get('Previous') or ''),
            'impact':'neutral','time_label':'Tentative' if row.get('DateSpan') not in (None,0,'0') else ''})
    return sorted(events,key=lambda event:event['timestamp'])


def load_calendar(provider='Investing.com',force=False):
    if provider=='Trading Economics API':
        key='trading_economics_us_week';token=os.getenv('TRADING_ECONOMICS_API_KEY','').strip()
        if not token:
            result={'data':[],'status':'Unavailable','retrieved_at':None,'error':'TRADING_ECONOMICS_API_KEY is not configured'}
        else:
            _,start,end=week_events([])
            # Include adjacent UTC dates, then strictly filter the week in ET.
            url=f'https://api.tradingeconomics.com/calendar/country/united%20states/{start-timedelta(days=1)}/{end+timedelta(days=1)}'
            result=cached_download(key,url,parse_trading_economics,300,force,
                params={'c':token,'importance':3,'f':'json'})
    else:
        key='investing_us_week'
        result=cached_download(key,calendar_url(),parse_calendar,300,force)
    return with_snapshot(key,result)


def earnings_calendar_url():
    # User-requested economic-widget parameters; provider support on this
    # full-page earnings endpoint is unverified. Do not claim enforced filters.
    from urllib.parse import parse_qsl, urlsplit
    params = dict(parse_qsl(urlsplit(calendar_url()).query))
    params['importance'] = '2,3'
    return 'https://www.investing.com/earnings-calendar/?' + urlencode(params)


def earnings_embed(top_crop=250, bottom_crop=65):
    # Visual clipping only: cross-origin provider DOM cannot be edited here.
    top_crop = max(0, min(450, int(top_crop)))
    bottom_crop = max(0, min(150, int(bottom_crop)))
    inner_height = (520 + top_crop + bottom_crop) / .8
    return (
        '<style>html,body{margin:0;background:#06101A}'
        '.earnings-frame{position:relative;width:100%;height:520px;overflow:hidden}'
        'iframe{position:absolute;left:0;top:-'+str(top_crop)+'px;display:block;'
        'width:125%;height:'+str(inner_height)+'px;border:0;transform:scale(.8);'
        'transform-origin:top left;filter:invert(.94) hue-rotate(180deg);color-scheme:light}'
        '</style><div class="earnings-frame"><iframe title="Investing.com earnings calendar" sandbox="allow-scripts allow-same-origin allow-forms" '
        'src="'+escape(earnings_calendar_url(),quote=True)+'"></iframe></div>'
    )


def calendar_panel():
    """Switch locally: no WebSocket, callback, fragment, or app rerun required."""
    _, week_start, week_end = week_events([])
    config = json.dumps({'economic': calendar_embed(), 'earnings': earnings_embed(), 'week': f'{week_start:%b %d} – {week_end:%b %d, %Y}'}).replace('<', r'\u003c')
    return r'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{margin:0;background:#06101a;color:#e2e8f0;font:14px system-ui,sans-serif}
h2{font-size:22px;margin:0 0 12px}p{color:#91a4b1;line-height:1.5}
button{padding:12px 18px;border:1px solid #3b4c5b;border-radius:10px;background:#0b1a2a;color:#e2e8f0;cursor:pointer;margin-bottom:16px;font:inherit;touch-action:manipulation}
button:focus-visible{outline:2px solid #37dc89}iframe{width:100%;height:525px;border:0;display:block}a{color:#64baff}
</style></head><body>
<h2 id="title"></h2><p id="description"></p>
<button id="switch" type="button"></button>
<details id="crop" hidden><summary>Adjust calendar view</summary><p>Visual cropping only. Set to zero to restore hidden controls.</p><label>Top crop <input id="top" type="range" min="0" max="450" step="5" value="250"></label><label>Bottom crop <input id="bottom" type="range" min="0" max="150" step="5" value="65"></label></details><div id="calendar"></div><p><a id="source" target="_blank" rel="noopener noreferrer">Calendar provided by Investing.com</a></p>
<script>
const documents=CONFIG;
let active='economic';
const button=document.getElementById('switch');
function showCalendar(destination){
 active=destination;
 const earnings=destination==='earnings';
 document.getElementById('title').textContent=earnings?'Earnings calendar — '+documents.week:'This week’s U.S. economic calendar — ★★★ high importance';
 document.getElementById('description').textContent=earnings?'Choose This Week inside the calendar to show this week’s reports. If that control is hidden, set Top crop to zero in Adjust calendar view. U.S. and two/three-star filters must be verified there; the provider may ignore URL settings.':'United States · three-star importance · announcement times default to Eastern Time.';
 button.textContent=earnings?'← Back to Economic Calendar':'📊 Show Earnings Calendar';
 button.setAttribute('aria-label',button.textContent);
 const frame=document.createElement('iframe');
 frame.title=earnings?'Earnings calendar':'Economic calendar';
 let markup=documents[destination];
 if(earnings){
  const top=Number(document.getElementById('top').value), bottom=Number(document.getElementById('bottom').value);
  markup=markup.replace('top:-250px','top:-'+top+'px').replace('height:1043.75px','height:'+((520+top+bottom)/.8)+'px');
 }
 document.getElementById('crop').hidden=!earnings;
 frame.srcdoc=markup;
 document.getElementById('calendar').replaceChildren(frame);
 document.getElementById('source').href=earnings?'https://www.investing.com/earnings-calendar/':'https://www.investing.com/economic-calendar/';
}
button.addEventListener('click',()=>showCalendar(active==='earnings'?'economic':'earnings'));
document.getElementById('top').addEventListener('change',()=>showCalendar(active));
document.getElementById('bottom').addEventListener('change',()=>showCalendar(active));
showCalendar('economic');
</script></body></html>'''.replace('CONFIG',config)


def render_economic_calendar():
    import streamlit.components.v1 as components
    components.html(calendar_panel(), height=780, scrolling=True)
