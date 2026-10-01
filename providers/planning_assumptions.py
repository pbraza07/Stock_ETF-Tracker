"""Forward economic assumptions. No selected-stock CAGR enters expected return."""
from copy import deepcopy
from datetime import datetime, timezone
import numpy as np

WEIGHTS = {'valuation': .30, 'erp': .20, 'macro': .20, 'institutional': .20, 'history': .10}
SIGNALS = [(3, 1., 1., 1.), (7, .35, .65, .5), (15, .03, .35, .15), (50, 0., .15, 0.)]
DEFAULTS = {
    'cma_weights': WEIGHTS, 'signal_weights': SIGNALS, 'return_bounds': [-.08, .18],
    'equity_risk_premium': .035, 'normalized_real_growth': .015,
    'expected_return_uncertainty': .03, 'impairment_base_probability': .002,
    'impairment_severity': .70, 'gap_probability': .01, 'gap_loss': .15,
    'ensemble_weights': [.5, .25, .25], 'block_months': [3, 6, 12, 24],
    'planning_percentile': 25, 'desired_survival': .90, 'solve_withdrawal': True,
    'solver_paths': 1000, 'inflation_adjusted': True, 'inflation': .025,
    'account': 'Taxable', 'tax_enabled': False, 'federal_rate': .22, 'state_rate': 0.,
    'capital_gains_rate': .15, 'taxable_weight': .5, 'deferred_weight': .5,
    'basis_fraction': 1., 'expense_ratio': .001, 'advisory_fee': 0.,
    'trading_friction': .0005, 'bid_ask': .0005, 'tax_drag': 0.,
    'sale_method': 'Proportional', 'custom_order': [], 'pal_balance': 0.,
    'pal_rate': .08, 'pal_variable': False, 'pal_spread': .03,
    'pal_interest': 'Portfolio', 'pal_ltv': .50, 'pal_maintenance': .65,
    'goal': 'Fully fund spending', 'goal_amount': 0., 'goal_real': True,
}

def number(value, default=None):
    try:
        v = float(value)
        return v if np.isfinite(v) else default
    except (ValueError, TypeError):
        return default

def settings(values=None):
    out=deepcopy(DEFAULTS); out.update(values or {})
    for key in ('inflation','expense_ratio','advisory_fee','trading_friction','bid_ask','tax_drag',
                'federal_rate','state_rate','capital_gains_rate','basis_fraction','pal_rate','pal_spread',
                'pal_ltv','pal_maintenance','desired_survival','impairment_base_probability','impairment_severity'):
        if number(out[key]) is None or not (0 <= float(out[key]) <= 1 if key=='basis_fraction' else 0 <= float(out[key]) < 1):
            raise ValueError(key+' must be a finite fraction from 0 to less than 1.')
    if not 0 < out['pal_ltv'] < out['pal_maintenance'] < 1:
        raise ValueError('PAL target LTV must be below maintenance threshold and 100%.')
    if sum(out['ensemble_weights']) <= 0 or min(out['ensemble_weights']) < 0:
        raise ValueError('Model weights must be nonnegative and sum to a positive value.')
    if not 1 <= out['planning_percentile'] < 50:
        raise ValueError('Planning percentile must be below the median and at least 1.')
    if out['taxable_weight']+out['deferred_weight']>1 or min(out['taxable_weight'],out['deferred_weight'])<0:
        raise ValueError('Blended account weights must total no more than 100%; remainder is Roth.')
    if out['pal_balance'] < 0: raise ValueError('PAL balance cannot be negative.')
    return out

