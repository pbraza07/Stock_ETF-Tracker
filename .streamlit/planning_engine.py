"""Forward Planning orchestration, diagnostics, scenarios and retirement solving."""
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from planning_assumptions import settings,forward_cma
from planning_paths import generate_paths
from planning_cashflows import simulate,sustainable_withdrawal,PCTS
from planning_validation import calibration,past_bias_adjustment

DISCLAIMER='Historical performance is used primarily to estimate risk characteristics and market behavior. Forward expected returns incorporate normalized fundamentals, valuation, macroeconomic conditions, capital-market assumptions, and uncertainty. Historical returns are not assumed to repeat.'

def stress_tests(paths,inputs,cfg,strategy):
    months=inputs['future_years']*12;n=len(inputs['holdings'])
    # Illustrative shocks, not claims of exact historical portfolio replay.
    schedules={'2000-2002 style technology collapse':[-.20,-.20,-.20], '2008-style financial crisis':[-.45],
        '2020-style sudden crash':[-.30,.25],'2022-style inflation/rate shock':[-.25],
        'Multi-year sideways market':[0.,0.,0.,0.,0.],'Decade of below-normal equities':[.01]*10,
        'Persistent 4-5% inflation':[.04]*10,'Elevated interest rates':[.03]*10,
        'Valuation compression':[-.15,-.10],'Concentrated-stock impairment':[]}
    output=[]
    for name,annual in schedules.items():
        r=np.full((months,1,n),np.expm1(np.log1p(.03)/12),dtype=float)
        for year,value in enumerate(annual[:inputs['future_years']]):r[year*12:(year+1)*12]=np.expm1(np.log1p(value)/12)
        if 'sudden crash' in name:r[:12]=0.;r[0]=-.30;r[1:12]=np.expm1(np.log1p(.25)/11)
        if 'impairment' in name:r[:,0,0]=0;r[0,0,0]=-.90
        inf=np.full((months,1),.045 if 'inflation' in name else cfg['inflation'])
        rates=np.full((months,1),.08 if 'rates' in name else .035)
        case=simulate(r,inputs,cfg,strategy,inf,rates,capture_balances=True)
        s=case['summary'];b=case['balances'][:,0];peak=inputs['starting_investment']-cfg['pal_balance']
        below=np.where(b<peak)[0];recovered=np.where(b>=peak)[0]
        recovery=next((int(i-below[0]) for i in recovered if len(below) and i>below[0]),None) if len(below) else 0
        output.append({'Strategy':strategy,'Stress':name,'Ending value':s['Median Ending Balance'],
            'Maximum drawdown':s['Maximum Drawdown (median)'],'Depletion year offset':s['Median Depletion Year (conditional)'],
            'Withdrawals funded (years)':s['Years of Withdrawals Funded'],'Recovery months to initial equity':recovery})
    return output

def run_planning(market,inputs,year_columns,monthly,live_context,data_as_of,progress=None):
    # Disk-backed scenario cubes avoid retaining hundreds of MB of anonymous RAM.
    # They contain intermediate simulated paths only and are removed on exit.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(prefix='marketscope-projection-') as workdir:
        return _run_planning(market,inputs,year_columns,monthly,live_context,data_as_of,progress,workdir)

