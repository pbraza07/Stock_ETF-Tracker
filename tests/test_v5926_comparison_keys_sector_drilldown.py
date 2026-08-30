from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'app.py'
SRC = APP.read_text()

def test_profit_tiles_are_namespaced_by_view():
    assert 'key=f"profit_tile_{clean_namespace}_{symbol}_{metric}"' in SRC
    assert 'namespace="navigator"' in SRC
    assert 'namespace="comparison"' in SRC
    assert 'card_profit_period_selected_{clean_namespace}_{clean_symbol}' in SRC

def test_sector_total_stocks_opens_top_performers_popover():
    assert 'TOTAL STOCKS ·' in SRC
    assert '_render_sector_top_performers_popover' in SRC
    assert 'Top Performers' in SRC
    assert 'sector_top_performers_table_' in SRC
    assert 'cached_logo_urls(tuple(drill_symbols))' in SRC
    assert 'Total Profit %' in SRC