def forward_cma(context, cfg):
    """Missing independent components are omitted, not replaced by 7%."""
    supplied=cfg.get('cma_inputs') or {}
    macro=context.get('macro') or {}
    treasury=number(supplied.get('treasury_yield'))
    rate_record=macro.get('treasury_10y') or {}
    if treasury is None: treasury=number(rate_record.get('value'))
    elif treasury is not None: rate_record={'observation_date':supplied.get('as_of'),'source':'User assumption'};treasury*=100
    treasury=treasury/100 if treasury is not None else None
    inflation=number(supplied.get('inflation_expectation'))
    inflation_source='Explicit user inflation expectation'
    inflation_date=supplied.get('as_of')
    if inflation is None:
        breakeven=number((macro.get('inflation_expectation') or {}).get('value'))
        inflation=breakeven/100 if breakeven is not None else cfg['inflation']
        inflation_source='FRED T10YIE breakeven proxy (includes risk/liquidity premia)' if breakeven is not None else 'Configured planning inflation assumption'
        inflation_date=(macro.get('inflation_expectation') or {}).get('observation_date') if breakeven is not None else None
    rows=[]
    def add(name,value,source,asof,detail):
        if value is not None and np.isfinite(value):
            rows.append({'Component':name,'Return':float(value),'Configured weight':cfg['cma_weights'].get(name,0),
                         'Source':source,'Source date':asof or 'Not supplied','Formula / assumptions':detail})
    pe=number(supplied.get('forward_pe')); growth=number(supplied.get('earnings_growth'))
    dividend=number(supplied.get('dividend_yield')); normalized_pe=number(supplied.get('normalized_pe'))
    if pe and pe>0 and growth is not None and dividend is not None and normalized_pe and normalized_pe>0:
        valuation=(normalized_pe/pe)**.1-1
        # Dividend + EPS growth + annualized multiple change; earnings yield informs ERP separately.
        add('valuation',dividend+growth+valuation,'Dated market fundamentals',supplied.get('as_of'),
            f'Dividend {dividend:.4f} + EPS growth {growth:.4f} + 10-year multiple change {valuation:.4f}; earnings yield {1/pe:.4f}; valuation percentile {supplied.get("valuation_percentile","unavailable")}')
    if treasury is not None:
        add('erp',treasury+cfg['equity_risk_premium'],'FRED DGS10 or explicit rate; assumed ERP',rate_record.get('observation_date'),
            f'Treasury {treasury:.4f} + configured ERP {cfg["equity_risk_premium"]:.4f}')
        add('macro',(1+inflation)*(1+cfg['normalized_real_growth'])*(1+cfg['equity_risk_premium'])-1,
            inflation_source+'; configured normalized real growth / ERP',inflation_date,
            f'Inflation {inflation:.4f}; normalized real growth {cfg["normalized_real_growth"]:.4f}; ERP {cfg["equity_risk_premium"]:.4f}. Shares ERP with rates model; not independent evidence.')
    providers=[x for x in supplied.get('institutional',[]) if number(x.get('return')) is not None and x.get('source') and x.get('as_of')]
    if providers:
        # One observation per named provider avoids duplicated source votes.
        unique={x['source']:x for x in providers}
        add('institutional',np.mean([x['return'] for x in unique.values()]),'; '.join(unique),
            '; '.join(x['as_of'] for x in unique.values()),'Equal provider mean; annual nominal geometric equity assumptions required')
    h=number(supplied.get('long_run_market_return'))
    if h is not None and supplied.get('history_source'):
        add('history',h,supplied['history_source'],supplied.get('as_of'),'Broad-market long-run evidence, never selected-stock CAGR')
    total=sum(max(0,r['Configured weight']) for r in rows)
    if total<=0: raise ValueError('Forward CMA unavailable. Refresh FRED rates or enter a dated Treasury/market assumption in Planning settings. No fixed 7% fallback is used.')
    for r in rows: r['Effective weight']=max(0,r['Configured weight'])/total
    anchor=sum(r['Return']*r['Effective weight'] for r in rows)
    uncertainty=max(cfg['expected_return_uncertainty'],float(np.std([r['Return'] for r in rows])))
    return {'geometric_return':anchor,'components':rows,'missing_components':[k for k in WEIGHTS if k not in [r['Component'] for r in rows]],
            'assumption_range':[anchor-uncertainty,anchor+uncertainty],'confidence':'LOW' if len(rows)<4 else 'MODERATE',
            'range_definition':'Assumption sensitivity range, not a statistically calibrated confidence interval',
            'refreshed_at':context.get('retrieved_at') or datetime.now(timezone.utc).isoformat()}

def signal_weights(year,cfg):
    for end,short,durable,sector in cfg['signal_weights']:
        if year<=end: return short,durable,sector
    return 0.,0.,0.

def decomposition(symbol,category,fundamental,anchor,year,cfg):
    short,durable,sector=signal_weights(year,cfg)
    f=fundamental or {}; rows={'Market anchor':anchor}
    pe=number(f.get('forward_pe')); earnings=number(f.get('forward_eps_growth'),number(f.get('earnings_growth')))
    margin=number(f.get('operating_margin')); leverage=number(f.get('debt_to_equity'))
    quality=number(f.get('return_on_invested_capital'),number(f.get('return_on_equity')))
    rows['Sector economics']=float((cfg.get('sector_adjustments') or {}).get(category,0))*sector
    rows['Earnings growth']=float(np.clip((earnings or 0)*.10,-.04,.03))*short
    rows['Valuation']=float(np.clip(np.log(20/pe)/10,-.08,.04))*durable if pe and pe>0 else 0.
    rows['Quality / ROIC proxy']=float(np.clip(((quality or .10)-.10)*.10,-.025,.02))*durable
    rows['Balance sheet']=(-min(.04,max(0,(leverage or 0)-100)/10000))*durable
    rows['Margin quality']=float(np.clip((margin-.10)*.10,-.04,.02))*durable if margin is not None else 0.
    rows['Analyst revisions']=float(np.clip(number(f.get('eps_revision_direction'),0)*.005,-.015,.015))*short
    rows['Momentum']=float(np.clip(number(f.get('momentum'),0)*.02,-.01,.01))*short
    rows['Dilution']= -float(np.clip(number(f.get('share_dilution'),0)*.2,0,.03))*durable
    rows['Historical alpha']=0. # Deliberate separation from selection and historical CAGR.
    raw=sum(rows.values()); final=float(np.clip(raw,*cfg['return_bounds']))
    rows['Bounds adjustment']=final-raw
    completeness=sum(number(f.get(k)) is not None for k in ('forward_pe','earnings_growth','operating_margin','debt_to_equity','return_on_equity'))
    confidence='MODERATE' if completeness>=4 else 'LOW'
    uncertainty=cfg['expected_return_uncertainty']*(1 if confidence=='MODERATE' else 1.75)*(1+.025*min(year-1,30))
    hazard=cfg['impairment_base_probability']*(1+min(3,max(0,(leverage or 0)-100)/100)+(2 if margin is not None and margin<0 else 0)+(1 if number(f.get('market_cap'),1e11)<2e9 else 0))
    hazard*=float((cfg.get('sector_impairment_multipliers') or {}).get(category,1))
    return {'Ticker':symbol,'Year':year,**rows,'Expected geometric return':final,
            'Expected return confidence':confidence,'Parameter uncertainty':uncertainty,
            'Annual impairment probability':min(.10,hazard),
            'Impairment loss severity':min(.99,cfg['impairment_severity']+max(0,(leverage or 0)-100)/4000+(.10 if margin is not None and margin<0 else 0)),
            'Short signal weight':short,'Durable signal weight':durable,
            'Missing evidence':'Analyst dispersion / business stability unverified; ROE proxy where ROIC unavailable'}
