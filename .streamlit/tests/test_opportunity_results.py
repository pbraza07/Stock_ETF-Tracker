import pandas as pd
from opportunity_results import result_table,highlight
from quality_opportunities import controls

def sample():
    market=pd.DataFrame([dict(Symbol=s,Type='Stock',Name=s,Sector='Tech',Price=100) for s in ['A','B','C','D']]+[dict(Symbol='ETF',Type='ETF')])
    base={'Quality score':70,'Target probability':.7,'Loss probability':.2,'Loss >20% probability':.1,'Worst-decile mean return':-.3,'Qualifies':False}
    rows=[dict(base,Ticker='A',**{'Quality score':40,'Target probability':.9,'Loss probability':.5}),dict(base,Ticker='B',**{'Target probability':.5}),dict(base,Ticker='C',Qualifies=True)]
    return market,dict(table=pd.DataFrame(rows),excluded=pd.DataFrame([dict(Ticker='D',Reason='Missing fundamentals')]),settings=controls())

def test_all_stocks_ranked_by_count_then_existing_order():
    m,r=sample();out=result_table(r,m)
    assert out.Ticker.tolist()==['C','B','A','D']
    assert out['Criteria met'].iloc[:3].tolist()==[5,4,3]
    assert out.Rank.tolist()==[1,2,3,4]
    assert pd.isna(out.iloc[-1]['Criteria met'])
    assert 'Missing fundamentals' in out.to_csv(index=False)
    assert pd.isna(out.iloc[-1]['Target probability'])

def test_failure_notes_and_styles():
    m,r=sample();out=result_table(r,m).set_index('Ticker');row=out.loc['B']
    assert 'required >= 60.0%' in row.Notes
    colors=highlight(row,r['settings'])
    assert '#54252d' in colors['Target probability']
    assert colors['Quality score']==''
    assert '#4ade80' in highlight(out.loc['C'],r['settings'])['Status']
    assert '#253244' in highlight(out.loc['D'],r['settings'])['Status']

def test_boundaries_and_negative_tail_requirement():
    m,r=sample();r['table'].loc[0,'Worst-decile mean return']=-.6
    out=result_table(r,m).set_index('Ticker')
    assert 'required >= -45.0%' in out.loc['A','Notes']
    r['table'].loc[0,['Quality score','Target probability','Loss probability','Loss >20% probability','Worst-decile mean return']]=[60,.6,.35,.15,-.45]
    r['table'].loc[0,'Qualifies']=True
    assert result_table(r,m).set_index('Ticker').loc['A','Criteria met']==5

def test_ties_preserve_existing_model_order():
    m,r=sample();r['table'].loc[0,'Loss probability']=.2
    assert result_table(r,m).Ticker.tolist()==['C','A','B','D']
