from pathlib import Path


def test_removed_columns_not_in_main_display_contract():
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    start = app.index("DISPLAY_COLS = [")
    end = app.index("]\nfiltered = apply_dynamic_filters", start)
    display_block = app[start:end]
    for removed in ["Return Basis", "Rating Source", "Data As Of", "Rating Updated ET", "Snapshot Updated ET"]:
        assert removed not in display_block


def test_clickable_filters_and_large_rows_are_configured():
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert 'st.segmented_control(' in app
    assert 'st.pills(' in app
    assert 'row_height=54' in app
    assert 'Rating update:' in app
    assert 'Snapshot update:' in app
