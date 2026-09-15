"""Server-generated recession charts: no browser chart library required."""
from html import escape
import math
import pandas as pd
from recession_shading import PERIODS


def indicator_svg(series, records, years=10):
    from recession_indicators import SERIES
    spec = SERIES[series]
    frame = pd.DataFrame(records)
    frame['date'] = pd.to_datetime(frame['date'])
    frame = frame.sort_values('date').drop_duplicates('date', keep='last')
    if years:
        frame = frame[frame.date >= frame.date.max()-pd.DateOffset(years=years)]
    frame = frame.set_index('date').asfreq('MS').reset_index()
    values = [float(v) for v in frame.value if pd.notna(v) and math.isfinite(float(v))]
    if not values:
        raise ValueError('No finite observations to chart')
    start, end = frame.date.min(), frame.date.max()
    span = max((end-start).total_seconds(), 86400)
    lo, hi = min(values), max(values)
    if series == 'RECPROUSM156N':
        lo, hi = 0, 100
    else:
        if series == 'SAHMREALTIME': lo, hi = min(lo,.5), max(hi,.5)
        pad = max((hi-lo)*.08, .1)
        lo, hi = lo-pad, hi+pad
    def x(d): return 90+((pd.Timestamp(d)-start).total_seconds()/span)*890
    def y(v): return 310-(float(v)-lo)/(hi-lo)*270
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 380" role="img">',
           f'<title>{escape(spec["name"])} — historical recession periods shaded red</title>',
           '<rect width="1000" height="380" fill="#06101A"/>',
           '<rect x="90" y="40" width="890" height="270" fill="#091825"/>']
    def text(px,py,label,anchor='start',color='#E2E8F0',size=13):
        svg.append(f'<text x="{px:.2f}" y="{py:.2f}" text-anchor="{anchor}" fill="{color}" font-family="Arial, sans-serif" font-size="{size}">{escape(str(label))}</text>')
    text(90,23,spec['units'])
    for a,b in PERIODS:
        a,b=max(start,pd.Timestamp(a)),min(end,pd.Timestamp(b))
        if a<=b:
            svg.append(f'<rect x="{x(a):.2f}" y="40" width="{max(x(b)-x(a),1):.2f}" height="270" fill="#F87171" fill-opacity="0.20"><title>Historical recession: {a:%b %Y} – {b:%b %Y}</title></rect>')
    for i in range(6):
        v=lo+(hi-lo)*i/5
        svg.append(f'<path d="M90 {y(v):.2f} H980" stroke="#20394A"/>')
        text(80,y(v)+4,f'{v:,.2f}'+('%' if series=='RECPROUSM156N' else ''),'end')
        d=start+(end-start)*i/5
        text(x(d),335,f'{d:%b %Y}','middle',size=12)
    if series=='SAHMREALTIME':
        svg.append(f'<path d="M90 {y(.5):.2f} H980" stroke="#FB7185" stroke-dasharray="6 4"/>')
        text(975,y(.5)-7,'Sahm threshold: 0.50 pp','end','#FB7185')
    segments=[]; segment=[]
    for row in frame.itertuples():
        if pd.isna(row.value) or not math.isfinite(float(row.value)):
            if segment: segments.append(segment); segment=[]
        else: segment.append((x(row.date), y(row.value)))
    if segment: segments.append(segment)
    for segment in segments:
        if len(segment)==1:
            px,py=segment[0];svg.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="3" fill="{spec["color"]}"/>')
        else:
            path=' '.join(('M' if i==0 else 'L')+f'{px:.2f},{py:.2f}' for i,(px,py) in enumerate(segment))
            svg.append(f'<path d="{path}" fill="none" stroke="{spec["color"]}" stroke-width="2.5"/>')
    text(535,367,'Observation month','middle')
    return ''.join(svg)+'</svg>'
