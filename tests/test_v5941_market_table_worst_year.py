from pathlib import Path
import ast

BASE = Path(__file__).resolve().parents[1]
APP = (BASE / "app.py").read_text(encoding="utf-8")

def test_market_table_includes_worst_year():
    assert 'table_df["Worst Year"] = table_df.apply(worst_completed_year_label, axis=1)' in APP
    assert '"Analyst Rating", "Worst Year", "Price Target Low"' in APP

def test_worst_year_uses_completed_calendar_year_columns():
    assert "def worst_completed_year_label" in APP
    assert "for year in YEAR_RETURN_COLS:" in APP
    assert 'return f"{worst_return:+.2f}% ({worst_year})"' in APP

def test_missing_preipo_years_are_skipped_not_zeroed():
    start = APP.index("def worst_completed_year_label")
    end = APP.index("SIGNAL_COLS", start)
    fn = APP[start:end]
    assert "if pd.isna(value) or not np.isfinite(value):" in fn
    assert "continue" in fn

def test_release_version_is_current():
    assert "5.9.43" in APP
