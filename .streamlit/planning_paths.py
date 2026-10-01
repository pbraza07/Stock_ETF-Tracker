"""Monthly joint paths; historical returns estimate risk, not persistent alpha."""
import numpy as np
import pandas as pd
from planning_assumptions import decomposition

# Return/log adjustment, volatility, correlation mix, inflation, short rate.
# Explicit stress design assumptions, not estimated transition probabilities.
SCENARIOS={
 'Normal Expansion':(0.,1.,.03,.025,.035),
 'Low-Growth Expansion':(-.025,1.05,.10,.02,.025),
 'Inflationary Expansion':(-.01,1.15,.12,.045,.055),
 'Conventional Recession':(-.14,1.5,.35,.02,.025),
 'Severe Recession':(-.32,2.,.65,.01,.01),
 'Stagflation':(-.12,1.6,.45,.055,.065),
 'Valuation Compression':(-.09,1.3,.25,.025,.045),
 'Productivity/AI Boom':(.08,1.15,.08,.02,.03),
 'High-Rate Structural Environment':(-.035,1.2,.20,.035,.07),
}

def stress_correlation(correlation,mix):
    n=len(correlation)
    result=(1-mix)*correlation+mix*np.ones((n,n))
    np.fill_diagonal(result,1.)
    eig,vec=np.linalg.eigh(result)
    result=(vec*np.maximum(eig,1e-8))@vec.T
    d=np.sqrt(np.diag(result));return result/np.outer(d,d)

def observed_blocks(model):
    h=model.historical_returns
    h=h[h['Data Status'].eq('Observed') & h['Frequency'].eq('Monthly')]
    if h.empty:return np.empty((0,len(model.symbols))),[]
    pivot=h.pivot_table(index='Period',columns='Ticker',values='Return',aggfunc='last').reindex(columns=model.symbols).dropna().sort_index()
    if pivot.empty:return np.empty((0,len(model.symbols))),[]
    periods=pd.PeriodIndex(pivot.index,freq='M').asi8
    return np.log1p(np.clip(pivot.to_numpy(),-.999999,None)),periods

def log_covariance(model):
    h=model.historical_returns
    for freq,factor,minimum in [('Monthly',12,12),('Annual',1,3)]:
        data=h[h['Data Status'].eq('Observed') & h['Frequency'].eq(freq)]
        if data.empty:continue
        matrix=data.pivot_table(index='Period',columns='Ticker',values='Return',aggfunc='last').reindex(columns=model.symbols).dropna()
        if len(matrix)<minimum:continue
        logs=np.log1p(np.clip(matrix.to_numpy(),-.999999,None))
        cov=np.atleast_2d(np.cov(logs,rowvar=False))*factor
        # Stabilize covariance without using historical mean for forward drift.
        return .8*cov+.2*np.diag(np.maximum(np.diag(cov),.0001)),freq+' observed log-return covariance'
    return np.asarray(model.annual_covariance),'Fallback covariance proxy; insufficient joint log-return evidence'

