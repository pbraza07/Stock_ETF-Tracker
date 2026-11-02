import pytest
import pandas as pd
from pandas.testing import assert_frame_equal
from favorite_picks import build_favorite_picks, screen_favorite_candidates
from test_v5111_favorite_picks import market_fixture,live_fixture,YEARS


@pytest.mark.parametrize('days',[1,25,100,200])
def test_partial_daily_history_does_not_abort_or_invent_observations(days):
    market=market_fixture();original=market.copy(deep=True);context=live_fixture()
    context['histories']={s:h.tail(days) for s,h in context['histories'].items()}
    result=build_favorite_picks(market,YEARS,context,simulations=100)
    table=result['table']
    assert len(table)==4
    assert table['200D Return %'].isna().all()
    if days<=50:assert table['50D Return %'].isna().all()
    if days<=20:assert table['20D Return %'].isna().all()
    assert table['Distance From 52W High %'].isna().all()
    assert table['Live Evidence Gaps'].str.contains('200D Return').all()
    assert table['Live Data Quality'].eq('Low').all()
    assert table['Trend Score'].eq(50.).all()
    assert result['warnings']
    assert_frame_equal(market,original)


def test_observed_returns_match_provider_history_exactly():
    context=live_fixture();result=build_favorite_picks(market_fixture(),YEARS,context,simulations=100)
    for _,row in result['table'].iterrows():
        close=context['histories'][row.Symbol].Close
        for period in [20,50,200]:
            assert row[f'{period}D Return %']==pytest.approx((close.iloc[-1]/close.iloc[-period-1]-1)*100)
        assert row['Live Evidence Gaps']=='None'
        assert row['Distance From 52W High %']==pytest.approx((close.iloc[-1]/close.tail(252).max()-1)*100)


def test_missing_classification_is_not_assumed_stock():
    assert screen_favorite_candidates(market_fixture().drop(columns='Type'),YEARS).empty


def test_annual_history_remains_required():
    m=market_fixture()
    m[YEARS]=float('nan')
    with pytest.raises(ValueError,match='completed annual history'):
        build_favorite_picks(m,YEARS,live_fixture(),simulations=100)
