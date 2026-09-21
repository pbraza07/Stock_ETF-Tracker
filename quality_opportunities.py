"""Quality-first research screen. Forward Planning assumptions, never CAGR targets.

Probabilities are conditional on the model, not calibrated success promises.
The universe is supplied by MarketScope; no ticker selections are embedded.
"""
from datetime import datetime, timezone
import hashlib
import numpy as np
import pandas as pd
from planning_assumptions import settings, forward_cma, number
from planning_paths import generate_paths, observed_blocks
from future_projection import prepare_projection_model

MODEL_VERSION='5.11.38-quality-1'
MODES=('Next 12 months','Annualized over horizon','At least target every year')
DEFAULTS=dict(target=.25,mode=MODES[0],years=1,count=2000,seed=1234,
    min_quality=60.,min_probability=.60,max_loss_probability=.35,
    max_severe_probability=.15,max_tail_loss=.45,annual_fee=.001,
    trade_cost=.001,max_per_sector=5)

def controls(values=None):
    cfg=dict(DEFAULTS,**(values or {}))
    if cfg['mode'] not in MODES:raise ValueError('Unknown return target definition.')
    if cfg['mode']==MODES[0]:cfg['years']=1
    if not 1<=int(cfg['years'])<=10 or not 100<=int(cfg['count'])<=10000:raise ValueError('Use 1–10 years and 100–10,000 paths.')
    for key in ('min_probability','max_loss_probability','max_severe_probability','max_tail_loss','annual_fee','trade_cost'):
        if not 0<=cfg[key]<1:raise ValueError(key+' must be between zero and one (exclusive).')
    if not 0<cfg['target']<=2 or not 0<=cfg['min_quality']<=100:raise ValueError('Invalid target or quality threshold.')
    return cfg

def universe(market):
    if market.empty:return market.copy()
    return market.loc[market['Type'].astype(str).str.casefold().eq('stock')].drop_duplicates('Symbol').sort_values('Symbol').copy()

def quality_table(market,context):
    rows=[]
    for _,r in universe(market).iterrows():
        s=str(r['Symbol']);f=(context.get('fundamentals') or {}).get(s,{})
        sector=str(r.get('Sector') or '').strip()
        financial=sector.casefold() in ('finance','financials','financial services')
        cap=number(f.get('market_cap'),number(r.get('MarketCap')))
        fcf=number(f.get('free_cash_flow'))
        rows.append({'Ticker':s,'Company':str(r.get('Name') or s),'Sector':sector,
            'Price':number(r.get('Price')),'ROIC / ROE proxy':number(f.get('return_on_invested_capital'),number(f.get('return_on_equity'))),
            'Operating margin':number(f.get('operating_margin')),
            'Cash-flow yield':fcf/cap if fcf is not None and cap and cap>0 and not financial else None,
            'Revenue growth':number(f.get('revenue_growth')),'Earnings growth':number(f.get('forward_eps_growth'),number(f.get('earnings_growth'))),
            'Debt / equity':number(f.get('debt_to_equity')) if not financial else None,
            'Forward P/E':number(f.get('forward_pe')),'Financial-sector treatment':financial,
            'Fundamentals retrieved':str(f.get('retrieved_at') or 'Unavailable'),
            'Fundamentals source':str(f.get('source') or 'Unavailable')})
    frame=pd.DataFrame(rows)
    if frame.empty:return frame
    fields=['ROIC / ROE proxy','Operating margin','Cash-flow yield','Revenue growth','Earnings growth','Debt / equity']
    for field in fields:frame[field]=pd.to_numeric(frame[field],errors='coerce')
    scores=[];coverage=[];bases=[];components=[]
    for _,r in frame.iterrows():
        peers=frame[frame.Sector.eq(r.Sector)]
        fields_used=[f for f in fields if not(r['Financial-sector treatment'] and f in ('Cash-flow yield','Debt / equity'))]
        total=0.;available=0;small=False;parts={}
        for field in fields_used:
            if pd.isna(r[field]):parts[field]=None;continue
            available+=1
            evidence=peers[field].dropna()
            if len(evidence)<5:
                # Conservative absolute scale when no adequate sector peer set exists.
                small=True
                low,high={'ROIC / ROE proxy':(0,.25),'Operating margin':(0,.25),'Cash-flow yield':(0,.08),
                    'Revenue growth':(0,.20),'Earnings growth':(0,.25),'Debt / equity':(0,200)}[field]
                score=float(np.clip((r[field]-low)/(high-low),0,1))
                if field=='Debt / equity':score=1-score
            else:
                score=float(((evidence<r[field]).sum()+.5*(evidence==r[field]).sum())/len(evidence))
                if field=='Debt / equity':score=1-score
            total+=score
            parts[field]=100*score
        scores.append(100*total/len(fields_used)) # Missing evidence is zero, never renormalized upwards.
        coverage.append(available/len(fields_used));bases.append('Absolute heuristic; small peer set' if small else 'Sector-relative percentiles')
        components.append(parts)
    frame['Quality score']=scores;frame['Evidence coverage']=coverage;frame['Quality basis']=bases
    frame['Quality component scores']=components
    return frame