def _run_planning(market,inputs,year_columns,monthly,live_context,data_as_of,progress,workdir):
    from future_projection import prepare_projection_model,ProjectionValidationError
    from future_projection_live import build_current_market_state
    cfg=settings(inputs.get('planning'));context=dict(live_context or {})
    context['fundamentals']={s:dict(v) for s,v in (context.get('fundamentals') or {}).items()}
    model=prepare_projection_model(market,inputs['holdings'],year_columns,monthly_returns=monthly,use_monthly=True)
    if not model.credible:raise ProjectionValidationError('At least three observed completed annual periods are required for risk estimation.')
    if cfg['pal_balance']>=inputs['starting_investment']*cfg['pal_maintenance']:raise ProjectionValidationError('Initial PAL exceeds the configured maintenance threshold.')
    cma=forward_cma(context,cfg)
    current=build_current_market_state(model.symbols,context)
    context['regime_probabilities']=current.get('regime_probabilities',{})
    for s,f in (context.get('fundamentals') or {}).items():
        f['momentum']=((current.get('holding_adjustments') or {}).get(s) or {}).get('return_200_day',0)
    records=cfg.get('validation_records') or []
    cutoff=pd.Timestamp(datetime.now(timezone.utc).date())
    records=[r for r in records if pd.Timestamp(r['End'])<=cutoff]
    # Supplied records must attest provenance; absent attestation cannot grant FULL status.
    if not cfg.get('verified_point_in_time_manifest'):
        records=[dict(r,Integrity='LIMITED',**{'Survivorship complete':False}) for r in records]
    bias=past_bias_adjustment(records,f"{inputs['forecast_start_year']}-01-01",1)
    cma['pre_calibration_return']=cma['geometric_return'];cma['bias_adjustment']=bias;cma['geometric_return']+=bias
    paths=generate_paths(model,context,cma,cfg,inputs['future_years'],inputs['simulation_count'],inputs['random_seed'],progress,workdir=workdir)
    names=['Rebalanced','Non-Rebalanced'] if inputs['strategy']=='Both' else [inputs['strategy']]
    weights=np.array([inputs['allocations'][s]/100 for s in inputs['holdings']]);weights/=weights.sum()
    cfg['custom_order_indices']=[inputs['holdings'].index(s) for s in cfg['custom_order'] if s in inputs['holdings']]
    cfg['custom_order_indices']+= [i for i in range(len(weights)) if i not in cfg['custom_order_indices']]
    strategies={};references={};agreement_rows=[];stresses=[];cases=[];sequences=[]
    for strategy in names:
        if progress:progress(1,4,f'{strategy}: calculating reference returns')
        reference_cfg=dict(cfg,pal_balance=0.)
        reference_inputs=dict(inputs,withdrawal_frequency='No Withdrawal',additional_contribution=0.)
        ref=simulate(paths['returns'],reference_inputs,reference_cfg,strategy,paths['inflation'],paths['rates'])
        cagr=(ref['ending']/inputs['starting_investment'])**(1/inputs['future_years'])-1
        medians=[]
        for k,label in enumerate(['Adaptive Monte Carlo','Centered Historical Bootstrap','Factor/CMA']):
            selected=cagr[paths['model_assignment']==k]
            if len(selected):
                median=float(np.median(selected));medians.append(median)
                agreement_rows.append({'Strategy':strategy,'Model':label,'P50 CAGR':median,'Paths':len(selected)})
        spread=float(np.ptp(medians)) if len(medians)>1 else 0.
        agreement='UNAVAILABLE' if len(medians)<2 else 'HIGH' if spread<.02 else 'MODERATE' if spread<.05 else 'LOW'
        # Plan under wider parameter uncertainty when models disagree; mean log return unchanged.
        rng=np.random.default_rng(inputs['random_seed']+903)
        uncertainty=rng.normal(size=(paths['returns'].shape[1],1))*spread/12
        from pathlib import Path
        plan_returns=np.memmap(Path(workdir)/('planning-'+strategy+'.bin'),mode='w+',dtype=np.float32,shape=paths['returns'].shape)
        for month in range(len(plan_returns)):
            original=paths['returns'][month]
            adjusted=np.expm1(np.log1p(original)+uncertainty).astype(np.float32)
            adjusted[original==0]=0
            plan_returns[month]=adjusted
        plan_returns.flush()
        if progress:progress(2,4,f'{strategy}: calculating spending, taxes and borrowing')
        plan_paths=dict(paths,returns=plan_returns)
        case=simulate(plan_returns,inputs,cfg,strategy,paths['inflation'],paths['rates'])
        case['summary']['Expected Investment Return']=float(np.dot(weights,[r['Expected geometric return'] for r in paths['decomposition'][:len(weights)]]))
        case['summary']['Planning Return']=float(np.percentile(cagr,max(1,cfg['planning_percentile']-(10 if agreement=='LOW' else 5 if agreement=='MODERATE' else 0))))
        case['summary']['Median Simulated CAGR (reference)']=float(np.median(cagr))
        case['summary']['Model Agreement']=agreement
        if cfg['solve_withdrawal']:
            if progress:progress(1,2,'Solving sustainable net spending with taxes, inflation and PAL')
            case['sustainable']=sustainable_withdrawal(plan_paths,inputs,cfg,strategy)
        else:case['sustainable']={'status':'Not requested'}
        # Sequence tests use same shock moved in time, on a disclosed subset.
        k=min(500,len(cagr));base=plan_returns[:,:k]
        if progress:progress(3,4,f'{strategy}: calculating sequence and stress tests')
        for name,start in ([('Early bear',0),('Middle bear',max(0,len(base)//2-6)),('Late bear',max(0,len(base)-12))] if cfg.get('run_diagnostics',True) else []):
            stressed=base.copy();stressed[start:start+12]=np.expm1(np.log1p(stressed[start:start+12])+np.log(.65)/12)
            seq=simulate(stressed,inputs,cfg,strategy,paths['inflation'][:,:k],paths['rates'][:,:k],detail=False)
            sequences.append({'Strategy':strategy,'Sequence':name,'Survival probability':seq['summary']['Portfolio Survival Probability'],
                'Fully funded probability':seq['summary']['Probability Spending Is Fully Funded'],'Median ending':seq['summary']['Median Ending Balance'], 'Paths':k})
        for name,shift,extra_inf,extra_fee,volscale in ([('Conservative',-.02,.01,.002,1.2),('Base',0.,0.,0.,1.),('Optimistic',.02,-.005,0.,.9)] if cfg.get('run_diagnostics',True) else []):
            casecfg=dict(cfg,advisory_fee=cfg['advisory_fee']+extra_fee)
            logs=np.log1p(base);mean=logs.mean(axis=1,keepdims=True)
            adjusted=np.expm1(mean+(logs-mean)*volscale+shift/12)
            cc=simulate(adjusted,inputs,casecfg,strategy,np.maximum(0,paths['inflation'][:,:k]+extra_inf),paths['rates'][:,:k],detail=False)
            cases.append({'Strategy':strategy,'Planning case':name,'Return assumption shift':shift,'Inflation shift':extra_inf,
                'Extra annual fees':extra_fee,'Volatility scale':volscale,'Survival':cc['summary']['Portfolio Survival Probability'],
                'Spending funded':cc['summary']['Probability Spending Is Fully Funded'],'Median ending':cc['summary']['Median Ending Balance']})
        if cfg.get('run_diagnostics',True):
            stress_rows=stress_tests(paths,inputs,cfg,strategy);stresses.extend(stress_rows)
            case['summary']['Worst illustrative stress ending value']=min(row['Ending value'] for row in stress_rows)
        # Keep exports compact; no huge per-path cubes in session-saved results.
        for key in ('balances','ending','fully_funded','surviving','drawdown','final_holdings','final_basis'):case.pop(key,None)
        strategies[strategy]=case;references[strategy]=ref['table']
        del ref,plan_paths,base,plan_returns
    corr=paths['correlation'];cov=paths['risk_covariance'];portvar=weights@cov@weights
    contribution=weights*(cov@weights)/max(portvar,1e-12)
    sectors={c:float(sum(w for w,cat in zip(weights,model.categories) if cat==c)) for c in set(model.categories)}
    trust=calibration(records)
    trust.update({'Live Data Status':current.get('status','See freshness'),'Forward CMA confidence':cma['confidence'],
        'Forward CMA freshness':cma['refreshed_at'],'Historical depth':model.diagnostics,
        'Model Agreement':{s:case['summary']['Model Agreement'] for s,case in strategies.items()},
        'Forward CMA unavailable components':cma['missing_components'],'Bootstrap evidence':'Observed monthly blocks' if paths['bootstrap_available'] else 'Unavailable; weight transferred to Monte Carlo',
        'Structural probabilities':'Configured scenario assumptions, not validated forecasts'})
    warnings=list(model.warnings)+['Research planning engine: forward coefficients, regime probabilities, impairment hazards and percentile coverage are not empirically certified.',
        'Historical calibration contains survivorship limitations unless a verified point-in-time dataset is supplied.',
        'Taxes use estimated average cost, no loss offsets, brackets, tax lots, deductions or early-distribution penalties. Tax-aware selling minimizes estimated current tax only.',
        'PAL maintenance is evaluated monthly; real lenders can demand immediate repayment. Borrowed proceeds are external and are not counted as portfolio income.',
        'Stress tests are illustrative designs, not exact historical portfolio replays. Recovery measures account equity after spending.']
    return {'planning_engine':True,'inputs':inputs,'settings':cfg,'strategies':strategies,'references':references,'cma':cma,
        'decomposition':pd.DataFrame(paths['decomposition']),'agreement':pd.DataFrame(agreement_rows),
        'stress_tests':pd.DataFrame(stresses),'planning_cases':pd.DataFrame(cases),'sequence_tests':pd.DataFrame(sequences),
        'trust':trust,'current_market_state':current,'warnings':warnings,'methodology':DISCLAIMER,
        'concentration':{'Holding HHI':float(weights@weights),'Sector weights':sectors,
            'Effective independent holdings (correlation approximation)':float(1/max(weights@corr@weights,1e-9)),
            'Top risk contributor':model.symbols[int(np.argmax(contribution))],'Risk contributions':dict(zip(model.symbols,contribution.tolist())),
            'Factor concentration':'See current market portfolio diagnostics; no complete factor exposures available'},
        'audit':{'model_version':'5.11.38','risk_covariance':cov.tolist(),'risk_source':paths['risk_source'],'regime_correlations':paths['regime_correlations'],
            'regime_parameters':paths['scenario_parameters'],'transition_matrix':paths['transition_matrix'],
            'parameters':cfg,'simulation_count':inputs['simulation_count'],'seed':inputs['random_seed'],
            'data_as_of':data_as_of,'impairment_events':paths['impairment_events'],
            'return_definition':'Drift is expected log growth converted to geometric return before impairment/gaps and costs; arithmetic expectation is separately estimated from paths.',
            'arithmetic_first_year_per_security':(np.prod(1+paths['returns'][:12].astype(float),axis=0)-1).mean(axis=0).tolist(),
            'planning_return_definition':'Lower-percentile terminal no-spending CAGR, percentile lowered when models disagree. Solver uses full widened paths, not a flat Planning Return.',
            'impairment_recovery':'Impaired slot becomes cash with zero subsequent return; no automatic replacement security.',
            'bootstrap_definition':'Centered observed monthly sequences rescaled around forward drift; historical mean removed.'}}
