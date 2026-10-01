"""Offline walk-forward of the actual stock screen using timestamped vintages.

No current live loader is called. Outcome records are never passed to screening.
This validates stock leaders, not discretionary portfolio choices.
"""
import numpy as np
import pandas as pd
from planning_validation import freeze_snapshot
from quality_opportunities import screen,MODES

def inputs_at(records,cutoff):
    frozen=freeze_snapshot(records,cutoff);members={};fund={};macro={};annual={};monthly={}
    for r in frozen:
        k=r['key'];v=r['value'];kind=r['kind']
        if kind=='universe':members[k]=v
        elif kind=='fundamentals':fund[k]=v
        elif kind=='macro':macro[k]={'value':v,'observation_date':r['observation_date']}
        elif kind=='prices':annual.setdefault(k,{})[str(pd.Timestamp(r['observation_date']).year)]=float(v)*100
        elif kind=='monthly':monthly.setdefault(k,{})[str(pd.Period(r['observation_date'],freq='M'))]=float(v)
    market=[];years=set()
    for symbol,v in members.items():
        if not v.get('eligible'):continue
        a=annual.get(symbol,{})
        years.update(a)
        market.append({'Symbol':symbol,'Name':v.get('name',symbol),'Type':v.get('type','Stock'),'Sector':v.get('sector'),
            'Price':v.get('price'),'MarketCap':v.get('market_cap'),**a})
    return pd.DataFrame(market,columns=list(dict.fromkeys(['Symbol','Name','Type','Sector','Price','MarketCap',*sorted(years)]))),sorted(years),{'returns':monthly},{'fundamentals':fund,'macro':macro,'snapshot_as_of':cutoff}

def run_bundle(bundle):
    rows=[];missing=[];decisions=[]
    for cutoff in sorted(bundle['cutoffs']):
        date=pd.Timestamp(cutoff)
        if (date.month,date.day)!=(12,31):raise ValueError('Annual outcome testing requires December 31 cutoffs.')
        market,years,monthly,context=inputs_at(bundle['records'],cutoff)
        # Caller-supplied present-day planning overrides are deliberately not accepted.
        result=screen(market,years,monthly,context,bundle.get('screen_settings'),planning=None)
        leaders=result['leaders'];h=result['settings']['years'];cfg=result['settings']
        decisions.append({'cutoff':cutoff,'selected':leaders.get('Ticker',pd.Series(dtype=str)).tolist(),
            'excluded':result['excluded'].to_dict('records')})
        outcomes=bundle.get('realized_annual_returns',{})
        def forward(mapping):
            a=[mapping.get(str(y)) for y in range(date.year+1,date.year+h+1)]
            if any(v is None for v in a):return None
            values=np.asarray(a,float)
            if not np.isfinite(values).all() or (values< -1).any():raise ValueError('Invalid outcome return.')
            # Same explicit annual fee and entry/exit costs as screening. No tax claim.
            value=np.prod(1+values)*(1-cfg['annual_fee'])**h*(1-cfg['trade_cost'])**2
            return value**(1/h)-1,values
        universe_values=[forward(outcomes.get(s,{})) for s in result['table'].get('Ticker',pd.Series(dtype=str))]
        median=float(np.median([v[0] for v in universe_values if v is not None])) if any(v is not None for v in universe_values) else None
        benchmark=forward(bundle.get('sp500_annual_returns',{}))
        for _,stock in leaders.iterrows():
            actual=forward(outcomes.get(stock.Ticker,{}))
            if actual is None:missing.append({'cutoff':cutoff,'ticker':stock.Ticker,'reason':'Missing realized outcome, including delisting/cash-slot evidence'});continue
            cagr,annual=actual
            netannual=(1+annual)*(1-cfg['annual_fee'])-1
            netannual[0]=(1+netannual[0])*(1-cfg['trade_cost'])-1
            netannual[-1]=(1+netannual[-1])*(1-cfg['trade_cost'])-1
            hit=bool(np.all(netannual>=cfg['target'])) if cfg['mode']==MODES[2] else bool(cagr>=cfg['target'])
            sector=forward(bundle.get('sector_annual_returns',{}).get(stock.Sector,{}))
            rows.append({'cutoff':cutoff,'end':str(date+pd.DateOffset(years=h)),'ticker':stock.Ticker,'horizon':h,
                'forecast_probability':stock['Target probability'],'target_hit':hit,'realized_cagr':cagr,
                'p50_bias_realized_minus_forecast':cagr-stock['Median return'],
                'beats_sp500':None if benchmark is None else cagr>benchmark[0],
                'beats_universe_median':None if median is None else cagr>median,
                'beats_sector':None if sector is None else cagr>sector[0]})
    independent=0;end=None
    for d in decisions:
        matches=[r for r in rows if r['cutoff']==d['cutoff']]
        if matches and (end is None or pd.Timestamp(d['cutoff'])>=end):independent+=1;end=pd.Timestamp(matches[0]['end'])
    bins=[]
    for bin_index in range(10):
        low=bin_index/10
        selected=[r for r in rows if min(9,int(r['forecast_probability']*10))==bin_index]
        if selected:bins.append({'probability_bin':f'{low:.0%}–{min(1,low+.1):.0%}','stock_forecasts':len(selected),'observed_hit_rate':float(np.mean([r['target_hit'] for r in selected]))})
    return {'records':rows,'decisions':decisions,'missing_outcomes':missing,'probability_bins':bins,
        'independent_calendar_windows':independent,'confidence':'UNVALIDATED — externally audit vintages and collect independent out-of-sample observations',
        'point_in_time_integrity':'PARTIAL — timestamps enforced; source provenance not independently verified',
        'survivorship':'Historical calibration contains survivorship limitations.' if not bundle.get('delisted_coverage_documented') else 'Coverage asserted by supplied manifest; not independently certified',
        'limitations':'Stock outcomes within a date are correlated, not independent trials. Bins are descriptive only. Annual outcomes cannot measure intrayear drawdowns. Discretionary portfolio selection is not backtested. Missing outcomes are reported, never converted to successes.'}

if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('bundle');p.add_argument('output');a=p.parse_args()
    Path(a.output).write_text(json.dumps(run_bundle(json.loads(Path(a.bundle).read_text())),indent=2,default=str))
