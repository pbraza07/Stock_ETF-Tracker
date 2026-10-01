from pathlib import Path

def test_clickable_filters_and_card_navigation_are_configured():
    app = (Path(__file__).resolve().parents[1] / 'app.py').read_text(encoding='utf-8')
    assert 'st.segmented_control(' in app
    assert 'st.pills(' in app
    assert 'instrument-card' in app
    assert 'Open {symbol}' in app
