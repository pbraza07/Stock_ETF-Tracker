from __future__ import annotations

import ast
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")
YAHOO = (ROOT / "providers" / "yahoo.py").read_text(encoding="utf-8")


def test_release_version_5960():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.74"
    assert "v5.9.66" in APP


def test_source_priority_debug_copy_cannot_render_in_ui():
    assert "Source priority:" not in APP
    assert "Load actual month-end returns for" not in APP

    tree = ast.parse(APP)
    # Streamlit magic can display standalone f-string expressions. None may remain.
    standalone_fstrings = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.JoinedStr)
    ]
    assert standalone_fstrings == []


def test_positive_months_use_no_truncation_custom_grid():
    assert "def _monthly_withdrawal_kpi_grid" in APP
    assert "monthly-withdrawal-kpi-grid" in APP
    assert "monthly-positive-months-card" in APP
    assert "positive-month-lines" in APP
    assert 'mc5.metric("Positive months"' not in APP

    for token in [
        "white-space: normal",
        "overflow: visible",
        "text-overflow: clip",
        ".monthly-positive-months-card",
    ]:
        assert token in CSS


def test_positive_months_renderer_preserves_both_full_counts():
    tree = ast.parse(APP)
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_monthly_withdrawal_kpi_grid"
    )
    module = ast.Module(body=[fn], type_ignores=[])
    ns = {"escape": escape}
    exec(compile(module, "app.py", "exec"), ns)
    html = ns["_monthly_withdrawal_kpi_grid"](
        1000.0, 21302804.53, 16042373.43, 179, 300, 79, 300
    )
    assert "RB</em> 179/300" in html
    assert "NR</em> 79/300" in html
    assert "$21,302,804.53" in html
    assert "$16,042,373.43" in html


def test_logo_cache_recovers_quickly_from_transient_failure():
    assert "@st.cache_data(ttl=30 * 60, show_spinner=False)" in APP
    assert "provider.get_logo_urls_many(clean, max_workers=3)" in APP


def test_logo_chain_has_real_image_fallback_before_initials():
    assert "logoUrl" in YAHOO
    assert 'meta.get("logo_url")' in YAHOO
    assert "financialmodelingprep.com/image-stock/" in YAHOO
    assert "onerror=" in APP
    assert "comparison-logo-inline-fallback" in APP
    assert ".comparison-logo-inline-fallback" in CSS


def test_card_view_still_passes_resolved_logo_urls():
    assert "visible_logo_urls = cached_logo_urls(" in APP
    assert 'logo_url=visible_logo_urls.get(symbol.upper(), "")' in APP


def test_pdf_contract_bumped_to_v19_for_current_version_on_rebuild():
    marker = 'MarketScope Portfolio Split Simulator v32 - v5.9.74 annual reset inside withdrawal tabs + annual reset withdrawal factor + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    assert APP.count(marker) >= 2


def test_logo_provider_returns_ticker_addressable_candidate_when_yahoo_metadata_is_missing(monkeypatch):
    import providers.yahoo as yahoo_module
    from providers.yahoo import YahooFinanceProvider

    class EmptySearch:
        quotes = []

    monkeypatch.setattr(yahoo_module.yf, "Search", lambda *args, **kwargs: EmptySearch())
    provider = YahooFinanceProvider()
    monkeypatch.setattr(provider, "get_metadata", lambda symbol: {})
    assert provider.get_logo_url("AAPL") == "https://financialmodelingprep.com/image-stock/AAPL.png"
