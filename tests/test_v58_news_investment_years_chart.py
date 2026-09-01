from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_news_button_and_directional_rules_present():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    provider = (ROOT / "providers" / "yahoo.py").read_text(encoding="utf-8")
    assert '"📰 News"' in app
    assert 'arrow = "▲" if is_up else "▼"' in app
    assert 'news-direction' in app
    assert '{arrow} {direction} DRIVER' in app
    assert '_classify_news_impact' in app
    assert '_directional_news_items' in app
    assert 'latest 7-day Yahoo Finance news feed' in app
    assert 'def get_recent_news' in provider
    assert 'yf.Search(' in provider


def test_investment_year_selector_controls_profit_sort():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'Investment years' in app
    assert 'ANNUAL_HORIZON_OPTIONS' in app
    assert '_investment_projection_for_sort(row, investment_amount, include_current_ytd, investment_years)' in app
    assert '_investment_projection(row, investment_amount, include_current_ytd, investment_years)' in app


def test_year_chart_supports_current_plus_prior_ten_years():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'chart_year_options = chart_year_labels(as_of=now_et(), include_current=True)' in app
    assert '_filter_history_for_calendar_year' in app
    assert 'cached_max_chart_history(selected)' in app
    assert 'Selecting another year replaces both the graph and year summary.' in app


def test_213_etf_csvs_are_preserved():
    data = ROOT / "data"
    allow = pd.read_csv(data / "etf_allowlist.csv")
    generated = pd.read_csv(data / "default_universe.csv")
    bootstrap = pd.read_csv(data / "default_universe.bootstrap.csv")
    assert len(allow) == 213
    assert int((generated["Type"].astype(str).str.upper() == "ETF").sum()) == 213
    assert int((bootstrap["Type"].astype(str).str.upper() == "ETF").sum()) == 213
