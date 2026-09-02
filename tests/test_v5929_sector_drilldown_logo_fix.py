from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "app.py").read_text(encoding="utf-8")

def test_version():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.65"

def test_sector_drilldown_uses_defined_logo_cache():
    assert "drill_logo_urls = cached_logo_urls(tuple(drill_symbols)) if drill_symbols else {}" in SRC
    assert "cached_instrument_logo_urls(tuple(drill_symbols))" not in SRC
    assert "def cached_logo_urls(" in SRC

def test_sector_drilldown_still_renders_top_performer_table():
    assert "TOTAL STOCKS ·" in SRC
    assert "Top Performers" in SRC
    assert '"Logo": st.column_config.ImageColumn("Logo", width="small")' in SRC
