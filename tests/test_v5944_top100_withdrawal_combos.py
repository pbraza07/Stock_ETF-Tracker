from pathlib import Path
import csv

BASE = Path(__file__).resolve().parents[1]
APP = (BASE / "app.py").read_text(encoding="utf-8")

FILES = [
    ("top100_rebalanced_withdrawal_10y.csv", "Rebalanced annually"),
    ("top100_not_rebalanced_withdrawal_10y.csv", "Not rebalanced"),
]


def _read(name):
    with (BASE / "data" / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_both_top100_withdrawal_ranking_files_exist_and_are_complete():
    for name, strategy in FILES:
        rows = _read(name)
        assert len(rows) == 100
        assert [int(r["Rank"]) for r in rows] == list(range(1, 101))
        assert all(r["Strategy"] == strategy for r in rows)


def test_every_combo_is_four_stocks_four_different_sectors_and_survives_all_withdrawals():
    for name, _ in FILES:
        rows = _read(name)
        for r in rows:
            stocks = [r[f"Stock {i}"] for i in range(1, 5)]
            sectors = [r[f"Sector {i}"] for i in range(1, 5)]
            assert len(set(stocks)) == 4
            assert len(set(sectors)) == 4
            assert abs(float(r["Starting Value ($)"]) - 300000.0) < 1e-6
            assert abs(float(r["Annual Withdrawal ($)"]) - 85000.0) < 1e-6
            assert abs(float(r["Total Withdrawn ($)"]) - 850000.0) < 1e-6
            assert float(r["Remaining Balance ($)"]) > 0.0
            for year in range(2016, 2026):
                assert float(r[f"{year} Balance After Withdrawal ($)"]) > 0.0


def test_rankings_are_descending_by_remaining_balance():
    for name, _ in FILES:
        vals = [float(r["Remaining Balance ($)"]) for r in _read(name)]
        assert all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))


def test_portfolio_ui_contains_two_new_top100_dropdowns_and_tables():
    assert "Top 100 — Rebalanced Annually" in APP
    assert "Top 100 — Not Rebalanced" in APP
    assert 'picker_key = "combo_10y_withdrawal_rebalanced_picker"' in APP
    assert 'picker_key = "combo_10y_withdrawal_not_rebalanced_picker"' in APP
    assert 'st.tabs(["🔄 Rebalanced Top 100", "↗ Not Rebalanced Top 100"])' in APP
    assert "_withdrawal_combo_rank_table" in APP


def test_preset_autoloads_300k_85k_10y_equal_split_withdrawals():
    assert 'st.session_state.portfolio_period = "10Y"' in APP
    assert 'st.session_state.portfolio_allocation_mode = "Equal split"' in APP
    assert 'st.session_state.portfolio_total_amount = float(COMBO_WITHDRAWAL_START)' in APP
    assert 'st.session_state.portfolio_withdrawals_enabled = True' in APP
    assert 'st.session_state.portfolio_annual_withdrawal = float(COMBO_WITHDRAWAL_ANNUAL)' in APP
    assert 'COMBO_WITHDRAWAL_START = 300_000.0' in APP
    assert 'COMBO_WITHDRAWAL_ANNUAL = 85_000.0' in APP


def test_saved_pdf_persistence_protection_remains_active():
    storage = (BASE / "pdf_storage.py").read_text(encoding="utf-8")
    assert 'PROTECTED_SIMULATION_LIBRARY = "data/saved_portfolio_simulations.json"' in storage
    assert 'PDF_REPO_DIR = "data/generated_pdfs"' in storage
