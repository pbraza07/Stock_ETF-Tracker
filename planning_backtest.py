"""Executable point-in-time selection + forward projection from supplied vintages.

This never downloads today's fundamentals as a historical substitute. The input
schema is documented in PLANNING_DATA.md. No bundled empirical certification.
"""
import numpy as np
import pandas as pd
from planning_validation import walk_forward,calibration

def run_bundle(bundle):
    from future_projection import run_future_projection
    count=int(bundle.get('simulation_count',500));limit=int(bundle.get('holding_count',4))
    def select(rows,cutoff):
        from top12_rankings import score_universe, select_sector_leaders
        members={r['key']:r['value'] for r in rows if r['kind']=='universe'}
        market=[];years=set()
        for symbol,member in members.items():
            if not member.get('eligible') or not member.get('sector'):continue
            row={'Symbol':symbol,'Name':member.get('name',symbol),'Type':'Stock','Sector':member['sector']}
            for record in rows:
                if record['kind']=='prices' and record['key']==symbol:
                    year=str(pd.Timestamp(record['observation_date']).year)
                    row[year]=float(record['value'])*100;years.add(year)
            market.append(row)
        context={'fundamentals':{r['key']:r['value'] for r in rows if r['kind']=='fundamentals'},
                 'macro':{r['key']:{'value':r['value'],'observation_date':r['observation_date']} for r in rows if r['kind']=='macro'}}
        scored,_,_=score_universe(pd.DataFrame(market),sorted(years),live=context,simulations=count,seed=123)
        score=bundle.get('selection_score','Max Profit Score')
        if score not in ('Max Profit Score','Recession Score'):raise ValueError('Unknown production ranking score')
        picks=select_sector_leaders(scored,score,threshold=0)
        selected=[];sectors=set()
        for _,row in picks.iterrows():
            if row.Sector in sectors:continue
            selected.append(row.Symbol);sectors.add(row.Sector)
            if len(selected)==limit:break
        if not selected:raise ValueError('No eligible point-in-time universe at '+str(cutoff))
        return selected
    def forecast(rows,selected,cutoff,horizon):
        members={r['key']:r['value'] for r in rows if r['kind']=='universe'}
        market=[];years=set();fund={};macro={}
        for s in selected:
            row={'Symbol':s,'Name':members[s].get('name',s),'Type':'Stock','Sector':members[s]['sector']}
            for r in rows:
                if r['kind']=='prices' and r['key']==s:
                    year=str(pd.Timestamp(r['observation_date']).year);row[year]=float(r['value'])*100;years.add(year)
            market.append(row)
        for r in rows:
            if r['kind']=='fundamentals':fund[r['key']]=r['value']
            if r['kind']=='macro':macro[r['key']]={'value':r['value'],'observation_date':r['observation_date']}
        # Only rate-based forward components whose observations were actually available at cutoff.
        cfg={'solve_withdrawal':False,'run_diagnostics':False,'expense_ratio':0.,'trading_friction':0.,'bid_ask':0.}
        result=run_future_projection(pd.DataFrame(market),{'holdings':selected,'starting_investment':100000,
            'allocation_mode':'Equal Split','withdrawal_frequency':'No Withdrawal','strategy':'Rebalanced',
            'rebalancing_frequency':'Yearly','future_years':horizon,'forecast_start_year':pd.Timestamp(cutoff).year+1,'simulation_count':count,
            'planning_engine':True,'planning':cfg,'random_seed':123},sorted(years),live_context={'fundamentals':fund,'macro':macro})
        table=result['references']['Rebalanced'];last=table.iloc[-1]
        return {**{f'P{p}':(last[f'P{p} Ending Balance']/100000)**(1/horizon)-1 for p in (10,25,50,75,90)},
                'Model version':'5.11.64','Exact production pipeline':True,
                'Probability positive':result['strategies']['Rebalanced']['summary']['Probability Nominal Gain'],
                'Selection policy':bundle.get('selection_score','Max Profit Score')+'; distinct sectors',
                'Input evidence SHA256':result['audit']['input_evidence']['sha256'],
                'Price basis':'Annual total returns; monthly cashflow path approximation'}
    outcomes=bundle.get('realized_annual_returns',{})
    def realize(selected,cutoff,horizon):
        start=pd.Timestamp(cutoff).year+1;values=[]
        for year in range(start,start+horizon):
            if any(str(year) not in outcomes.get(s,{}) for s in selected):return None
            values.append(float(np.mean([outcomes[s][str(year)] for s in selected])))
        # Delisted outcomes must include terminal losses and subsequent cash-slot zeros.
        if any(v< -1 for v in values):raise ValueError('Invalid realized total return below -100%.')
        return {'cagr':float(np.prod(1+np.array(values))**(1/horizon)-1),'volatility':float(np.std(values))}
    records=walk_forward(bundle['records'],bundle['cutoffs'],select,forecast,realize,
        horizons=bundle.get('horizons',[1,3,5,10]),delisted_coverage=bool(bundle.get('verified_delisted_coverage')))
    return {'records':records,'calibration':calibration(records),'selection_policy':'Production ranking score on frozen input rows; distinct sectors, then rank order',
            'limitations':'Annual realized comparison uses annual equal-weight rebalancing and excludes tax/fee drag; align costs before interpreting bias. Vintage provenance depends on supplied source records.'}

if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser();parser.add_argument('bundle');parser.add_argument('output');args=parser.parse_args()
    Path(args.output).write_text(json.dumps(run_bundle(json.loads(Path(args.bundle).read_text())),indent=2,default=str))
