"""Source-attributed RSS news and explainable, non-predictive market context.

No paywall scraping, LLM API, invented news, or implied full-article analysis.
"""
from __future__ import annotations

import hashlib
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import requests
from bs4 import BeautifulSoup

SOURCES = [
    dict(id='cnbc_markets', name='CNBC · Markets', publisher='CNBC', url='https://www.cnbc.com/id/100003114/device/rss/rss.html', domains=['cnbc.com']),
    dict(id='cnbc_economy', name='CNBC · Economy', publisher='CNBC', url='https://www.cnbc.com/id/20910258/device/rss/rss.html', domains=['cnbc.com']),
    dict(id='bbc', name='BBC · Business', publisher='BBC', url='https://feeds.bbci.co.uk/news/business/rss.xml', domains=['bbc.com','bbc.co.uk']),
    dict(id='guardian', name='The Guardian · Business', publisher='The Guardian', url='https://www.theguardian.com/business/rss', domains=['theguardian.com']),
    dict(id='ft', name='Financial Times · Markets', publisher='Financial Times', url='https://www.ft.com/markets?format=rss', domains=['ft.com']),
    dict(id='wsj', name='The Wall Street Journal · Markets', publisher='The Wall Street Journal', url='https://feeds.content.dowjones.io/public/rss/RSSMarketsMain', domains=['wsj.com']),
    dict(id='marketwatch', name='MarketWatch · Top stories', publisher='MarketWatch', url='https://feeds.content.dowjones.io/public/rss/mw_topstories', domains=['marketwatch.com']),
    dict(id='yahoo', name='Yahoo Finance', publisher='Yahoo Finance', url='https://finance.yahoo.com/news/rssindex', domains=['finance.yahoo.com']),
    dict(id='fed', name='Federal Reserve · Releases', publisher='Federal Reserve', url='https://www.federalreserve.gov/feeds/press_all.xml', domains=['federalreserve.gov'], official=True),
    dict(id='bls', name='BLS · Economic releases', publisher='Bureau of Labor Statistics', url='https://www.bls.gov/feed/bls_latest.rss', domains=['bls.gov'], official=True),
    dict(id='bea', name='BEA · Economic releases', publisher='Bureau of Economic Analysis', url='https://apps.bea.gov/rss/rss.xml', domains=['bea.gov'], official=True),
    dict(id='ecb', name='ECB · Press releases', publisher='European Central Bank', url='https://www.ecb.europa.eu/rss/press.html', domains=['ecb.europa.eu']),
    dict(id='investing', name='Investing.com · Stock markets', publisher='Investing.com', url='https://www.investing.com/rss/news_25.rss', domains=['investing.com']),
]
SOURCE_BY_ID = {s['id']: s for s in SOURCES}

TOPICS = [
    ('Rates & central banks', r'\b(fed|fomc|ecb|central bank|interest rates?|treasur\w*|bond yields?|monetary)\b',
     'Interest rates affect financing costs and the discount rate applied to future profits.'),
    ('Inflation', r'\b(inflation|cpi|pce|consumer prices?|producer prices?)\b',
     'Inflation can change purchasing power, margins and the expected path of interest rates.'),
    ('Growth & jobs', r'\b(gdp|growth|recession|payrolls?|unemployment|jobs|employment|retail sales)\b',
     'Growth and labor demand influence earnings, spending and recession risk.'),
    ('Earnings & companies', r'\b(earnings|profits?|revenue|guidance|companies|company|chip\w*|ai|nvidia|apple|microsoft)\b',
     'Earnings and guidance affect equity valuations; one company may not represent the market.'),
    ('Trade & geopolitics', r'\b(tariffs?|trade|war|sanctions?|geopolit\w*|conflict)\b',
     'Trade and geopolitical changes can affect costs, supply chains and risk appetite.'),
    ('Energy & commodities', r'\b(oil|gas|energy|opec|gold|commodit\w*)\b',
     'Commodity prices affect inflation and margins differently across sectors.'),
    ('Market prices & credit', r'\b(stocks?|s&p|nasdaq|dow|equities|wall street|markets?|bonds?|credit|bank\w*)\b',
     'Prices and credit conditions show risk appetite; reported moves do not establish the next move.'),
]
# Intentionally narrow rules. Negations, forecasts/questions and conflicting clues abstain.
RULES = [
    ('bullish', r'\b(?:stocks|equities|s&p 500|nasdaq|dow|stock futures)\b.{0,30}\b(?:rise|rises|rally|rallies|surge|surges|gain|gains|climb|climbs)\b', 'The headline reports a positive equity-market move.', 'reported move'),
    ('bearish', r'\b(?:stocks|equities|s&p 500|nasdaq|dow|stock futures)\b.{0,30}\b(?:fall|falls|drop|drops|plunge|plunges|slide|slides|tumble|tumbles)\b', 'The headline reports a negative equity-market move.', 'reported move'),
    ('bullish', r'\b(?:raises?|lifts?|raised)\b.{0,20}\b(?:earnings|profit|revenue) (?:outlook|forecast|guidance)\b', 'Stronger earnings guidance can support the affected shares, all else equal.', 'potential catalyst'),
    ('bearish', r'\b(?:cuts?|lowers?|slashed)\b.{0,20}\b(?:earnings|profit|revenue) (?:outlook|forecast|guidance)\b', 'Weaker earnings guidance can pressure the affected shares, all else equal.', 'potential catalyst'),
    ('bullish', r'\binflation\b.{0,20}\b(?:slows|cools|eases)\b', 'Cooling inflation can ease rate pressure; weak demand could offset that benefit.', 'potential catalyst'),
    ('bearish', r'\binflation\b.{0,20}\b(?:accelerates|surges|jumps)\b', 'Rising inflation can pressure margins and interest-rate expectations.', 'potential catalyst'),
    ('bearish', r'\b(?:files? for bankruptcy|credit crisis|debt default|bank failure)\b', 'Financial distress can increase credit risk; wider-market effects depend on exposure.', 'potential catalyst'),
]


