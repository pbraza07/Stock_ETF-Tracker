from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")

def test_v5932_release():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.70"

def test_sector_drilldown_columns_are_unique():
    assert "drill_cols = list(dict.fromkeys([" in APP
    assert '"Total Profit", "Total Profit %"' in APP

def test_total_stocks_is_the_popover_control():
    assert "with st.popover(" in APP
    assert "TOTAL STOCKS ·" in APP
    assert "View top performers" not in APP
