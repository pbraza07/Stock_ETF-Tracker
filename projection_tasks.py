"""Importable worker entry points: data acquisition and mathematics, no UI state."""
from functools import partial
from shared_cache import cached

def live_context(symbols,market):
    from providers import YahooFinanceProvider
    from future_projection_live import fetch_live_projection_context
    # Retain relevant fundamentals/sector snapshot as key; exclude volatile quote columns.
    selected=market.loc[market.Symbol.isin(symbols)].copy()
    stable=selected.drop(columns=[c for c in selected.columns if c in {'Price','Current Price','1D','Last Updated','Price Updated ET'}],errors='ignore')
    return cached('projection-context',(tuple(sorted(symbols)),stable),
        lambda:fetch_live_projection_context(YahooFinanceProvider(),tuple(sorted(symbols)),selected),
        ttl=1800,default={},valid=lambda v:bool(v))

def monthly_history(symbols,years):
    from projection_data_service import cached_future_projection_monthly_returns
    return cached('monthly-observed',(tuple(sorted(symbols)),tuple(years)),
        lambda:cached_future_projection_monthly_returns(tuple(sorted(symbols)),tuple(years)),
        ttl=21600,default={},valid=lambda v:bool(v) and not v.get('unavailable'))

def projection(market,inputs,years,data_as_of,model_as_of,progress):
    from future_projection import run_future_projection
    progress(0,3,'Loading observed histories')
    needs=inputs.get('planning_engine') or inputs['withdrawal_frequency']=='Monthly' or (inputs['strategy'] in {'Rebalanced','Both'} and inputs['rebalancing_frequency'] in {'Quarterly','Monthly'})
    monthly=monthly_history(inputs['holdings'],years) if needs else {}
    progress(1,3,'Loading current fundamentals and macro')
    context=live_context(inputs['holdings'],market)
    if inputs.get('planning_engine'):
        from projection_macro import fetch_one
        try:
            _,series=fetch_one('inflation_expectation','T10YIE')
            context.setdefault('macro',{})['inflation_expectation']=series
        except Exception:context.setdefault('failures',[]).append('Breakeven inflation unavailable; explicit planning inflation assumption used.')
    progress(2,3,'Starting simulation')
    result=run_future_projection(market,inputs,years,monthly,data_as_of,model_as_of,progress,context)
    from uuid import uuid4
    result['_report_identity']=uuid4().hex
    return result

def quality(market,years,cfg,planning,progress):
    from quality_opportunities import universe,screen
    from opportunity_data import retain_observed_fundamentals
    stocks=tuple(universe(market).Symbol)
    progress(0,3,'Loading fundamental and macro sources')
    context=dict(live_context(stocks,market),requested_symbols=list(stocks))
    context=retain_observed_fundamentals(context)
    progress(1,3,'Loading actual monthly history')
    monthly=monthly_history(stocks,years)
    result=screen(market,years,monthly,context,cfg,planning,progress)
    return dict(result=result,market=market.copy(),monthly=monthly,context=context,years=list(years))

def quality_portfolio(bundle,selected,maxweight,maxsector,progress):
    from quality_opportunities import portfolio
    progress(0,1,'Evaluating portfolio')
    return portfolio(bundle['market'],bundle['years'],bundle['monthly'],bundle['context'],selected,bundle['result'],maxweight,maxsector)