def utcnow():
    return datetime.now(timezone.utc)


def plain(value):
    soup = BeautifulSoup(str(value or '')[:200_000], 'html.parser')
    for tag in soup(['script','style','noscript']):
        tag.decompose()
    return ' '.join(unescape(soup.get_text(' ')).split())


def canonical_url(url, domains=None):
    try:
        parsed = urlsplit(str(url).strip())
        host = (parsed.hostname or '').lower()
        if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            return ''
        if domains and not any(host == d or host.endswith('.'+d) for d in domains):
            return ''
        if not host or host in ('localhost', '127.0.0.1'):
            return ''
        query = [(k,v) for k,v in parse_qsl(parsed.query) if not k.lower().startswith('utm_') and k.lower() not in ('guccounter','gucereferrer','gucereferrersig','cmpid','ocid')]
        return urlunsplit(('https', host, parsed.path or '/', urlencode(query), ''))
    except ValueError:
        return ''


def timestamp(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (ValueError, TypeError, OverflowError):
        try:
            dt = datetime.fromisoformat(value.replace('Z','+00:00'))
        except (ValueError, TypeError):
            return None
    # Unknown timezone must not be falsely reported as UTC.
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def classify(title):
    lower = title.lower()
    topics = [name for name, pattern, _ in TOPICS if re.search(pattern, lower)]
    channel = next((why for name, _, why in TOPICS if name in topics), 'The broader market effect is not clear from this feed item.')
    ambiguous = bool(re.search(r'\b(not|no|never|denies|unlikely|could|may|might|would|will|forecast|expected|expects|predicts)\b|\?',lower))
    hits = [] if ambiguous else [(direction, why, kind) for direction, pattern, why, kind in RULES if re.search(pattern,lower)]
    directions = {x[0] for x in hits}
    direction = next(iter(directions)) if len(directions)==1 else 'mixed' if len(directions)>1 else 'unclear'
    reasons = list(dict.fromkeys(x[1] for x in hits))
    reason = ' '.join(reasons) if reasons else 'No unambiguous directional signal in the headline. Open the source for context.'
    return dict(direction=direction, reason=reason, topics=topics or ['Other business news'], channel=channel,
                basis='headline rules v1', confidence='LOW', signal_kind=' / '.join(sorted({x[2] for x in hits})) or 'unclassified')


def make_item(title, description, url, published, source, retrieved=None):
    title = plain(title)[:500]
    url = canonical_url(url, source['domains'])
    if not title or not url:
        return None
    retrieved = retrieved or utcnow().isoformat()
    analysis = classify(title)
    # Publisher text is an explicitly attributed short feed excerpt, not a full transcript.
    excerpt = ' '.join(plain(description).split()[:25])
    summary = [excerpt or 'This source supplied a headline without a feed description.',
               analysis['channel'], analysis['reason']]
    return dict(id=hashlib.sha256(url.encode()).hexdigest()[:24], url=url, title=title, excerpt=excerpt,
                summary=summary, publisher=source['publisher'], source_id=source['id'], published_at=timestamp(published),
                first_seen_at=retrieved, last_seen_at=retrieved, analysis=analysis,
                content_scope='Feed excerpt and MarketScope context; linked article not analyzed',
                headline_group=hashlib.sha256(re.sub(r'\W+', '',title.lower()).encode()).hexdigest()[:20])


def parse_feed(data, source, retrieved=None):
    if len(data)>2_000_000 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('Unsafe or oversized XML feed')
    root = ET.fromstring(data)
    local = lambda tag: tag.rsplit('}',1)[-1]
    if local(root.tag) not in ('rss','feed','RDF'):
        raise ValueError('Response is not RSS or Atom')
    rows = []
    for node in (n for n in root.iter() if local(n.tag) in ('item','entry')):
        fields = {}
        for child in node:
            name = local(child.tag)
            if name=='link':
                if child.attrib.get('rel','alternate')=='alternate':
                    fields['link'] = child.attrib.get('href') or child.text or ''
            elif name in ('title','description','summary','pubDate','published','updated','date'):
                fields[name] = ''.join(child.itertext())
        item = make_item(fields.get('title'), fields.get('description') or fields.get('summary'), fields.get('link'),
                         fields.get('pubDate') or fields.get('published') or fields.get('date') or fields.get('updated'), source, retrieved)
        if item:
            rows.append(item)
    return list({row['id']:row for row in rows}.values())


def bounded_get(url, allowed_domains):
    """Only curated public sources, bounded responses, no redirects to arbitrary hosts."""
    started = time.monotonic()
    for _ in range(4):
        if not canonical_url(url, allowed_domains):
            raise ValueError('Source redirected outside its allowed domains')
        with requests.get(url, timeout=(3,6), stream=True, allow_redirects=False,
                          headers={'User-Agent':'MarketScope/5.11.48 RSS reader', 'Accept':'application/rss+xml, application/atom+xml, text/xml, text/html'}) as response:
            if response.status_code in (301,302,303,307,308):
                from urllib.parse import urljoin
                url = urljoin(url, response.headers.get('Location',''))
                continue
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_content(16384):
                data.extend(chunk)
                if len(data)>2_000_000 or time.monotonic()-started>18:
                    raise ValueError('Source response exceeded size/time limit')
            return bytes(data)
    raise ValueError('Too many source redirects')


def fetch_source(source):
    fetched = utcnow().isoformat()
    try:
        feed_host = urlsplit(source['url']).hostname
        data = bounded_get(source['url'], list(set(source['domains']+[feed_host])))
        items = parse_feed(data, source, fetched)
        return items, dict(source_id=source['id'], name=source['name'], status='OK' if items else 'EMPTY',
                           attempted_at=fetched, last_success_at=fetched, count=len(items), error='')
    except Exception as exc:
        # Never include request headers, credentials or potentially huge HTML in diagnostics.
        status = getattr(getattr(exc,'response',None),'status_code',None)
        error = f'HTTP {status}' if status else type(exc).__name__
        return [], dict(source_id=source['id'],name=source['name'],status='UNAVAILABLE',attempted_at=fetched,count=0,error=error)


def collect(sources=None, progress=None):
    sources = SOURCES if sources is None else sources
    items, statuses = [], {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        pending = {executor.submit(fetch_source, source):source for source in sources}
        for done, future in enumerate(as_completed(pending),1):
            rows, status = future.result()
            items.extend(rows); statuses[status['source_id']]=status
            if progress:
                progress(done,len(sources),status['name'])
    return items, statuses


def official_release(item):
    """Only original U.S. federal release bodies; commercial articles stay at source."""
    source = SOURCE_BY_ID.get(item['source_id'],{})
    if not source.get('official'):
        raise ValueError('Full text is not enabled for this publisher')
    url = canonical_url(item['url'],source['domains'])
    path = urlsplit(url).path.lower()
    if not any(part in path for part in ('pressreleases/','news.release/','/news/')):
        raise ValueError('Only original agency release pages are eligible')
    data = bounded_get(url,source['domains'])
    soup = BeautifulSoup(data,'html.parser')
    body = soup.select_one('#article, .col-xs-12.col-sm-8.col-md-8, .field--name-body, #bodytext, article')
    if body is None:
        raise ValueError('Release body could not be identified; use the original link')
    for tag in body(['script','style','nav','footer','aside','form']):
        tag.decompose()
    text = '\n\n'.join(line.strip() for line in body.get_text('\n').splitlines() if line.strip())
    if len(text)<120:
        raise ValueError('No readable release body returned')
    return dict(text=text[:100_000], truncated=len(text)>100_000, retrieved_at=utcnow().isoformat(),url=url,
                rights='Original U.S. federal agency release; attribution retained')
