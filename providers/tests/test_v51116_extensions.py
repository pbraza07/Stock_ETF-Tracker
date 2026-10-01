import pandas as pd
import pytest
from urllib.parse import urlparse, parse_qs
from ytd_simulator import simulate_ytd
from top12_rankings import select_sector_leaders
from economic_calendar import calendar_url


def test_custom_start_and_none_disable_all_cashflows_and_rebalancing():
    prices=pd.DataFrame({'A':[100,120,90,150],'B':[100,90,150,100]},index=pd.to_datetime(['2024-12-31','2025-01-02','2025-02-03','2026-01-05']))
    runs=[simulate_ytd(prices,1000,'Monthly',500,'None',rb,'2026-01-05','2025-01-01') for rb in [True,False]]
    pd.testing.assert_frame_equal(runs[0][1],runs[1][1])
    assert runs[0][1]['Actual Withdrawal'].sum()==0
    assert runs[0][1].iloc[-1]['Ending Balance']==pytest.approx(1250)
    assert runs[0][1].attrs['custom_start']
    assert runs[0][1].attrs['start_date']=='2024-12-31'


def test_sector_leaders_five_each_without_filling_short_sectors():
    frame=pd.DataFrame({'Symbol':[str(i) for i in range(15)],'Sector':['A']*7+['B']*6+['C']*2,'Score':range(15)})
    result=select_sector_leaders(frame,'Score',threshold=0)
    assert result.groupby('Sector').size().to_dict()=={'A':5,'B':5,'C':2}
    assert set(result[result.Sector=='A'].Symbol)=={'2','3','4','5','6'}


def test_weekly_high_importance_calendar_has_announcement_timezone():
    url=urlparse(calendar_url());q=parse_qs(url.query)
    assert url.hostname=='sslecal2.investing.com'
    assert q['importance']==['3'] and q['calType']==['week']
    assert q['timeZone']==['8']
