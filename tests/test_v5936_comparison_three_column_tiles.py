from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_and_comparison_tile_css_contract():
    assert (ROOT / "VERSION.txt").read_text().strip() == "5.9.55"
    css = (ROOT / "styles.css").read_text(encoding="utf-8")
    assert 'div[class*="st-key-comparison_card_"] [data-testid="stHorizontalBlock"]' in css
    assert 'grid-template-columns: repeat(3, minmax(0, 1fr)) !important;' in css
    assert 'div[class*="st-key-comparison_card_"] [data-testid="stButton"] button' in css


def test_comparison_fragment_still_builds_rows_of_three():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'for idx in range(0, len(PERF_COLS), 3):' in app
    assert 'tile_cols = st.columns(3, gap="small")' in app
    assert 'namespace="comparison"' in app