def generate_paths(model,context,cma,cfg,years,count,seed,progress=None,workdir=None):
    months=years*12;n=len(model.symbols)
    if months*count*n*4>300_000_000:
        raise ValueError('This planning run exceeds the memory budget. Reduce simulation quality or holdings; requested paths are never silently reduced.')
    # Per-path parameter uncertainty and period draws are horizon independent.
    rng=np.random.default_rng(seed)
    if workdir:
        from pathlib import Path
        returns=np.memmap(Path(workdir)/'scenarios.bin',mode='w+',shape=(months,count,n),dtype=np.float32)
    else:returns=np.empty((months,count,n),dtype=np.float32)
    inflation=np.empty((months,count),dtype=np.float32);rates=np.empty_like(inflation)
    cov,risk_source=log_covariance(model)
    vol=np.sqrt(np.maximum(np.diag(cov),.0001)); corr=cov/np.outer(vol,vol);np.fill_diagonal(corr,1.)
    scenario_config=cfg.get('scenarios') or SCENARIOS
    names=list(scenario_config);params=np.array(list(scenario_config.values()),float)
    probabilities=np.asarray(cfg.get('scenario_probabilities',[.40,.13,.10,.08,.025,.035,.08,.08,.07]),float)
    if len(probabilities)!=len(names) or min(probabilities)<0 or probabilities.sum()<=0:raise ValueError('Invalid structural scenario probabilities.')
    probabilities/=probabilities.sum()
    transition=np.asarray(cfg.get('transition_matrix',.96*np.eye(len(names))+.04*np.tile(probabilities,(len(names),1))),float)
    if transition.shape!=(len(names),len(names)) or (transition<0).any() or not np.allclose(transition.sum(1),1):raise ValueError('Invalid structural transition matrix.')
    initial=probabilities.copy()
    # Current conditions affect only the start; persistent transitions evolve thereafter.
    bear=float((context.get('regime_probabilities') or {}).get('Bear',.18))
    if bear>1:bear/=100
    initial[3:6]*=1+max(0,bear)*2;initial/=initial.sum()
    regime=rng.choice(len(names),count,p=initial)
    mixture=np.array(cfg['ensemble_weights'],float);mixture/=mixture.sum()
    assignment=rng.choice(3,count,p=mixture)
    parameter_shock=rng.normal(size=(count,n))
    history,ordinals=observed_blocks(model);history=history-history.mean(axis=0) if len(history) else history
    blocks=[int(b) for b in cfg['block_months'] if 1<=b<=len(history)]
    starts={b:np.array([i for i in range(len(history)-b+1) if ordinals[i+b-1]-ordinals[i]==b-1]) for b in blocks}
    blocks=[b for b in blocks if len(starts[b])]
    if not blocks:assignment[assignment==1]=0
    cursor=np.zeros(count,dtype=int);remaining=np.zeros(count,dtype=int)
    dead=np.zeros((count,n),bool);cluster=np.ones(count)
    roots=[np.linalg.cholesky(stress_correlation(corr,p[2])) for p in params]
    annual=[];fund=context.get('fundamentals') or {}
    for year in range(1,years+1):
        annual.append([decomposition(s,c,fund.get(s),cma['geometric_return'],year,cfg) for s,c in zip(model.symbols,model.categories)])
    # Center structural mean adjustments under governed long-run probabilities.
    centered=params[:,0]-probabilities@params[:,0]
    impairment_count=0
    for m in range(months):
        if m:
            u=rng.random(count);regime=(u[:,None]>np.cumsum(transition[regime],axis=1)).sum(1).clip(0,len(names)-1)
        d=annual[m//12];means=np.array([v['Expected geometric return'] for v in d]);uncert=np.array([v['Parameter uncertainty'] for v in d])
        z=rng.standard_t(6,size=(count,n))*np.sqrt(4/6)
        # Bounded log shocks keep moments finite; no unbounded exponential Student-t claim.
        z=np.clip(z,-8,8)
        shocks=np.empty_like(z)
        for k in range(len(names)):
            mask=regime==k;shocks[mask]=z[mask]@roots[k].T
        scale=params[regime,1]*np.sqrt(cluster)
        risk=shocks*vol[None,:]/np.sqrt(12)*scale[:,None]
        boot=assignment==1
        if boot.any():
            reset=np.where(boot & (remaining==0))[0]
            # Independent uniform block selection, no fixed 6-month replay.
            chosen=rng.choice(blocks,len(reset)) if len(reset) else []
            for b in blocks:
                indices=reset[np.asarray(chosen)==b]
                if len(indices):cursor[indices]=rng.choice(starts[b],len(indices));remaining[indices]=b
            risk[boot]=history[cursor[boot]]*scale[boot,None]
            cursor[boot]+=1;remaining[boot]-=1
        factor=assignment==2
        drift=np.broadcast_to(np.log1p(means),(count,n)).copy()
        # Factor model deliberately shrinks security adjustments toward forward CMA.
        drift[factor]=.75*np.log1p(cma['geometric_return'])+.25*np.log1p(means)
        drift+=(parameter_shock*uncert[None,:])
        logret=drift/12+centered[regime,None]/12+risk
        gaps=rng.random((count,n))<cfg['gap_probability']/12
        logret+=gaps*np.log1p(-cfg['gap_loss'])
        hazard=np.array([v['Annual impairment probability'] for v in d])
        hazard=np.where(np.array(model.types)=='ETF',0,hazard)
        event=(rng.random((count,n))<(1-(1-hazard)**(1/12)))[...] & ~dead
        # Permanent destruction: remaining recovery value becomes zero-return cash; no rebound of failed stock.
        current=np.expm1(np.clip(logret,-12,2))
        current[dead]=0.
        severity=np.broadcast_to([v['Impairment loss severity'] for v in d],current.shape)
        current[event]=-severity[event];dead|=event
        impairment_count+=int(event.sum());returns[m]=current
        inflation[m]=np.clip(cfg['inflation']+(params[regime,3]-.025),0,.15)
        rates[m]=params[regime,4]
        cluster=np.clip(.94*cluster+.06*np.mean(z*z,axis=1),.5,3)
        if progress and (m%3==0 or m==months-1):progress(m+1,months,f'Generating {count:,} forward paths: forecast months')
    if isinstance(returns,np.memmap):returns.flush()
    return {'returns':returns,'inflation':inflation,'rates':rates,'model_assignment':assignment,
            'decomposition':[r for year in annual for r in year], 'correlation':corr,
            'regime_correlations':{k:stress_correlation(corr,p[2]).tolist() for k,p in zip(names,params)},
            'bootstrap_available':bool(blocks),'impairment_events':impairment_count,
            'scenario_parameters':scenario_config,'transition_matrix':transition.tolist(),
            'risk_covariance':cov,'risk_source':risk_source}
