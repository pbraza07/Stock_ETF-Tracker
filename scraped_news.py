"""Headlines from the eight configured HTML listing pages."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from market_news import bounded_get, canonical_url

# Aggregators link directly to the original publisher. Only listing pages are fetched.
SITES = {
    "Yahoo Finance": ("https://finance.yahoo.com/news/", 'article a[href], a[href*="/news/"] h3, a[href*="/news/"] h2'),
    "MarketWatch": ("https://www.marketwatch.com/latest-news", 'h3.article__headline a, a[href*="/story/"], a[href*="/livecoverage/"]'),
    "Google Finance": ("https://www.google.com/finance/", 'a:has(.Yfwt5), article a[href], a:has(h3)'),
    "StockAnalysis.com": ("https://stockanalysis.com/news/", 'a[href^="/news/"]:not([href="/news/"]), h3 a[href]'),
    "MarketBeat": ("https://www.marketbeat.com/headlines/", 'a[href*="/articles/"], a[href*="/instant-alerts/"], a[href*="/originals/"], a[href*="/stock-ideas/"], a[href*="/videos/"]'),
    "The Motley Fool": ("https://www.fool.com/investing-news/", 'a[href*="/20"]'),
    "Finviz": ("https://finviz.com/news.ashx", "a.nn-tab-link"),
    "Stocktwits": ("https://stocktwits.com/news", 'a[href*="/news-articles/"]'),
}


def headlines(name, html):
    base, selector = SITES[name]
    soup = BeautifulSoup(html, "html.parser")
    rows = {}
    for node in soup.select(selector):
        link = node if node.name == "a" else node.find_parent("a")
        if not link or not link.get("href"):
            continue
        url = canonical_url(urljoin(base, link["href"]))
        if not url or urlsplit(url).path in ("", "/") or url.rstrip("/") == base.rstrip("/"):
            continue
        heading = node.select_one("h2,h3,h4,.Yfwt5") or node
        title = " ".join(heading.stripped_strings)
        if 18 <= len(title) <= 300:
            row = {"title": title, "url": url}
            # Use only metadata belonging to this story, never a sibling story.
            card = link.find_parent(["article", "li", "tr"])
            if card and len(card.select("h2,h3,h4")) <= 1 and len(set(
                a.get("href") for a in card.select("a[href]") if len(a.get_text(strip=True)) >= 18
            )) <= 1:
                paragraph = card.find("p")
                if paragraph:
                    excerpt = " ".join(paragraph.stripped_strings)
                    if excerpt and excerpt != title:
                        row["excerpt"] = " ".join(excerpt.split()[:25])
                        from news_context import matches, securities
                        row["listing_symbols"] = [symbol for symbol, company, _ in securities()
                                                  if matches(excerpt, symbol, company)]
                moment = card.select_one("time[datetime]")
                if moment:
                    row["published_at"] = moment["datetime"]
            rows.setdefault(url, row)
        if len(rows) >= 25:
            break
    return list(rows.values())


def scrape(name):
    base = SITES[name][0]
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        html = bounded_get(base, [urlsplit(base).hostname], accept="text/html")
        rows = headlines(name, html)
        status = "Available" if rows else "No readable headlines"
    except Exception as exc:
        response = getattr(exc, "response", None)
        status = f"HTTP {response.status_code}" if response is not None else "Page unavailable"
        rows = []
    return name, dict(checked=stamp, status=status, rows=rows)


def collect_pages(previous):
    with ThreadPoolExecutor(max_workers=8) as pool:
        result = dict(pool.map(scrape, SITES))
    for name, entry in result.items():
        if entry["rows"]:
            entry["collected"] = entry["checked"]
        elif name in previous:
            entry["rows"] = previous[name]["rows"]
            entry["collected"] = previous[name].get("collected")
    return result
