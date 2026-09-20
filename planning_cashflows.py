"""Pathwise monthly ledger with average-cost estimated taxes and PAL liabilities."""
import numpy as np
import pandas as pd

PCTS=[10,25,50,75,90]

def tax_rates(cfg,balance,basis,internal=False):
    if not cfg['tax_enabled']:return np.zeros_like(balance)
    ordinary=min(.95,cfg['federal_rate']+cfg['state_rate'])
    gains=min(.95,cfg['capital_gains_rate']+cfg['state_rate'])
    frac=np.clip(1-np.divide(basis,balance,out=np.ones_like(balance),where=balance>0),0,1)
    account=cfg['account']
    taxable=1 if account=='Taxable' else cfg['taxable_weight'] if account=='Blended' else 0
    deferred=1 if account=='Tax-deferred' else cfg['deferred_weight'] if account=='Blended' else 0
    return taxable*gains*frac + (0 if internal else deferred*ordinary)

def liquidate(holdings,basis,net_needed,cfg,target,last_returns,method=None):
    """Sales target spendable cash, not gross proceeds. Updates basis proportionally."""
    needed=np.maximum(np.asarray(net_needed),0).copy();net=np.zeros_like(needed);tax=np.zeros_like(net);gross=np.zeros_like(net)
    sales=np.zeros_like(holdings);method=method or cfg['sale_method']
    rates=tax_rates(cfg,holdings,basis);friction=cfg['trading_friction']+cfg['bid_ask']
    keep=np.maximum(.01,1-rates-friction)
    if method=='Proportional':
        capacity=(holdings*keep).sum(1)
        portion=np.clip(np.divide(needed,capacity,out=np.zeros_like(needed),where=capacity>0),0,1)
        sales=holdings*portion[:,None]
    else:
        if method=='Overweight first':priority=holdings-holdings.sum(1)[:,None]*target
        elif method=='Strongest first':priority=last_returns
        elif method=='Weakest first':priority=-last_returns
        elif method=='Tax-aware':priority=-rates
        else:
            order=cfg.get('custom_order_indices',list(range(holdings.shape[1])))
            priority=np.broadcast_to(-np.argsort(order),(len(holdings),len(order)))
        order=np.argsort(-priority,axis=1,kind='stable');paths=np.arange(len(holdings))
        for rank in range(holdings.shape[1]):
            j=order[:,rank];amount=np.minimum(holdings[paths,j],needed/keep[paths,j])
            sales[paths,j]=amount;needed-=amount*keep[paths,j]
    ratio=np.divide(sales,holdings,out=np.zeros_like(sales),where=holdings>0)
    basis*=1-ratio;holdings-=sales
    gross=sales.sum(1);tax=(sales*rates).sum(1);net=(sales*keep).sum(1)
    return net,gross,tax,sales,gross*friction

