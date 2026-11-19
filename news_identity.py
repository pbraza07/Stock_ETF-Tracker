"""Identify tracked stocks in visible article headings and opening paragraphs."""
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from market_news import bounded_get, canonical_url
from news_context import matches, securities
from scraped_news import SITES
from shared_cache import cached

PUBLISHERS = [urlsplit(url).hostname.removeprefix("www.") for url, _ in SITES.values()]
PUBLISHERS += ["reuters.com", "wsj.com", "foxbusiness.com", "bloomberg.com", "cnbc.com", "nytimes.com"]


def opening_symbols(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("nav, aside, footer, script, style, [hidden], [aria-hidden=true]"):
        tag.decompose()
    heading = soup.select_one("article h1, main h1, h1")
    body = soup.select_one('[itemprop="articleBody"], .article-body, .article__body, #article-body, article, main')
    first = body.select_one("p") if body else None
    text = " ".join(tag.get_text(" ", strip=True) for tag in (heading, first) if tag)
    return [symbol for symbol, name, _ in securities() if matches(text, symbol, name)]


def article_symbols(url):
    if not canonical_url(url, PUBLISHERS):
        return []
    def load():
        return opening_symbols(bounded_get(url, PUBLISHERS, accept="text/html"))
    return cached("news-opening-symbols-v1", (url,), load, ttl=86400, default=[], background=True)