def path_metrics(returns,assignment,cfg,weights=None,rebalanced=False):
    """Monthly joint simulation, zero external cashflows, after explicit costs.
    Full liquidation cost is charged at the final month only; taxes excluded.
    """
    months,count,n=returns.shape
    weights=np.asarray(weights if weights is not None else np.ones(n)/n,float)
    if len(weights)!=n or (weights<0).any() or not np.isclose(weights.sum(),1):raise ValueError('Invalid portfolio weights.')
    holdings=np.tile(weights*(1-cfg['trade_cost']),(count,1))
    peak=np.ones(count);dd=np.zeros(count);annual=[];last=np.ones(count);turnover=np.zeros(count)
    for m in range(months):
        holdings*=np.maximum(0,1+returns[m]);holdings*=(1-cfg['annual_fee'])**(1/12)
        if rebalanced and m%12==11 and m<months-1:
            target=holdings.sum(1)[:,None]*weights
            traded=np.abs(target-holdings).sum(1);turnover+=traded
            holdings=np.maximum(0,holdings.sum(1)-traded*cfg['trade_cost'])[:,None]*weights
        value=holdings.sum(1)*(1-cfg['trade_cost'] if m==months-1 else 1)
        peak=np.maximum(peak,value);dd=np.minimum(dd,value/peak-1)
        if m%12==11:
            annual.append(value/np.maximum(last,1e-12)-1);last=value.copy()
    terminal=value-1;cagr=np.maximum(value,0)**(12/months)-1
    outcome=terminal if cfg['mode']==MODES[0] else cagr
    success=np.all(np.asarray(annual)>=cfg['target'],axis=0) if cfg['mode']==MODES[2] else outcome>=cfg['target']
    p=float(success.mean());z=1.96;den=1+z*z/count
    center=(p+z*z/(2*count))/den;radius=z*np.sqrt(p*(1-p)/count+z*z/(4*count*count))/den
    cutoff=np.quantile(outcome,.10);tail=float(outcome[outcome<=cutoff].mean())
    models={name:float(cagr[assignment==i].mean()) for i,name in enumerate(('Adaptive MC','Centered block bootstrap','Factor/CMA')) if (assignment==i).any()}
    spread=max(models.values())-min(models.values()) if len(models)>1 else None
    return {'Target probability':p,'MC sampling low':max(0,center-radius),'MC sampling high':min(1,center+radius),
        'Loss probability':float((terminal<0).mean()),'Loss >20% probability':float((terminal<-.20).mean()),
        'P10 return':float(np.quantile(outcome,.10)),'Median return':float(np.median(outcome)),
        'P90 return':float(np.quantile(outcome,.90)),'Worst-decile mean return':tail,
        'Planning return (P25 CAGR)':float(np.quantile(cagr,.25)),
        'Mean maximum monthly drawdown':float(dd.mean()),'Mean turnover / initial capital':float(turnover.mean()),
        'Model disagreement (CAGR spread)':spread,'Model mean CAGRs':models,
        'Probability status':'UNCALIBRATED MODEL ESTIMATE'}

def qualifies(row,cfg):
    reasons=[]
    for ok,label in [(row['Quality score']>=cfg['min_quality'],'Quality'),
        (row['Target probability']>=cfg['min_probability'],'Target probability'),
        (row['Loss probability']<=cfg['max_loss_probability'],'Loss probability'),
        (row['Loss >20% probability']<=cfg['max_severe_probability'],'Severe loss'),
        (row['Worst-decile mean return']>=-cfg['max_tail_loss'],'Worst-decile loss')]:
        if not ok:reasons.append(label)
    return reasons

