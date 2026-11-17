from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np
import top12_data as data


def clock(monkeypatch):
    monkeypatch.setattr(data, 'now_et', lambda: datetime(2026,11,16,tzinfo=ZoneInfo('America/New_York')))


def test_loader_includes_current_year_but_no_future_months(monkeypatch):
    clock(monkeypatch)
    frame=pd.DataFrame([{'Symbol':'A','2025-12':1.,'2026-01':2.,'2026-10':3.,'2026-11':4.,'2026-12':99.,'2026-13':99.,'Monthly Observation Through':'2026-11-13'}])
    monkeypatch.setattr(data.pd,'read_csv',lambda *a,**k:frame)
    result=data.load_monthly(['A','B'],['2025'],remote=False)
    assert result['returns']['A']=={'2025-12':.01,'2026-01':.02,'2026-10':.03,'2026-11':.04}
    assert result['returns']['B']=={}
    meta=data.monthly_metadata(result)
    assert meta['Monthly Data Through']=='2026-11'
    assert meta['Monthly Current Coverage']=='1/2 instruments'
    assert meta['Monthly Observation Through']=='2026-11-13'
    assert 'partial' in meta['Monthly Period Basis']


def test_daily_extension_uses_prior_month_close_and_no_future_prices(monkeypatch):
    clock(monkeypatch)
    hist=pd.DataFrame({'Close':[100.,110.,121.,999.]},index=pd.to_datetime(['2025-12-31','2026-10-30','2026-11-13','2026-11-20']))
    original={'returns':{'A':{'2025-12':.02},'B':{}}}
    result=data.extend_with_recent_history(original,{'histories':{'A':hist}})
    assert np.isclose(result['returns']['A']['2026-11'],.1)
    assert '2026-10' not in result['returns']['A'] # no September close; never invent
    assert result['observation_dates']['A']=='2026-11-13'
    assert result['partial_month']=='2026-11'
    assert original['returns']['A']=={'2025-12':.02}


def test_stale_live_history_cannot_replace_newer_saved_observations(monkeypatch):
    clock(monkeypatch)
    saved={'returns':{'A':{'2026-11':.1}},'observation_dates':{'A':'2026-11-13'}}
    hist=pd.DataFrame({'Close':[100.,90.]},index=pd.to_datetime(['2026-10-30','2026-11-02']))
    result=data.extend_with_recent_history(saved,{'histories':{'A':hist}})
    assert result['returns']['A']['2026-11']==.1
    assert result['observation_dates']['A']=='2026-11-13'


def test_partial_month_does_not_enter_monthly_model_calibration(monkeypatch):
    import pytest
    import top12_rankings as rankings
    from test_v5115_top12 import fixture, YEARS
    captured = {}
    class Captured(Exception): pass
    def prepare(*a, **kw):
        captured.update(kw['monthly_returns'])
        raise Captured()
    monkeypatch.setattr(rankings, 'prepare_projection_model', prepare)
    monthly={'returns':{'A':{'2026-10':.03,'2026-11':.90}},'partial_month':'2026-11'}
    with pytest.raises(Captured):
        rankings.score_universe(fixture(), YEARS, monthly)
    assert captured['returns']['A']=={'2026-10':.03}
    assert monthly['returns']['A']['2026-11']==.90


def test_snapshot_writer_includes_current_month_not_future():
    import scripts.update_snapshot as snapshot
    current=snapshot.now_et().strftime('%Y-%m')
    assert snapshot.MONTHLY_RETURN_COLS[-1]==current
    assert snapshot.MONTHLY_FULL_RETURN_COLS[-1]==current
    assert all(m<=current for m in snapshot.MONTHLY_FULL_RETURN_COLS)


def test_december_partial_does_not_change_completed_year_withdrawal_window():
    from scripts.build_actual_monthly_rankings import _month_columns
    frame=pd.DataFrame(columns=[f'{y}-{m:02d}' for y in range(2016,2027) for m in range(1,13)])
    months=_month_columns(frame,as_of=datetime(2026,12,15))
    assert len(months)==120 and months[0]=='2016-01' and months[-1]=='2025-12'
