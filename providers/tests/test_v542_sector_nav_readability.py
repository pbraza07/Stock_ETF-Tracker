from pathlib import Path

def _app(): return (Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')

def test_nav_not_in_display_columns_and_stock_only_sectors_preserved():
    app=_app(); start=app.index('DISPLAY_COLS = ['); end=app.index('filtered = apply_dynamic_filters', start); block=app[start:end]
    assert '"NAV"' not in block
    assert 'stock_sector_rows = market.loc[market["Type"].astype(str).str.upper().eq("STOCK")]' in app

def test_cards_have_mobile_readability_css():
    css=(Path(__file__).resolve().parents[1]/'styles.css').read_text(encoding='utf-8')
    assert '.instrument-card' in css
    assert '@media (max-width: 900px)' in css
