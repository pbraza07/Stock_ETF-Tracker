from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_release_version_5975():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.78"
    assert "v5.9.78" in APP


def test_build_simulation_has_persistent_annual_strategy_tabs():
    assert "annual_withdrawal_tabs_rendered = False" in APP
    assert "annual_withdrawal_tabs_rendered = True" in APP
    assert "if not annual_withdrawal_tabs_rendered:" in APP

    # One tab set renders populated results; the second preserves the row when
    # Yearly Withdrawal is off/unavailable.
    assert APP.count('"↻ Rebalanced annually"') >= 2
    assert APP.count('"↝ Not rebalanced"') >= 2
    assert APP.count('"⚖ Side-by-side"') >= 2
    assert APP.count('"📅 Annual Reset"') >= 2


def test_tabs_remain_visible_when_yearly_withdrawal_toggle_is_off():
    fallback = APP[APP.index("if not annual_withdrawal_tabs_rendered:"):]
    assert "if not portfolio_withdrawals_enabled:" in fallback
    assert "Enable **Yearly withdrawal** above" in fallback
    assert "tabs remain visible" in fallback.lower()


def test_annual_reset_placeholder_explains_withdrawal_dependency():
    fallback = APP[APP.index("if not annual_withdrawal_tabs_rendered:"):]
    reset = fallback[fallback.index("with reset_tab:"):]
    assert "Withdrawal / year ($)" in reset
    assert "each independent Annual Reset row" in reset


def test_successful_annual_withdrawal_still_renders_full_strategy_tabs():
    success = APP[APP.index("annual_withdrawal_tabs_rendered = False"):]
    success = success[:success.index("if not annual_withdrawal_tabs_rendered:")]
    assert 'rb_tab, nr_tab, compare_tab, reset_tab, start_year_rb_tab, start_year_nr_tab = st.tabs([' in success
    assert "with rb_tab:" in success
    assert "with nr_tab:" in success
    assert "with compare_tab:" in success
    assert "with reset_tab:" in success
    assert "with start_year_rb_tab:" in success
    assert "with start_year_nr_tab:" in success
    assert "_portfolio_annual_reset_dataframe(" in success


def test_pdf_contract_bumped_to_v33():
    marker = 'MarketScope Portfolio Split Simulator v36 - v5.9.78 start-year RB/NR depletion dashboard + split start-year rebalanced/not-rebalanced tabs + start-year rolling withdrawal paths + persistent Build Simulation withdrawal tabs + annual reset inside withdrawal tabs + annual reset withdrawal factor + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    assert APP.count(marker) >= 2
