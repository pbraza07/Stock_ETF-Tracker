from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
VIEWER = (ROOT / "static" / "pdf_viewer.html").read_text(encoding="utf-8")

def test_v5933_release():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.10.0"

def test_sector_timeframe_metric_is_always_series():
    assert "def _sector_numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:" in APP
    assert "pd.Series(np.nan, index=frame.index" in APP
    assert "selected_returns = _sector_period_return_series(drill_table, selected_tf)" in APP
    assert "selected_returns.to_numpy" in APP

def test_no_app_owned_print_pdf_control_and_pdf_toolbar_hidden():
    combined = (APP + "\n" + VIEWER).lower()
    assert "print pdf" not in combined
    assert "window.print" not in combined
    assert "#toolbar=0&navpanes=0" in VIEWER
