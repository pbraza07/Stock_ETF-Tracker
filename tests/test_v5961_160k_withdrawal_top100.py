from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
SCRIPT = (ROOT / "scripts" / "build_160k_withdrawal_rankings.py").read_text(encoding="utf-8")

RB_FILE = ROOT / "data" / "top100_rebalanced_withdrawal_10y_160k_max5.csv"
NR_FILE = ROOT / "data" / "top100_not_rebalanced_withdrawal_10y_160k_max5.csv"
SOURCE_FILE = ROOT / "data" / "annual_performance_160k_source.csv"


def _rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _verify_top100(path: Path, strategy_prefix: str):
    rows = _rows(path)
    assert len(rows) == 100
    assert [int(row["Rank"]) for row in rows] == list(range(1, 101))

    uses = Counter()
    for row in rows:
        stocks = [row[f"Stock {idx}"] for idx in range(1, 5)]
        sectors = [row[f"Sector {idx}"] for idx in range(1, 5)]
        assert len(set(stocks)) == 4
        assert len(set(sectors)) == 4
        assert row["Strategy"].startswith(strategy_prefix)
        assert float(row["Starting Value ($)"]) == 300000.0
        assert float(row["Annual Withdrawal ($)"]) == 160000.0
        assert int(float(row["Target Withdrawals"])) == 10
        assert 0 <= int(float(row["Withdrawals Fully Funded"])) <= 10
        assert row["Full 10Y Withdrawal Goal"] in {"Yes", "No"}
        assert int(float(row["Max Ticker Repeats"])) == 5
        for stock in stocks:
            uses[stock] += 1

    assert max(uses.values()) <= 5
    assert len(uses) >= 80

    # Stored per-row usage metadata must match actual Top-100 counts.
    for row in rows:
        for idx in range(1, 5):
            stock = row[f"Stock {idx}"]
            assert int(float(row[f"Stock {idx} Top100 Uses"])) == uses[stock]

    return rows, uses


def test_release_version_5961():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.11.0"
    assert "v5.9.66" in APP


def test_source_and_generated_ranking_files_are_packaged():
    assert SOURCE_FILE.exists()
    assert RB_FILE.exists()
    assert NR_FILE.exists()

    with SOURCE_FILE.open("r", encoding="utf-8-sig", newline="") as fh:
        header = next(csv.reader(fh))
    for column in ["Symbol", "Name", "Type", "Sector", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017", "2016"]:
        assert column in header


def test_rebalanced_top100_enforces_four_sectors_and_max_five_uses():
    rows, uses = _verify_top100(RB_FILE, "Rebalanced")
    assert len(uses) == 84
    assert max(uses.values()) == 5
    assert sum(row["Full 10Y Withdrawal Goal"] == "Yes" for row in rows) == 9
    assert rows[0]["Combo"] == "PBR + TSLA + AMD + ANET"
    assert int(float(rows[0]["Withdrawals Fully Funded"])) == 10
    assert float(rows[0]["Remaining Balance ($)"]) > 5_600_000


def test_not_rebalanced_top100_enforces_four_sectors_and_max_five_uses():
    rows, uses = _verify_top100(NR_FILE, "Not rebalanced")
    assert len(uses) == 82
    assert max(uses.values()) == 5
    assert sum(row["Full 10Y Withdrawal Goal"] == "Yes" for row in rows) == 8
    assert rows[0]["Combo"] == "PBR + DHR + NVDA + ANET"
    assert int(float(rows[0]["Withdrawals Fully Funded"])) == 10
    assert float(rows[0]["Remaining Balance ($)"]) > 1_550_000


def test_rankings_prioritize_income_delivery_before_ending_balance():
    # The generator's explicit objective protects the user's $160K/year goal.
    assert "number of full $160,000 annual withdrawals funded" in SCRIPT or "Income delivery is the primary objective" in SCRIPT
    assert "funded.astype(np.float64) * 1e12" in SCRIPT
    assert "total_withdrawn * 1e3" in SCRIPT


def test_generator_enforces_stock_only_four_sectors_and_max_five():
    assert 'str(raw.get("Type") or "").strip().upper() != "STOCK"' in SCRIPT
    assert "for a, b, c, d in itertools.combinations(sectors, 4)" in SCRIPT
    assert "MAX_TICKER_USES = 5" in SCRIPT
    assert "if any(uses[symbol] >= MAX_TICKER_USES for symbol in symbols)" in SCRIPT


def test_portfolio_simulator_has_new_160k_dropdown_family():
    assert "💰 10Y $160K Withdrawal Top 100" in APP
    assert "COMBO_10Y_REBALANCED_WITHDRAWAL_160K_FILE" in APP
    assert "COMBO_10Y_NOT_REBALANCED_WITHDRAWAL_160K_FILE" in APP
    assert "COMBO_WITHDRAWAL_ANNUAL_160K = 160_000.0" in APP
    assert "10Y $160K rebalanced withdrawal combination" in APP
    assert "10Y $160K not-rebalanced withdrawal combination" in APP


def test_160k_dropdown_autoloads_exact_simulation_inputs():
    assert "annual_withdrawal: float = COMBO_WITHDRAWAL_ANNUAL" in APP
    assert "st.session_state.portfolio_total_amount = float(COMBO_WITHDRAWAL_START)" in APP
    assert "st.session_state.portfolio_period = \"10Y\"" in APP
    assert "st.session_state.portfolio_allocation_mode = \"Equal split\"" in APP
    assert "st.session_state.portfolio_withdrawals_enabled = True" in APP
    assert "st.session_state.portfolio_monthly_withdrawals_enabled = False" in APP
    assert "COMBO_WITHDRAWAL_ANNUAL_160K," in APP


def test_withdrawal_table_exposes_diversification_and_depletion_fields():
    assert 'f"Stock {idx} Top100 Uses"' in APP
    for field in [
        "Target Withdrawals",
        "Withdrawals Fully Funded",
        "Full 10Y Withdrawal Goal",
        "Depleted Year",
        "Max Ticker Repeats",
        "Distinct Tickers in Top 100",
        "Ranking Source",
        "Ranking Method",
    ]:
        assert field in APP


def test_pdf_contract_bumped_to_v20():
    marker = 'MarketScope Portfolio Split Simulator v37 - v5.9.82 monthly reset + monthly start-year RB/NR depletion dashboard + continuous monthly start-year paths + start-year RB/NR depletion dashboard + split start-year strategies + persistent Build Simulation withdrawal tabs + annual and monthly reset views + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    assert APP.count(marker) >= 2