def screen(market,year_columns,monthly,context,values=None,planning=None,progress=None):
    cfg=controls(values);pcfg=settings(planning);cma=forward_cma(context,pcfg)
    quality=quality_table(market,context);rows=[];excluded=[];audit={}
    for i,r in quality.iterrows():
        symbol=r['Ticker']
        if progress:progress(i,len(quality),'Evaluating eligible stocks')
        reason=None
        if r.Sector.casefold() in ('','unknown','nan','none','n/a'):reason='Missing sector'
        elif r['Evidence coverage']<.75:reason='Insufficient fundamental evidence (minimum 75%)'
        elif number(r['Price']) is None or r['Price']<=0:reason='No valid current/snapshot price'
        elif number(r['Forward P/E']) is None or r['Forward P/E']<=0:reason='No valid valuation evidence'
        elif number(r['ROIC / ROE proxy']) is None or r['ROIC / ROE proxy']<=0:reason='Positive profitability evidence required'
        elif number(r['Operating margin']) is None or r['Operating margin']<=0:reason='Positive operating margin required'
        elif not r['Financial-sector treatment'] and number(r['Cash-flow yield']) is not None and r['Cash-flow yield']<=0:reason='Nonpositive free cash flow'
        if reason:excluded.append({'Ticker':symbol,'Reason':reason});continue
        try:
            model=prepare_projection_model(market,[symbol],year_columns,monthly_returns=monthly,use_monthly=True)
            if not model.credible:raise ValueError('Insufficient completed annual risk history')
            history,_=observed_blocks(model)
            if len(history)<24:raise ValueError('Fewer than 24 observed monthly returns')
            seed=cfg['seed']+int(hashlib.sha256(symbol.encode()).hexdigest()[:6],16)
            paths=generate_paths(model,context,cma,pcfg,cfg['years'],cfg['count'],seed)
            metrics=path_metrics(paths['returns'],paths['model_assignment'],cfg)
            row=r.to_dict();row.update(metrics)
            row['Expected Investment Return']=paths['decomposition'][0]['Expected geometric return']
            row['History months']=len(history)
            row['Confidence']='LOW — strategy unvalidated'
            fails=qualifies(row,cfg);row['Qualifies']=not fails;row['Failed constraints']=', '.join(fails)
            row['Why selected']=f"Quality {row['Quality score']:.0f}/100; model target chance {metrics['Target probability']:.0%}; loss >20% chance {metrics['Loss >20% probability']:.0%}; {len(history)} observed months."
            rows.append(row);audit[symbol]=paths['decomposition']
        except (ValueError,KeyError,np.linalg.LinAlgError) as exc:excluded.append({'Ticker':symbol,'Reason':str(exc)})
    table=pd.DataFrame(rows)
    leaders=table
    if not table.empty:
        table=table.sort_values(['Target probability','Quality score','Ticker'],ascending=[False,False,True]).reset_index(drop=True)
        leaders=table[table.Qualifies].groupby('Sector',sort=False).head(cfg['max_per_sector']).copy()
    return {'table':table,'leaders':leaders,'excluded':pd.DataFrame(excluded),'decomposition':audit,'settings':cfg,'planning':pcfg,'cma':cma,
        'model_version':MODEL_VERSION,'generated_at':datetime.now(timezone.utc).isoformat(),
        'data_through':context.get('history_through') or context.get('snapshot_as_of') or 'Unavailable',
        'universe_count':len(quality),'context_failures':context.get('failures',[]),
        'validation':'NOT VALIDATED — current universe has survivorship limitations; point-in-time fundamentals and delisted records not supplied.'}

def portfolio(market,year_columns,monthly,context,symbols,result,max_weight=.25,max_sector=.35):
    if not symbols or len(set(symbols))!=len(symbols):raise ValueError('Choose unique qualified holdings.')
    if len(symbols)>12:raise ValueError('This research portfolio supports up to 12 holdings to bound server workload.')
    table=result['table'].set_index('Ticker')
    if any(s not in table.index or not table.loc[s,'Qualifies'] for s in symbols):raise ValueError('Only stocks meeting all screen constraints can be included.')
    weight=1/len(symbols)
    allocation=table.loc[symbols].groupby('Sector').size()*weight
    if weight>max_weight+1e-9 or allocation.max()>max_sector+1e-9:raise ValueError('Selected holdings exceed position or sector limits. Add qualified diversifiers or explicitly change limits.')
    model=prepare_projection_model(market,symbols,year_columns,monthly_returns=monthly,use_monthly=True)
    history,_=observed_blocks(model)
    if len(history)<24:raise ValueError('At least 24 common observed months are required for joint correlation evidence.')
    cfg=result['settings'];paths=generate_paths(model,context,result['cma'],result['planning'],cfg['years'],cfg['count'],cfg['seed'])
    metrics={name:path_metrics(paths['returns'],paths['model_assignment'],cfg,rebalanced=rb) for name,rb in [('Rebalanced (yearly)',True),('Non-Rebalanced',False)]}
    w=np.ones(len(symbols))/len(symbols)
    for v in metrics.values():
        v['Quality score']=float(table.loc[symbols,'Quality score'].mean())
        v['Failed constraints']=', '.join(qualifies(v,cfg));v['Meets constraints']=not v['Failed constraints']
        v['Expected Investment Return']=float(np.mean([d['Expected geometric return'] for d in paths['decomposition'] if d['Year']==1]))
    return {'metrics':metrics,'sector_allocation':allocation.to_dict(),'holdings':symbols,
        'effective_independent_holdings':float(1/(w@paths['correlation']@w)),
        'correlation':paths['correlation'].tolist(),'common_months':len(history),
        'limitations':'Equal-weight research portfolio; yearly RB versus drifting NR. No withdrawals. Taxes excluded. Sector names do not eliminate shared factor risk; no complete factor exposure model.'}
