import pytest
from free_data_evidence import sec_facts,fred_records,collect

def test_sec_restatement_is_not_known_before_filing():
    rows=[dict(end='2020-12-31',filed='2021-02-01',val=10,accn='a',form='10-K'),
          dict(end='2020-12-31',filed='2022-02-01',val=20,accn='b',form='10-K/A')]
    p={'facts':{'us-gaap':{'Assets':{'units':{'USD':rows}}}}}
    assert sec_facts(p,'2021-02-01')==[]
    assert sec_facts(p,'2021-02-02')[0]['value']==10
    assert sec_facts(p,'2022-02-02')[0]['value']==20

def test_units_periods_remain_separate():
    r=dict(end='2020-12-31',filed='2021-02-01',val=10,accn='a',form='10-K')
    p={'facts':{'us-gaap':{'Revenues':{'units':{'USD':[r,dict(r,start='2020-01-01')],'EUR':[r]}}}}}
    assert len(sec_facts(p,'2021-03-01'))==3

def test_fred_cutoff_missing_nonfinite_and_pagination():
    rows=[{'date':'2020-01-01','value':'1'},{'date':'2022-01-01','value':'2'},
          {'date':'2020-02-01','value':'.'},{'date':'2020-03-01','value':'nan'}]
    result=fred_records({'observations':rows},'UNRATE','2021-01-01')
    assert len(result)==1 and result[0]['available_at']=='2021-01-01'
    with pytest.raises(ValueError):fred_records({'count':9,'observations':rows},'UNRATE','2021-01-01')

def test_free_fred_uses_exact_vintage(monkeypatch):
    import free_data_evidence as m
    monkeypatch.setenv('FRED_API_KEY','test-only')
    def fetch(url,params):
        assert params['realtime_start']==params['realtime_end']==params['observation_end']=='2020-01-01'
        return {'observations':[{'date':'2019-01-01','value':'1'}]}
    monkeypatch.setattr(m,'request_json',fetch)
    r=collect('Macro vintage','DGS10','2020-01-01')
    assert r['probability_validation']=='UNVALIDATED' and not r['survivorship_complete']
    assert 'test-only' not in str(r)

def test_ui_no_request_on_open():
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_string('from free_data_evidence import render_free_evidence\nrender_free_evidence()').run()
    assert not app.exception
    assert 'No calibration uplift' in app.caption[-1].value
