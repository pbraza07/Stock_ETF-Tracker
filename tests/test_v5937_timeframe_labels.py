from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"

def test_version_5937():
    assert (ROOT / "VERSION.txt").read_text().strip() == "5.9.51"

def test_pdf_setup_removed_and_timeframe_labels_centralized():
    src = APP.read_text(encoding="utf-8")
    assert 'st.popover("ⓘ PDF Setup"' not in src
    assert 'def timeframe_display_label' in src
    assert '_TIMEFRAME_YEAR_BY_HORIZON' in src
    assert 'format_func=timeframe_display_label' in src
    assert 'timeframe_display_label(metric)' in src
    assert 'timeframe_column_config' in src
