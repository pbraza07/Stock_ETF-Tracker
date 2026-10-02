"""Stock references in saved news, independent of date and impact filters."""
from functools import lru_cache
from news_context import securities, matches


@lru_cache(maxsize=10000)
def _references(title, excerpt, universe):
    text=title+' '+excerpt
    return tuple((symbol,name,sector) for symbol,name,sector in universe
                 if symbol and matches(text,symbol,name))


def stock_index(payload, universe=None):
    """Recompute membership from archive text; older rows need no migration.

    Matching uses the same verified universe as card labels. Neutral stories are
    included. Unknown entities are not assigned guessed tickers.
    """
    universe=tuple(securities() if universe is None else universe)
    index={}
    for article_id,row in payload.get('articles',{}).items():
        for symbol,name,sector in _references(row.get('title',''),row.get('excerpt',''),universe):
            entry=index.setdefault(symbol,dict(company=name,sector=sector,article_ids=set()))
            entry['article_ids'].add(article_id)
    return index