def simulate(returns,inputs,cfg,strategy,inflation=None,rates=None,annual_spending=None,detail=True,capture_balances=False):
    months,count,n=returns.shape;weights=np.array([inputs['allocations'][s]/100 for s in inputs['holdings']]);weights/=weights.sum()
    initial=inputs['starting_investment'];h=np.tile(initial*weights,(count,1));basis=h*cfg['basis_fraction']
    debt=np.full(count,float(cfg['pal_balance']));initial_equity=initial-cfg['pal_balance']
    cpi=np.ones(count);cumulative=np.zeros(count);gross_total=np.zeros(count);tax_total=np.zeros(count);fees_total=np.zeros(count)
    fully=np.ones(count,bool);floor_ok=np.ones(count,bool);depleted=np.full(count,np.nan);funded=np.zeros(count)
    peak=np.full(count,max(initial_equity,1));drawdown=np.zeros(count);maintenance=np.zeros(count,bool)
    balances=[];records=[];funding=[];last=np.zeros((count,n));peak_month=np.zeros(count);recovery=np.zeros(count);underwater=np.zeros(count)
    annual=annual_spending if annual_spending is not None else (inputs['monthly_withdrawal']*12 if inputs['withdrawal_frequency']=='Monthly' else inputs['annual_withdrawal'])
    if inputs['withdrawal_frequency']=='No Withdrawal' and annual_spending is None:annual=0.
    frequency=inputs['withdrawal_frequency'];begin=inputs['withdrawal_timing']=='Beginning of period'
    def withdraw(m):
        due=(frequency=='Monthly') or ((m%12==0) if begin else (m%12==11))
        nominal=annual/(12 if frequency=='Monthly' else 1) if due else 0.
        # Escalate once each anniversary: Year 1 retains requested purchasing power.
        wanted=np.full(count,nominal)*(year_cpi if cfg['inflation_adjusted'] else 1)
        net,gross,tax,sales,cost=liquidate(h,basis,wanted,cfg,weights,last)
        return wanted,net,gross,tax,sales,cost
    year_cpi=cpi.copy()
    for m in range(months):
        opening=h.sum(1)-debt
        if m%12==0:year_cpi=cpi.copy()
        contribution=inputs.get('additional_contribution',0) if frequency=='Monthly' or m%12==0 else 0
        h+=contribution*weights;basis+=contribution*weights
        if begin:wanted,net,gross,tax,sales,cost=withdraw(m)
        invested=h.copy();h*=np.maximum(0,1+returns[m]);last=returns[m]
        investment_profit=(h-invested).sum(1)
        fee=1-(1-min(.99,cfg['expense_ratio']+cfg['advisory_fee']+cfg['tax_drag']+inputs.get('annual_management_fee',0)))**(1/12)
        fee_amount=h.sum(1)*fee;h*=1-fee
        rate=(rates[m]+cfg['pal_spread']) if cfg['pal_variable'] and rates is not None else cfg['pal_rate']
        interest=debt*np.asarray(rate)/12
        if cfg['pal_interest']=='Capitalize':debt+=interest
        else:
            paid,_,interest_tax,_,interest_cost=liquidate(h,basis,interest,cfg,weights,last)
            debt+=np.maximum(interest-paid,0);tax_total+=interest_tax;fees_total+=interest_cost
        if not begin:wanted,net,gross,tax,sales,cost=withdraw(m)
        cumulative+=net;gross_total+=gross;tax_total+=tax;fees_total+=cost+fee_amount
        success=net>=wanted-.01;fully&=success;funded+=np.where(wanted>0,np.clip(net/np.maximum(wanted,.01),0,1)/(12 if frequency=='Monthly' else 1),0)
        assets=h.sum(1);breach=debt>assets*cfg['pal_maintenance'];maintenance|=breach
        # Iterate because sale taxes/friction also reduce collateral.
        for _ in range(8):
            if not breach.any():break
            assets=h.sum(1);repay=np.where(breach,np.maximum(0,(debt-cfg['pal_ltv']*assets)/(1-cfg['pal_ltv'])),0)
            cash,_,loan_tax,_,loan_cost=liquidate(h,basis,repay,cfg,weights,last)
            debt=np.maximum(0,debt-cash);tax_total+=loan_tax;fees_total+=loan_cost
        due={'Monthly':True,'Quarterly':m%3==2,'Yearly':m%12==11,'None':False}.get(inputs['rebalancing_frequency'],False)
        if strategy=='Rebalanced' and due:
            total=h.sum(1);target=total[:,None]*weights;sell=np.maximum(h-target,0)
            tr=tax_rates(cfg,h,basis,internal=True)
            reb_tax=(sell*tr).sum(1);trade_cost=2*sell.sum(1)*(cfg['trading_friction']+cfg['bid_ask'])
            fraction=np.divide(sell,h,out=np.zeros_like(sell),where=h>0);basis*=1-fraction
            h-=sell;remaining=np.maximum(0,total-reb_tax-trade_cost);new=remaining[:,None]*weights
            basis+=np.maximum(new-h,0);h=new;tax_total+=reb_tax;fees_total+=trade_cost
        if inflation is not None:cpi*=(1+inflation[m])**(1/12)
        else:cpi*=(1+cfg['inflation'])**(1/12)
        equity=np.maximum(0,h.sum(1)-debt);dead=equity<=.01;depleted[np.isnan(depleted)&dead]=(m+1)/12
        peak=np.maximum(peak,equity);drawdown=np.minimum(drawdown,equity/np.maximum(peak,1)-1)
        underwater=np.where(equity<peak-.01,underwater+1,0);recovery=np.maximum(recovery,underwater)
        threshold=cfg['goal_amount']*(cpi if cfg['goal_real'] else 1);floor_ok&=equity>=threshold
        if detail:
            if capture_balances:balances.append(equity.copy())
            row={'Date':str(pd.Period(f"{inputs['forecast_start_year']}-01",freq='M')+m),'Beginning balance':float(np.median(opening)),
                 'Median investment profit before costs':float(np.median(investment_profit)),
                 'Gross withdrawal':float(np.median(gross)),'Estimated withdrawal taxes':float(np.median(tax)),
                 'Net spendable income':float(np.median(net)),'Requested spending':float(np.median(wanted)),
                 'Median PAL debt':float(np.median(debt)),'Median real balance':float(np.median(equity/cpi)),
                 'P50 Cumulative spending':float(np.median(cumulative))}
            row.update({f'P{p} Ending Balance':float(np.percentile(equity,p)) for p in PCTS});records.append(row)
            for j,s in enumerate(inputs['holdings']):funding.append({'Date':row['Date'],'Ticker':s,'Mean gross sale for spending':float(sales[:,j].mean()),'P50 gross sale for spending':float(np.median(sales[:,j]))})
    goal=cfg['goal']
    goal_ok=fully if goal=='Fully fund spending' else floor_ok if goal=='Never below floor' else equity>=threshold if goal=='Reach target' else equity>=initial_equity*(cpi if cfg['goal_real'] else 1)
    surviving=~np.isfinite(depleted);valid=depleted[np.isfinite(depleted)]
    summary={'Portfolio Survival Probability':float(surviving.mean()),'Probability Spending Is Fully Funded':float(fully.mean()),
             'Probability of Depletion':float((~surviving).mean()),'Probability Principal Is Preserved':float((equity>=initial_equity*cpi).mean()),
             'Probability Goal Is Achieved':float(goal_ok.mean()),'Median Ending Balance':float(np.median(equity)),
             'P10 Ending Balance':float(np.percentile(equity,10)),'Median Real Ending Balance':float(np.median(equity/cpi)),
             'Median Depletion Year (conditional)':float(np.median(valid)) if len(valid) else None,
             'Worst Decile Depletion Year (conditional)':float(np.percentile(valid,10)) if len(valid) else None,
             'Years of Withdrawals Funded':float(np.median(funded)),'Maximum Drawdown (median)':float(np.median(drawdown)),
             'Longest Underwater Period (median months)':float(np.median(recovery)),
             'PAL Maintenance Breach Probability':float(maintenance.mean()),'Estimated Taxes (median)':float(np.median(tax_total)),
             'Fees and Friction (median)':float(np.median(fees_total)), 'Net Spending (median)':float(np.median(cumulative)),
             'Gross Spending Withdrawals (median)':float(np.median(gross_total))}
    return {'summary':summary,'table':pd.DataFrame(records),'funding':pd.DataFrame(funding),
            'ending':equity,'fully_funded':fully,'surviving':surviving,'drawdown':drawdown,'final_holdings':h,'final_basis':basis,
            'balances':np.asarray(balances) if detail else None}

def sustainable_withdrawal(paths,inputs,cfg,strategy):
    n=min(paths['returns'].shape[1],cfg['solver_paths'])
    # Disclosed deterministic subset, same paths at each bisection (common random numbers).
    ix=np.linspace(0,paths['returns'].shape[1]-1,n,dtype=int)
    r=paths['returns'][:,ix];inf=paths['inflation'][:,ix];rates=paths['rates'][:,ix]
    lo=0.;hi=inputs['starting_investment']*2
    def probability(amount):
        result=simulate(r,inputs,cfg,strategy,inf,rates,annual_spending=amount,detail=False)
        return float((result['fully_funded'] & result['surviving']).mean())
    if probability(0)<cfg['desired_survival']:return {'initial_annual_withdrawal':0.,'status':'Target unattainable even with zero spending','paths':n}
    for _ in range(14):
        mid=(lo+hi)/2
        if probability(mid)>=cfg['desired_survival']:lo=mid
        else:hi=mid
    return {'initial_annual_withdrawal':lo,'achieved_sample_probability':probability(lo),'target':cfg['desired_survival'],
            'paths':n,'search_resolution':hi-lo,'status':'Simulation estimate; not a guaranteed sustainable rate'}
