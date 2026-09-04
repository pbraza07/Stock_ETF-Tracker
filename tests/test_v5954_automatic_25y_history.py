from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
SNAPSHOT = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
YAHOO = (ROOT / "providers" / "yahoo.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")


def test_version_5954():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.11.0"


def test_explicit_history_start_reaches_prior_anchor_for_2001():
    assert 'start: str = "2000-01-01"' in YAHOO
    assert 'start=start' in YAHOO
    assert 'auto_adjust=True' in YAHOO
    assert 'download_daily_history_since' in YAHOO


def test_long_history_download_is_chunked_and_missing_symbols_retry_individually():
    assert 'chunk_size: int = 20' in YAHOO
    assert 'for offset in range(0, len(symbols), chunk_size)' in YAHOO
    assert 'yf.Ticker(symbol).history(' in YAHOO


def test_daily_snapshot_uses_automatic_25y_history():
    assert 'provider.download_daily_history_since(' in SNAPSHOT
    assert 'ANNUAL_HISTORY_START' in SNAPSHOT
    assert '_annual_value_or_prior' in SNAPSHOT
    assert '_monthly_value_or_prior' in SNAPSHOT


def test_verified_old_returns_are_not_erased_by_provider_gaps():
    assert 'return _numeric_or_na(prior.get(year))' in SNAPSHOT
    assert 'Do not erase a previously verified annual return' in APP


def test_manual_refresh_and_single_metrics_use_same_25y_source():
    assert 'provider.download_daily_history_since([symbol], start=ANNUAL_HISTORY_START, chunk_size=1)' in APP
    assert 'provider.download_daily_history_since(batch, start=ANNUAL_HISTORY_START, chunk_size=20)' in APP


def test_max_year_chart_uses_explicit_start_history():
    assert 'if str(chart_period).upper() == "MAX"' in YAHOO
    assert 'download_daily_history_since([symbol], start="2000-01-01", chunk_size=1)' in YAHOO


def test_repair_banner_and_button_are_removed():
    assert 'Repair 25Y annual history now' not in APP
    assert 'repair_25y_annual_history' not in APP
    assert '25-year annual-history backfill is incomplete' not in APP


def test_workflow_automatically_requests_25y_history():
    assert 'MARKETSCOPE_ANNUAL_HISTORY_START: 2000-01-01' in WORKFLOW
    assert 'Build dynamic annual returns and matching actual monthly history' in WORKFLOW
