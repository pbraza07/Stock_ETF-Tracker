from pathlib import Path


def _app():
    return (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")


def test_sector_buttons_are_built_from_stock_rows_only():
    app = _app()
    block = app[app.index("stock_sector_rows ="):app.index("selected_sectors =", app.index("stock_sector_rows ="))]
    assert 'eq("STOCK")' in block
    assert '"etf / fund"' in block


def test_nav_is_not_a_main_table_column():
    app = _app()
    start = app.index("DISPLAY_COLS = [")
    end = app.index("]\nfiltered = apply_dynamic_filters", start)
    display_block = app[start:end]
    assert '"NAV"' not in display_block
    main = app[app.index("# Main sortable table"):app.index('st.markdown("### Symbol detail")')]
    assert 'NumberColumn("NAV"' not in main


def test_table_typography_is_larger_for_pc_and_mobile():
    app = _app()
    css = (Path(__file__).resolve().parents[1] / "styles.css").read_text(encoding="utf-8")
    assert '"font-size": "19px"' in app
    assert '"font-size": "21px"' in app
    assert 'row_height=54' in app
    assert '@media (max-width: 768px)' in css
    assert 'font-size: 1.08rem' in css
