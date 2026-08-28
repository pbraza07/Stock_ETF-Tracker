from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


def test_return_tiles_are_clickable_profit_controls():
    assert 'def _period_profit_href' in APP
    assert 'def _period_profit_projection' in APP
    assert 'perf-cell-button' in APP
    assert 'Calculate profit for' in APP
    assert 'SELECTED PERIOD' in APP
    assert '.period-profit-card' in CSS
    assert '.perf-cell-active' in CSS


def test_ytd_is_a_first_class_investment_period():
    assert '["YTD", *[f"{i}Y" for i in range(1, 11)]]' in APP
    assert 'investment_is_ytd = investment_period_choice == "YTD"' in APP
    assert 'if int(years_requested) == 0:' in APP
    assert 'YTD-only calculation' in APP


def test_profit_link_preserves_key_card_context():
    for token in [
        '"profit_amount"', '"card_page"', '"sort_choice"', '"instrument"',
        '"ratings"', '"signals"', '"sectors"', '"search"'
    ]:
        assert token in APP
