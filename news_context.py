"""Story-specific context with independent security, sector and market scope.

No signal is propagated from one company to its sector or the whole market.
"""
import csv
from functools import lru_cache
from pathlib import Path
import re
from html import escape

from market_news import classify, plain

SECTORS={
 'Technology':r'\b(?:technology (?:stocks|shares|sector)|tech (?:stocks|shares|sector)|chipmakers|semiconductor (?:stocks|sector))\b',
 'Financials':r'\b(?:bank (?:stocks|shares)|banks|financial (?:stocks|sector))\b',
 'Energy':r'\b(?:energy (?:stocks|shares|sector)|oil (?:stocks|companies))\b',
 'Healthcare':r'\b(?:healthcare|health care|biotech|pharmaceutical) (?:stocks|shares|sector)\b',
 'Consumer Discretionary':r'\b(?:retail|consumer discretionary|automaker) (?:stocks|shares|sector)\b',
 'Consumer Staples':r'\bconsumer staples\b',
 'Industrials':r'\bindustrial (?:stocks|shares|sector)\b',
 'Utilities':r'\butilities (?:stocks|shares|sector)\b',
 'Real Estate':r'\b(?:real estate (?:stocks|sector)|reits)\b',
 'Communication Services':r'\b(?:communication services|telecom (?:stocks|sector))\b',
 'Materials':r'\b(?:materials|mining) (?:stocks|shares|sector)\b',
}


