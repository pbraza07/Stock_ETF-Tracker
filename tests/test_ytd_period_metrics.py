from io import BytesIO
import pandas as pd
import pytest
from pypdf import PdfReader
from openpyxl import load_workbook
from ytd_period_metrics import period_metrics, reporting_frequency, stats_html
from ytd_simulator import simulate_ytd, make_saved_record
from ytd_reports import summary_html, build_ytd_pdf, build_ytd_excel


def test_daily_streak_dates_zero_and_earliest_tie():
    dates=pd.bdate_range('2026-01-02',periods=9)
    daily=pd.DataFrame({'Return %':[1,2,0,-1,-2,1,2,-1,-2],
                        'Profit':[10,20,0,-10,-30,10,20,-10,-30]},index=dates)
    s=period_metrics(daily,'Daily')
    assert s['positive']==dict(count=2,start='2026-01-02',end='2026-01-05')
    assert s['negative']==dict(count=2,start='2026-01-07',end='2026-01-08')
    assert s['max_profit']['start']=='2026-01-05'
    assert s['max_loss']['start']=='2026-01-08'
    assert s['max_loss']['profit']==-30


def test_aggregation_uses_profit_sum_and_compounded_returns():
    daily=pd.DataFrame({'Date':['2026-01-29','2026-01-30','2026-02-02','2026-02-03'],
                        'Return %':[10,-10,1,1],'Profit':[100,-110,9,9.09]})
    for frequency in ['Weekly','Monthly']:
        s=period_metrics(daily,frequency)
        assert s['negative']['count']==1 # +10% then -10% compounds to -1%.
        assert s['max_loss']['profit']==-10
        assert s['max_loss']['start']=='2026-01-29'
        assert s['max_loss']['end']=='2026-01-30'
        assert s['max_profit']['profit']==pytest.approx(18.09)
        assert s['positive']['start']=='2026-02-02'


def test_flat_and_missing_do_not_create_extremes_or_bridge_streaks():
    d=pd.DataFrame({'Return %':[0,0],'Profit':[0,0]},index=pd.bdate_range('2026-01-01',periods=2))
    s=period_metrics(d,'Daily')
    assert s['positive']['count']==s['negative']['count']==0
    assert s['max_profit'] is None and s['max_loss'] is None
    assert 'No qualifying period' in stats_html(s)
    d['Return %']=[1,float('nan')]
    assert period_metrics(d,'Monthly')['positive']['count']==0


def sample_record(frequency='Monthly',cadence='Monthly'):
    p=pd.DataFrame({'A':[100,110,121,100,90]},index=pd.to_datetime(['2025-12-31','2026-01-02','2026-01-05','2026-02-02','2026-02-03']))
    names=[('Performance',False)] if cadence=='None' else [('Rebalanced',True),('Non-Rebalanced',False)]
    return make_saved_record({n:simulate_ytd(p,1000,frequency,500,'Daily',rb,'2026-02-03') for n,rb in names},
                             {'holdings':['A'],'cadence':cadence,'reporting_frequency':frequency},'Test')


def test_withdrawal_does_not_turn_profitable_day_into_loss():
    r=sample_record('Daily')
    s=period_metrics(r['strategies']['Rebalanced']['daily'],'Daily')
    assert s['positive']['count']==2
    assert s['max_profit']['profit']==pytest.approx(100)
    assert r['strategies']['Rebalanced']['daily'][0]['Ending Balance']<1000


@pytest.mark.parametrize('frequency',['Daily','Weekly','Monthly'])
def test_result_saved_cards_and_exports_show_same_statistics(frequency):
    r=sample_record(frequency)
    html=summary_html(r)
    assert f'Rebalanced - {frequency} performance statistics' in html
    assert f'Non-Rebalanced - {frequency} performance statistics' in html
    assert 'Longest positive streak' in html and 'Maximum period loss' in html
    pdf=PdfReader(BytesIO(build_ytd_pdf(r)))
    text=' '.join(p.extract_text() for p in pdf.pages)
    assert 'PERIOD PERFORMANCE STATISTICS' in text
    assert 'Longest positive streak' in text and frequency in text
    wb=load_workbook(BytesIO(build_ytd_excel(r)))
    rows=list(wb['Summary'].values)
    assert any(row[2]=='Longest positive streak' and row[1]==frequency for row in rows if len(row)>2)
    del r['inputs']['reporting_frequency']
    assert reporting_frequency(r)==frequency
    assert 'Longest positive streak' in summary_html(r)


def test_none_cadence_preserves_performance_labels():
    html=summary_html(sample_record('Weekly','None'))
    assert 'Performance - Weekly performance statistics' in html
    assert 'Rebalanced' not in html and 'RB ' not in html


def test_actual_area_renders_statistics():
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_string('''
import pandas as pd
from ytd_simulator import show_snapshot
show_snapshot({'Beginning Balance':1000,'Current Balance':990,'Positive Days':1,'Days':2,'Positive Months':0,'Months':1},
pd.DataFrame({'Date':['2026-01-02','2026-01-05'],'Return %':[1,-2],'Profit':[10,-20]}),'Daily')
''').run()
    assert not app.exception
    assert any('Longest negative streak' in m.value and '2026-01-05' in m.value for m in app.markdown)
