from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'app.py').read_text(encoding='utf-8')
RANKER = (ROOT / 'scripts' / 'build_recession_rankings.py').read_text(encoding='utf-8')
MONTHLY = (ROOT / 'scripts' / 'build_actual_monthly_rankings.py').read_text(encoding='utf-8')
WORKFLOW = (ROOT / '.github' / 'workflows' / 'update_market_snapshot.yml').read_text(encoding='utf-8')


def test_release_version_5951():
    assert (ROOT / 'VERSION.txt').read_text().strip() == '5.9.79'


def test_rankings_are_hidden_in_respective_popover_buttons():
    for label in [
        '📈 5Y Combo Rankings',
        '📊 10Y Combo Rankings',
        '💵 10Y Yearly Withdrawal',
        '🗓️ 10Y Actual-Monthly Withdrawal',
        '🛡️ Recession-Balanced Top 100',
    ]:
        assert f'st.popover("{label}"' in APP


def test_recession_rankings_have_two_profit_and_two_defense_roles():
    for filename in ['top100_recession_balanced_rebalanced_10y.csv', 'top100_recession_balanced_not_rebalanced_10y.csv']:
        df = pd.read_csv(ROOT / 'data' / filename)
        assert len(df) == 100
        assert (df['Role 1'] == 'Profit Engine').all()
        assert (df['Role 2'] == 'Profit Engine').all()
        assert (df['Role 3'] == 'Recession Defense').all()
        assert (df['Role 4'] == 'Recession Defense').all()
        for _, row in df.iterrows():
            assert len({row[f'Sector {i}'] for i in range(1,5)}) == 4


def test_recession_method_uses_nber_periods_and_annual_stress_years():
    assert 'RECESSION_STRESS_YEARS = ["2001", "2008", "2009", "2020"]' in RANKER
    assert 'https://www.nber.org/research/data/us-business-cycle-expansions-and-contractions' in RANKER
    assert 'Mar-Nov 2001; Dec 2007-Jun 2009; Feb-Apr 2020' in RANKER


def test_rebalanced_tables_use_full_yearly_withdrawal_detail_contract():
    for token in [
        'Stock {idx}', 'Sector {idx}', 'Name {idx}',
        'Worst Year', 'Best Year', 'Starting Value ($)', 'Total Withdrawn ($)',
        'Remaining Balance ($)', 'Net Value incl. Withdrawals ($)',
        'Net Profit incl. Withdrawals ($)', 'Balance After Withdrawal ($)',
    ]:
        assert token in APP
    assert 'Positive Months' in APP
    assert 'Months Funded' in APP


def test_monthly_ranker_persists_identity_annual_worst_best_fields():
    assert 'row[f"Name {pos}"] = name' in MONTHLY
    assert 'row[year] = sim["annual_returns"].get(year, np.nan)' in MONTHLY
    assert 'row["Worst Year"]' in MONTHLY
    assert 'row["Best Year"]' in MONTHLY


def test_refresh_rebuilds_recession_rankings():
    assert 'python scripts/build_recession_rankings.py' in WORKFLOW
    assert 'data/top100_recession_balanced_rebalanced_10y.csv' in WORKFLOW
    assert 'data/top100_recession_balanced_not_rebalanced_10y.csv' in WORKFLOW