@lru_cache(maxsize=2)
def _universe(path,mtime):
    with open(path,encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    result=[]
    for row in rows:
        if row.get('Type') not in ('Stock',None,''):continue
        name=row.get('Name','')
        name=re.split(r'\b(?:Inc\.?|Corporation|Corp\.?|PLC|plc|Ltd\.?|Limited|Class|Common|Ordinary|American Depositary)\b',name)[0].strip(' ,.-')
        if len(name)<4:continue
        if name=='Amazon.com':name='Amazon'
        result.append((row.get('Symbol',''),name,row.get('Sector') or 'Sector unavailable'))
    return result


def securities():
    path=Path(__file__).parent/'data/default_universe.csv'
    try:return _universe(str(path),path.stat().st_mtime_ns)
    except (OSError,ValueError):return []


def matches(text,symbol,name):
    # Ambiguous ordinary words are not identified as tickers unless explicitly marked.
    ticker=bool(re.search(r'(?:\$|\b(?:NASDAQ|NYSE):\s*)'+re.escape(symbol)+r'\b',text))
    if len(symbol)>=3 and symbol not in {'ALL','ARE','NOW','ONE','FOR','USA','CEO','GDP','CPI','CAT'}:
        ticker=ticker or bool(re.search(r'(?<!\w)'+re.escape(symbol)+r'(?!\w)',text))
    return ticker or bool(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',text,re.I))


def result(name,text,reason_if_unknown):
    analysis=classify(text)
    return dict(name=name,direction=analysis['direction'],reason=analysis['reason'] if analysis['direction']!='unclear' else reason_if_unknown,
                evidence=text,confidence='LOW')


def combine(name,parts,unknown):
    signals=[result(name,p,unknown) for p in parts]
    directions={x['direction'] for x in signals if x['direction']!='unclear'}
    direction=next(iter(directions)) if len(directions)==1 else 'mixed' if directions else 'unclear'
    return dict(name=name,direction=direction,reason=' '.join(dict.fromkeys(x['reason'] for x in signals if x['direction']!='unclear')) or unknown,
                evidence='; '.join(parts),confidence='LOW')


def story_context(row,universe=None):
    text=row['title']+'. '+row.get('excerpt','')
    clauses=[s.strip() for s in re.split(r'[.!?;]|\b(?:but|while|whereas)\b',text) if s.strip()]
    holdings=[]
    for symbol,name,sector in (securities() if universe is None else universe):
        if not symbol or not matches(text,symbol,name):continue
        parts=[]
        for clause in clauses:
            if matches(clause,symbol,name):
                # Only company-linked share movement or guidance is eligible.
                normalized=re.sub(re.escape(name),symbol,clause,flags=re.I)
                normalized=re.sub(r'(?<!\w)'+re.escape(symbol)+r'(?:\s+(?:stock|shares))?\b','Stocks',normalized)
                if re.search(r'\bStocks\s+(?:rise|rises|rally|rallies|surge|surges|gain|gains|climb|climbs|fall|falls|drop|drops|plunge|plunges|slide|slides|tumble|tumbles|raises?|raised|lifts?|cuts?|lowers?|slashed)\b',normalized,re.I):
                    parts.append(normalized)
        record=combine(symbol,parts,'Company mentioned; its directional effect is not established by this feed item.')
        record['reason']=record['reason'].replace('equity-market move','move in the named stock')
        record['evidence']='; '.join(c for c in clauses if matches(c,symbol,name))
        record.update(company=name,sector=sector);holdings.append(record)
    sector_names={x['sector'] for x in holdings if x['sector']!='Sector unavailable'}
    sector_names.update(name for name,pattern in SECTORS.items() if re.search(pattern,text,re.I))
    sectors=[]
    for name in sorted(sector_names):
        pattern=SECTORS.get(name)
        parts=[re.sub(pattern,'Stocks',c,flags=re.I) for c in clauses if pattern and re.search(pattern,c,re.I)]
        sectors.append(combine(name,parts,'Company-specific news does not establish a sector-wide direction.'))
    market_parts=[]
    for clause in clauses:
        broad=bool(re.search(r'\b(?:s&p(?: 500)?|nasdaq|dow|wall street|u\.s\. (?:stocks|equities)|stock market)\b',clause,re.I))
        unqualified=bool(re.match(r'\s*(?:u\.s\. )?(?:stocks|equities|stock futures)\b',clause,re.I))
        macro=bool(re.search(r'\binflation\b',clause,re.I))
        if (broad and not re.search(r'\b(?:NASDAQ|NYSE):',clause)) or unqualified or macro:market_parts.append(clause)
    market=combine('Overall U.S. market',market_parts,'No clear broad-market direction can be established from this feed item.')
    return dict(stocks=holdings,sectors=sectors,market=market,basis='Headline and short feed excerpt; scoped rules v2; LOW confidence')


def story_summary(row):
    """Specific publisher description only; generic channel text belongs in reader."""
    text=plain(row.get('excerpt','')).strip()
    if not text:return row['title']+' — No additional description was supplied by this source.'
    # Old excerpts may stop in the middle of a sentence at the original word cap.
    if text[-1] not in '.!?…':text+='…'
    return text


def impact_html(context):
    styles={'bullish':('▲','Potentially bullish','#35ec87'),'bearish':('▼','Potentially bearish','#ff667b'),
            'mixed':('↕','Mixed','#facc15'),'unclear':('↔','Neutral / unclear','#9daebe')}
    sections=[]
    for label,rows in [('Stock',context['stocks']),('Sector',context['sectors']),('Market',[context['market']])]:
        if not rows:
            rows=[dict(name='Not identified',direction='unclear',reason='No tracked '+label.lower()+' identified in this headline/excerpt.')]
        badges=[]
        for row in rows:
            arrow,status,color=styles[row['direction']]
            badges.append(f'<span title="{escape(row["reason"],quote=True)}" style="color:{color};display:inline-block;margin:3px 12px 3px 0">{arrow} {escape(row["name"])} · {status}</span>')
        sections.append('<div><b>'+label+':</b> '+' '.join(badges)+'</div>')
    return '<div style="font-size:13px;line-height:1.5;padding:8px 0">'+''.join(sections)+'<div style="color:#8ba5b6;font-size:11px">Potential impact · Low confidence · Neutral means unclear, not zero effect</div></div>'
