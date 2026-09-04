from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
SCRIPT = (ROOT / "scripts" / "build_20y_160k_withdrawal_rankings.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")

SOURCE = ROOT / "data" / "annual_performance_20y_160k_source.csv"
RB = ROOT / "data" / "top250_rebalanced_withdrawal_20y_160k_max10.csv"
NR = ROOT / "data" / "top250_not_rebalanced_withdrawal_20y_160k_max10.csv"


def _rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _verify(path: Path, strategy_prefix: str):
    rows = _rows(path)
    assert len(rows) == 250
    assert [int(row["Rank"]) for row in rows] == list(range(1, 251))

    uses = Counter()
    for row in rows:
        stocks = [row[f"Stock {idx}"] for idx in range(1, 5)]
        sectors = [row[f"Sector {idx}"] for idx in range(1, 5)]
        assert len(set(stocks)) == 4
        assert len(set(sectors)) == 4
        assert row["Strategy"].startswith(strategy_prefix)
        assert float(row["Starting Value ($)"]) == 300000.0
        assert float(row["Annual Withdrawal ($)"]) == 160000.0
        assert int(float(row["Target Withdrawals"])) == 20
        assert 0 <= int(float(row["Withdrawals Fully Funded"])) <= 20
        assert row["Full 20Y Withdrawal Goal"] in {"Yes", "No"}
        assert int(float(row["Max Ticker Repeats"])) == 10
        for stock in stocks:
            uses[stock] += 1

    assert max(uses.values()) <= 10
    assert len(uses) >= 100

    for row in rows:
        for idx in range(1, 5):
            stock = row[f"Stock {idx}"]
            assert int(float(row[f"Stock {idx} Top250 Uses"])) == uses[stock]

    return rows, uses


def test_release_version_5963():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.11.2"
    assert "v5.9.66" in APP


def test_20y_source_contains_exact_2006_2025_completed_year_window():
    assert SOURCE.exists()
    with SOURCE.open("r", encoding="utf-8-sig", newline="") as fh:
        header = next(csv.reader(fh))
    years = [str(year) for year in range(2025, 2005, -1)]
    assert all(year in header for year in years)
    assert len(years) == 20


def test_rebalanced_top250_enforces_four_sectors_and_max10():
    rows, uses = _verify(RB, "Rebalanced")
    assert len(uses) == 104
    assert max(uses.values()) == 10
    funded = [int(float(row["Withdrawals Fully Funded"])) for row in rows]
    assert max(funded) == 6
    assert rows[0]["Combo"] == "AEM + BKNG + MNST + ISRG"
    assert int(float(rows[0]["Withdrawals Fully Funded"])) == 6
    assert float(rows[0]["Total Withdrawn ($)"]) > 1_070_000


def test_not_rebalanced_top250_enforces_four_sectors_and_max10():
    rows, uses = _verify(NR, "Not rebalanced")
    assert len(uses) == 103
    assert max(uses.values()) == 10
    funded = [int(float(row["Withdrawals Fully Funded"])) for row in rows]
    assert max(funded) == 6
    assert rows[0]["Combo"] == "SCCO + BKNG + MNST + NVO"
    assert int(float(rows[0]["Withdrawals Fully Funded"])) == 6
    assert float(rows[0]["Total Withdrawn ($)"]) > 1_100_000


def test_generator_uses_income_survival_priority_and_max10():
    assert "TOP_N = 250" in SCRIPT
    assert "MAX_TICKER_USES = 10" in SCRIPT
    assert "HORIZON_YEARS = 20" in SCRIPT
    assert "funded.astype(np.float64) * 1e15" in SCRIPT
    assert "total_withdrawn * 1e6" in SCRIPT
    assert "itertools.combinations(sectors, 4)" in SCRIPT
    assert 'str(raw.get("Type") or "").strip().upper() != "STOCK"' in SCRIPT


def test_portfolio_simulator_has_new_20y_top250_dropdown_family():
    assert "🏆 20Y $160K Withdrawal Top 250" in APP
    assert "COMBO_20Y_REBALANCED_WITHDRAWAL_160K_FILE" in APP
    assert "COMBO_20Y_NOT_REBALANCED_WITHDRAWAL_160K_FILE" in APP
    assert "20Y $160K rebalanced withdrawal combination" in APP
    assert "20Y $160K not-rebalanced withdrawal combination" in APP
    assert "🔄 Rebalanced Top 250" in APP
    assert "↗ Not Rebalanced Top 250" in APP


def test_preset_autoloads_20y_and_160k():
    assert 'period: str = "10Y"' in APP
    assert 'st.session_state.portfolio_period = str(period)' in APP
    assert 'COMBO_WITHDRAWAL_ANNUAL_160K,' in APP
    assert '"20Y",' in APP
    assert "st.session_state.portfolio_total_amount = float(COMBO_WITHDRAWAL_START)" in APP
    assert "st.session_state.portfolio_withdrawals_enabled = True" in APP
    assert "st.session_state.portfolio_monthly_withdrawals_enabled = False" in APP


def test_withdrawal_table_supports_top250_usage_and_20y_columns():
    assert 'f"Stock {idx} Top250 Uses"' in APP
    assert '"Full 20Y Withdrawal Goal"' in APP
    assert '"Distinct Tickers in Top 250"' in APP
    assert 'years = sorted(' in APP
    assert 'balance_cols = [f"{year} Balance After Withdrawal ($)" for year in sorted(years)]' in APP


def test_static_ranking_assets_do_not_retrigger_market_refresh():
    for path in [
        "data/annual_performance_20y_160k_source.csv",
        "data/top250_rebalanced_withdrawal_20y_160k_max10.csv",
        "data/top250_not_rebalanced_withdrawal_20y_160k_max10.csv",
    ]:
        assert f"- '{path}'" in WORKFLOW


def test_pdf_contract_bumped_to_v22():
    marker = 'MarketScope Portfolio Split Simulator v37 - v5.9.82 monthly reset + monthly start-year RB/NR depletion dashboard + continuous monthly start-year paths + start-year RB/NR depletion dashboard + split start-year strategies + persistent Build Simulation withdrawal tabs + annual and monthly reset views + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    assert APP.count(marker) >= 2
