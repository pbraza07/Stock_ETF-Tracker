from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")

def test_v5930_release():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.31"

def test_sector_drilldown_columns_are_unique():
    assert "drill_cols = list(dict.fromkeys([" in APP
    assert '"YTD", "1Y", "Price Target Average"' in APP

def test_stock_count_is_the_drilldown_button():
    assert "stocks\\nView top performers" in APP
    assert "tap below" not in APP
    assert "stocks • View top performers" not in APP
