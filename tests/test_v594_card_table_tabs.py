from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


def test_release_version_594():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.5"


def test_actual_tabs_exist_for_cards_and_table():
    assert 'st.tabs(["▦ Card View", "▤ Table View"])' in APP
    assert "with card_view_tab:" in APP
    assert "with table_view_tab:" in APP


def test_table_contains_current_market_and_simulation_fields():
    required = [
        '"Symbol"', '"Name"', '"Type"', '"Sector"', '"Industry"', '"Price"',
        '"Market Cap ($B)"', '"Analyst Rating"', '"Price Target Low"',
        '"Price Target Average"', '"Price Target High"', '"Avg Target Implied %"',
        '"Short Buy"', '"Long Buy"', '"Fundamental Buy"', '"Simulation Period"',
        '"Investment Amount ($)"', '"Estimated Value ($)"', '"Profit / Loss ($)"',
        '"Simulation Return %"', '"Signal Reasons"',
    ]
    for token in required:
        assert token in APP
    assert '*PERF_COLS' in APP


def test_table_has_explicit_and_native_sorting():
    assert '"Sort table by"' in APP
    assert '"High → Low", "Low → High"' in APP
    assert "click any column header" in APP
    assert "table_df.sort_values" in APP


def test_removed_columns_are_not_reintroduced_in_table_column_list():
    table_section = APP.split('TABLE_COLUMNS = [', 1)[1].split(']', 1)[0]
    for removed in [
        "NAV", "Exchange", "Inception Date", "Return Basis", "Rating Source",
        "Data As Of", "Rating Updated ET", "Snapshot Updated ET",
    ]:
        assert f'"{removed}"' not in table_section


def test_tab_visuals_are_styled():
    assert 'div[data-baseweb="tab-list"]' in CSS
    assert 'button[data-baseweb="tab"]' in CSS
    assert '.table-view-header' in CSS
